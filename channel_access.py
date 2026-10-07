from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlparse

from aiogram import Bot

from config import settings

logger = logging.getLogger(__name__)


class ChannelAccessError(RuntimeError):
    pass


@dataclass(slots=True)
class ChannelCapabilities:
    resolvable: bool = False
    is_admin: bool = False
    can_invite: bool = False
    can_restrict: bool = False
    channel_id: int | None = None
    error: str | None = None


def telegram_http_url(raw: str | None) -> str | None:
    """Return a safe Telegram HTTP(S) URL only.

    Numeric -100... ids are intentionally rejected here: Telegram inline keyboard
    URL buttons only accept real HTTP URLs.
    """
    value = (raw or "").strip()
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.hostname not in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
        return None
    if not parsed.path.strip("/"):
        return None
    return value if "://" in value else f"https://{value}"


async def resolve_channel_id(bot: Bot, ref: int | str | None) -> int | None:
    if ref is None:
        return None
    try:
        return int((await bot.get_chat(ref)).id)
    except Exception as exc:
        logger.warning("Could not resolve Telegram channel %r: %s", ref, exc)
        return None


async def channel_capabilities(bot: Bot, ref: int | str | None) -> ChannelCapabilities:
    if ref is None:
        return ChannelCapabilities(error="unresolved")
    try:
        chat = await bot.get_chat(ref)
        channel_id = int(chat.id)
        me = await bot.get_me()
        member = await bot.get_chat_member(channel_id, me.id)
        raw = getattr(member, "status", "")
        status = getattr(raw, "value", str(raw)).lower().split(".")[-1]
        creator = status == "creator"
        admin = creator or status == "administrator"
        can_invite = creator or (admin and bool(getattr(member, "can_invite_users", False)))
        can_restrict = creator or (admin and bool(getattr(member, "can_restrict_members", False)))
        return ChannelCapabilities(
            resolvable=True,
            is_admin=admin,
            can_invite=can_invite,
            can_restrict=can_restrict,
            channel_id=channel_id,
        )
    except Exception as exc:
        return ChannelCapabilities(error=str(exc)[:300])


async def _single_use_invite(
    bot: Bot,
    ref: int | str,
    *,
    name: str,
    hours: int = 24,
) -> str:
    caps = await channel_capabilities(bot, ref)
    if not caps.resolvable or not caps.channel_id:
        raise ChannelAccessError(f"channel {ref!r} cannot be resolved")
    if not caps.can_invite:
        raise ChannelAccessError(
            f"bot cannot create invite links in {caps.channel_id}; enable Invite Users permission"
        )
    try:
        invite = await bot.create_chat_invite_link(
            caps.channel_id,
            name=name[:32],
            expire_date=datetime.now(timezone.utc) + timedelta(hours=hours),
            member_limit=1,
        )
        url = str(invite.invite_link)
        if not telegram_http_url(url):
            raise ChannelAccessError("Telegram returned an invalid invite URL")
        return url
    except ChannelAccessError:
        raise
    except Exception as exc:
        raise ChannelAccessError(f"createChatInviteLink failed for {caps.channel_id}: {exc}") from exc


async def public_join_url(bot: Bot, lang: str, user_id: int) -> str | None:
    """Get a clickable join URL for the language-specific mandatory channel.

    Backwards compatible behavior:
    - PUB_LINK_*=https://t.me/... -> use the configured link directly.
    - PUB_LINK_*=@publicname      -> use https://t.me/publicname.
    - PUB_LINK_*=-100...          -> treat as a private channel id and ask Telegram
                                    to create a one-user 24h invite link.
    """
    raw = settings.public_channel(lang)
    direct = telegram_http_url(raw)
    if direct:
        return direct

    ref = settings.public_channel_ref(lang)
    if ref is None:
        return None
    if isinstance(ref, str) and ref.startswith("@"):
        return f"https://t.me/{ref[1:]}"

    return await _single_use_invite(
        bot,
        ref,
        name=f"pub-{lang}-{user_id}",
        hours=24,
    )


async def private_channel_id(bot: Bot) -> int | None:
    return await resolve_channel_id(bot, settings.private_channel_ref)


async def private_access_available(bot: Bot) -> bool:
    # A static invite/public link is a backwards-compatible fallback.
    if telegram_http_url(settings.private_channel_url):
        return True
    caps = await channel_capabilities(bot, settings.private_channel_ref)
    return bool(caps.resolvable and caps.can_invite)


async def private_join_url(bot: Bot, user_id: int) -> str | None:
    """Create a one-user paid-channel invite when PRIVATE_CHANNEL_URL is a chat id.

    If the deployment still uses an explicit Telegram invite link, keep supporting it.
    """
    ref = settings.private_channel_ref
    if ref is not None:
        try:
            return await _single_use_invite(
                bot,
                ref,
                name=f"paid-{user_id}",
                hours=24,
            )
        except ChannelAccessError:
            logger.exception("Could not create paid invite for user %s", user_id)

    return telegram_http_url(settings.private_channel_url)
