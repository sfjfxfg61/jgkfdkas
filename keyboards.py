from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings
from monetization import PRODUCTS, price, product_title
from texts import t

REGION_NAMES = {
    "ua": "🇺🇦 Україна",
    "cis": "🌍 СНГ / CIS",
    "eu": "🇪🇺 Europe",
    "us": "🇺🇸 USA / Canada",
    "latam": "🌎 LATAM",
    "asia": "🌏 Asia / SEA",
    "global": "🌐 Global",
}

LANG_NAMES = {
    "uk": "🇺🇦 Українська",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
    "fr": "🇫🇷 Français",
    "es": "🇪🇸 Español",
}


def region_confirm_kb(lang: str, market: str) -> InlineKeyboardMarkup:
    ok = {"uk": "Так, залишити", "ru": "Да, оставить", "en": "Yes, keep it", "de": "Ja, behalten", "fr": "Oui, garder", "es": "Sí, dejar así"}.get(lang, "Yes")
    change = {"uk": "Змінити", "ru": "Изменить", "en": "Change", "de": "Ändern", "fr": "Changer", "es": "Cambiar"}.get(lang, "Change")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {ok}", callback_data=f"region:set:{market}")],
        [InlineKeyboardButton(text=f"🌍 {change}", callback_data="region:choose")],
    ])


def region_choose_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=REGION_NAMES["ua"], callback_data="region:set:ua"), InlineKeyboardButton(text=REGION_NAMES["cis"], callback_data="region:set:cis")],
        [InlineKeyboardButton(text=REGION_NAMES["eu"], callback_data="region:set:eu"), InlineKeyboardButton(text=REGION_NAMES["us"], callback_data="region:set:us")],
        [InlineKeyboardButton(text=REGION_NAMES["latam"], callback_data="region:set:latam"), InlineKeyboardButton(text=REGION_NAMES["asia"], callback_data="region:set:asia")],
        [InlineKeyboardButton(text=REGION_NAMES["global"], callback_data="region:set:global")],
    ])


def language_choose_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANG_NAMES["uk"], callback_data="lang:set:uk"), InlineKeyboardButton(text=LANG_NAMES["ru"], callback_data="lang:set:ru")],
        [InlineKeyboardButton(text=LANG_NAMES["en"], callback_data="lang:set:en"), InlineKeyboardButton(text=LANG_NAMES["de"], callback_data="lang:set:de")],
        [InlineKeyboardButton(text=LANG_NAMES["fr"], callback_data="lang:set:fr"), InlineKeyboardButton(text=LANG_NAMES["es"], callback_data="lang:set:es")],
    ])


def public_gate_kb(lang: str, *, join_url: str | None = None) -> InlineKeyboardMarkup:
    """Mandatory-channel keyboard.

    join_url must be a real HTTP(S) Telegram URL. Numeric -100... channel ids are
    deliberately never placed into an inline URL button.
    """
    rows: list[list[InlineKeyboardButton]] = []
    url = (join_url or "").strip()
    if url.startswith(("https://", "http://")):
        rows.append([InlineKeyboardButton(text=f"📣 {t(lang, 'join_public')}", url=url)])
    rows.append([InlineKeyboardButton(text=f"✅ {t(lang, 'check_public')}", callback_data="public:check")])
    rows.append([InlineKeyboardButton(text="🌐 Language", callback_data="settings:language_public")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_kb(lang: str, *, paid: bool = False, tier: str = "free") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"💎 {t(lang, 'premium')}", callback_data="nav:premium")],
        [InlineKeyboardButton(text=f"💌 {t(lang, 'write_btn')}", callback_data="nav:write")],
    ]
    if paid:
        rows.append([InlineKeyboardButton(text=f"🔐 {t(lang, 'access')}", callback_data="nav:access")])
    if tier in {"pro", "ultra", "black"}:
        rows.append([InlineKeyboardButton(text="💌 Chat", callback_data="nav:paid_chat")])
    if tier == "black":
        rows.append([InlineKeyboardButton(text=f"📞 {t(lang, 'call_btn')}", callback_data="call:request")])
    rows.append([InlineKeyboardButton(text=f"⚙️ {t(lang, 'settings_btn')}", callback_data="nav:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Region", callback_data="settings:region"), InlineKeyboardButton(text="🌐 Language", callback_data="settings:language")],
        [InlineKeyboardButton(text="←", callback_data="nav:menu")],
    ])


