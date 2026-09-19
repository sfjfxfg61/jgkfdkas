from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from monetization import PRODUCTS, price
from texts import t


def intro_kb(lang: str, public_channel_url: str = "") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t(lang, "begin"), callback_data="onboarding:begin")]]
    if public_channel_url:
        rows.append([InlineKeyboardButton(text=t(lang, "public_channel"), url=public_channel_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def styles_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "style_warm"), callback_data="style:warm")],
        [InlineKeyboardButton(text=t(lang, "style_playful"), callback_data="style:playful")],
        [InlineKeyboardButton(text=t(lang, "style_calm"), callback_data="style:calm")],
    ])


def main_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💬 {t(lang, 'chat')}", callback_data="nav:chat")],
        [InlineKeyboardButton(text=f"👤 {t(lang, 'profile')}", callback_data="nav:profile"), InlineKeyboardButton(text=f"🧠 {t(lang, 'memory')}", callback_data="nav:memory")],
        [InlineKeyboardButton(text=f"⚙️ {t(lang, 'settings')}", callback_data="nav:settings"), InlineKeyboardButton(text=f"✨ {t(lang, 'premium')}", callback_data="nav:premium")],
    ])


def premium_kb(lang: str, market: str, show_manage: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Plus · {price(market, 'plus')} ⭐", callback_data="pay:plus")],
        [InlineKeyboardButton(text=f"⭐ Pro · {price(market, 'pro')} ⭐", callback_data="pay:pro")],
        [InlineKeyboardButton(text=f"✨ Ultra · {price(market, 'ultra')} ⭐", callback_data="pay:ultra")],
        [InlineKeyboardButton(text=f"♠ Black · {price(market, 'black')} ⭐", callback_data="pay:black")],
        [InlineKeyboardButton(text="🌍 Pricing region", callback_data="market:choose")],
    ]
    if show_manage:
        rows.append([InlineKeyboardButton(text="Manage subscription", callback_data="subscription:manage")])
    rows.append([InlineKeyboardButton(text=f"← {t(lang, 'menu')}", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(lang: str, proactive: bool) -> InlineKeyboardMarkup:
    state = t(lang, "on" if proactive else "off")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "toggle_proactive", state=state), callback_data="settings:proactive")],
        [InlineKeyboardButton(text=t(lang, "change_style"), callback_data="settings:style")],
        [InlineKeyboardButton(text="🌍 Pricing region", callback_data="market:choose")],
        [InlineKeyboardButton(text=t(lang, "clear_memory"), callback_data="memory:confirm")],
        [InlineKeyboardButton(text=f"← {t(lang, 'menu')}", callback_data="nav:menu")],
    ])


def market_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🇺🇸 USA / Canada", callback_data="market:set:us")],
        [InlineKeyboardButton(text="🇪🇺 EU / UK", callback_data="market:set:eu")],
        [InlineKeyboardButton(text="🇺🇦 Ukraine", callback_data="market:set:ua")],
        [InlineKeyboardButton(text="🌎 Latin America", callback_data="market:set:latam")],
        [InlineKeyboardButton(text="🌍 Eastern Europe", callback_data="market:set:cis")],
        [InlineKeyboardButton(text="🌐 Global", callback_data="market:set:global")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_kb(url: str, product_code: str, lang: str) -> InlineKeyboardMarkup:
    product = PRODUCTS[product_code]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Pay for {product.title}", url=url)],
        [InlineKeyboardButton(text=f"← {t(lang, 'premium')}", callback_data="nav:premium")],
    ])


def subscription_kb(lang: str, recurring: bool) -> InlineKeyboardMarkup:
    rows = []
    if recurring:
        rows.append([InlineKeyboardButton(text="Cancel renewal", callback_data="subscription:cancel")])
    else:
        rows.append([InlineKeyboardButton(text="Resume renewal", callback_data="subscription:resume")])
    rows.append([InlineKeyboardButton(text=f"← {t(lang, 'menu')}", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_clear_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "clear_yes"), callback_data="memory:clear")],
        [InlineKeyboardButton(text=t(lang, "cancel"), callback_data="nav:settings")],
    ])
