from types import SimpleNamespace

import pytest

pytest.importorskip("aiogram")

import channel_access
import keyboards


class FakeBot:
    def __init__(self):
        self.created = []

    async def get_chat(self, ref):
        return SimpleNamespace(id=int(ref) if str(ref).lstrip('-').isdigit() else -1001234567890)

    async def get_me(self):
        return SimpleNamespace(id=999)

    async def get_chat_member(self, chat_id, user_id):
        return SimpleNamespace(
            status=SimpleNamespace(value='administrator'),
            can_invite_users=True,
            can_restrict_members=True,
        )

    async def create_chat_invite_link(self, chat_id, **kwargs):
        self.created.append((chat_id, kwargs))
        return SimpleNamespace(invite_link='https://t.me/+generated123')


def _set_setting(name, value):
    old = getattr(channel_access.settings, name)
    object.__setattr__(channel_access.settings, name, value)
    return old


@pytest.mark.asyncio
async def test_numeric_public_channel_creates_clickable_invite():
    old = _set_setting('pub_link_uk', '-1003583530409')
    try:
        bot = FakeBot()
        url = await channel_access.public_join_url(bot, 'uk', 123)
        assert url == 'https://t.me/+generated123'
        assert bot.created[0][0] == -1003583530409
        assert bot.created[0][1]['member_limit'] == 1
    finally:
        object.__setattr__(channel_access.settings, 'pub_link_uk', old)


def test_public_gate_never_uses_numeric_id_as_url():
    kb = keyboards.public_gate_kb('uk', join_url='-1003583530409')
    urls = [button.url for row in kb.inline_keyboard for button in row if button.url]
    assert urls == []


@pytest.mark.asyncio
async def test_numeric_paid_channel_requires_approval():
    old = _set_setting('private_channel_url', '-1007777777777')
    try:
        bot = FakeBot()
        url = await channel_access.private_join_url(bot, 456)
        assert url == 'https://t.me/+generated123'
        assert bot.created[0][0] == -1007777777777
        assert bot.created[0][1]['creates_join_request'] is True
        assert 'member_limit' not in bot.created[0][1]
    finally:
        object.__setattr__(channel_access.settings, 'private_channel_url', old)


@pytest.mark.asyncio
async def test_static_tg_link_stays_supported():
    old = _set_setting('pub_link_en', 'https://t.me/+abcDEF')
    try:
        bot = FakeBot()
        url = await channel_access.public_join_url(bot, 'en', 789)
        assert url == 'https://t.me/+abcDEF'
        assert bot.created == []
    finally:
        object.__setattr__(channel_access.settings, 'pub_link_en', old)