def premium_kb(lang: str, market: str, *, has_recurring: bool = False) -> InlineKeyboardMarkup:
    icons = {"plus": "💎", "pro": "💌", "ultra": "👑", "black": "🖤"}
    rows = []
    for code in PRODUCTS:
        marker = "⭐ " if code == "pro" else ""
        rows.append([InlineKeyboardButton(
            text=f"{marker}{icons[code]} {product_title(lang, code)} — {price(market, code)} ⭐",
            callback_data=f"pay:{code}",
        )])
    ask = {"uk":"Запитати перед оплатою","ru":"Спросить перед оплатой","en":"Ask before paying","de":"Vorher fragen","fr":"Poser une question","es":"Preguntar antes de pagar"}.get(lang, "Ask before paying")
    rows.append([InlineKeyboardButton(text=f"💬 {ask}", callback_data="nav:write")])
    if has_recurring:
        rows.append([InlineKeyboardButton(text=f"⚙️ {t(lang, 'manage_subscription')}", callback_data="subscription:manage")])
    rows.append([InlineKeyboardButton(text="←", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_kb(invoice_url: str, product_code: str, lang: str) -> InlineKeyboardMarkup:
    buy = {"uk": "Оплатити", "ru": "Оплатить", "en": "Pay", "de": "Bezahlen", "fr": "Payer", "es": "Pagar"}.get(lang, "Pay")
    help_text = {"uk":"Потрібна допомога?","ru":"Нужна помощь?","en":"Need help?","de":"Hilfe nötig?","fr":"Besoin d'aide ?","es":"¿Necesitas ayuda?"}.get(lang, "Need help?")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ {buy} · {product_title(lang, product_code)}", url=invoice_url)],
        [InlineKeyboardButton(text=f"💬 {help_text}", callback_data="nav:write")],
        [InlineKeyboardButton(text="←", callback_data="nav:premium")],
    ])


def followup_checkout_kb(
    lang: str,
    product_code: str,
    market: str,
    *,
    invoice_url: str | None = None,
    amount: int | None = None,
) -> InlineKeyboardMarkup:
    shown_amount = int(amount) if amount else price(market, product_code)
    button = InlineKeyboardButton(
        text=f"⭐ {product_title(lang, product_code)} · {shown_amount} ⭐",
        url=invoice_url if invoice_url else None,
        callback_data=None if invoice_url else f"pay:{product_code}",
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [button],
        [InlineKeyboardButton(text=f"💌 {t(lang, 'write_btn')}", callback_data="nav:write")],
    ])


def followup_offer_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💎 {t(lang, 'premium')}", callback_data="nav:premium")],
        [InlineKeyboardButton(text=f"💌 {t(lang, 'write_btn')}", callback_data="nav:write")],
    ])


def buyer_checkin_kb(lang: str, tier: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"🔐 {t(lang, 'access')}", callback_data="nav:access")]]
    if tier in {"pro", "ultra", "black"}:
        rows.append([InlineKeyboardButton(text="💌 Chat", callback_data="nav:paid_chat")])
    rows.append([InlineKeyboardButton(text=f"💬 {t(lang, 'write_btn')}", callback_data="nav:write")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def access_kb(lang: str, *, recurring: bool, tier: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"🔐 {t(lang, 'channel_join')}", callback_data="access:invite")]]
    if recurring:
        rows.append([InlineKeyboardButton(text=f"⚙️ {t(lang, 'manage_subscription')}", callback_data="subscription:manage")])
    if tier in {"pro", "ultra", "black"}:
        rows.append([InlineKeyboardButton(text="💌 Chat", callback_data="nav:paid_chat")])
    if tier == "black":
        rows.append([InlineKeyboardButton(text=f"📞 {t(lang, 'call_btn')}", callback_data="call:request")])
    rows.append([InlineKeyboardButton(text="←", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_kb(lang: str, renewal_enabled: bool, tier: str) -> InlineKeyboardMarkup:
    rows = []
    if renewal_enabled:
        rows.append([InlineKeyboardButton(text=t(lang, "cancel_renewal"), callback_data="subscription:cancel")])
    else:
        rows.append([InlineKeyboardButton(text=t(lang, "resume_renewal"), callback_data="subscription:resume")])
    if tier == "black":
        rows.append([InlineKeyboardButton(text=f"📞 {t(lang, 'call_btn')}", callback_data="call:request")])
    rows.append([InlineKeyboardButton(text="←", callback_data="nav:access")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_ticket_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👀 Приват", callback_data=f"aq:{user_id}:private"),
            InlineKeyboardButton(text="📸 Контент", callback_data=f"aq:{user_id}:content"),
        ],
        [
            InlineKeyboardButton(text="💸 Дорого", callback_data=f"aq:{user_id}:expensive"),
            InlineKeyboardButton(text="⭐ Тарифы", callback_data=f"aq:{user_id}:paywall"),
        ],
        [
            InlineKeyboardButton(text="💳 Как купить", callback_data=f"aq:{user_id}:buy"),
            InlineKeyboardButton(text="🕒 Потом", callback_data=f"aq:{user_id}:later"),
        ],
        [InlineKeyboardButton(text="✅ Закрыть тикет", callback_data=f"aq:{user_id}:close")],
    ])


def invite_kb(lang: str, invite_url: str, *, tier: str = "free", recurring: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"🔐 {t(lang, 'channel_join')}", url=invite_url)]]
    if recurring:
        rows.append([InlineKeyboardButton(text=f"⚙️ {t(lang, 'manage_subscription')}", callback_data="subscription:manage")])
    if tier in {"pro", "ultra", "black"}:
        rows.append([InlineKeyboardButton(text="💌 Chat", callback_data="nav:paid_chat")])
    if tier == "black":
        rows.append([InlineKeyboardButton(text=f"📞 {t(lang, 'call_btn')}", callback_data="call:request")])
    rows.append([InlineKeyboardButton(text="←", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="ap:stats"),
            InlineKeyboardButton(text="💬 Очередь", callback_data="ap:queue"),
        ],
        [
            InlineKeyboardButton(text="🧲 Дожимы", callback_data="ap:jobs"),
            InlineKeyboardButton(text="📞 Звонки", callback_data="ap:calls"),
        ],
        [
            InlineKeyboardButton(text="📣 Рассылка", callback_data="ap:broadcast"),
            InlineKeyboardButton(text="👤 Пользователь", callback_data="ap:userhelp"),
        ],
        [
            InlineKeyboardButton(text="🚦 Заливщики", callback_data="ap:partners"),
        ],
        [
            InlineKeyboardButton(text="🩺 Диагностика", callback_data="ap:diag"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="ap:home"),
        ],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Админ-панель", callback_data="ap:home")]
    ])


def partner_profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="partner:self")],
    ])
