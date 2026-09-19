from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings
from monetization import PRODUCTS, price
from texts import t


def main_kb(lang: str) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=f"✨ {t(lang, 'premium')}", callback_data="nav:premium"),
    ]]
    public_channel_url = settings.public_channel(lang)
    if public_channel_url:
        rows.insert(0, [InlineKeyboardButton(text=f"📢 {t(lang, 'public_channel')}", url=public_channel_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_kb(lang: str, market: str, show_manage: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Plus · {price(market, 'plus')} ⭐", callback_data="pay:plus")],
        [InlineKeyboardButton(text=f"⭐ Pro · {price(market, 'pro')} ⭐", callback_data="pay:pro")],
        [InlineKeyboardButton(text=f"✨ Ultra · {price(market, 'ultra')} ⭐", callback_data="pay:ultra")],
        [InlineKeyboardButton(text=f"♠ Black · {price(market, 'black')} ⭐", callback_data="pay:black")],
    ]
    if show_manage:
        rows.append([InlineKeyboardButton(text="Manage subscription", callback_data="subscription:manage")])
    rows.append([InlineKeyboardButton(text=f"← {t(lang, 'menu')}", callback_data="nav:menu")])
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
