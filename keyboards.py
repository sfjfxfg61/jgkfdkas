from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings
from monetization import MARKETS, price, product_title
from texts import t


def main_kb(lang: str) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=f"✨ {t(lang, 'premium')}", callback_data="nav:premium"),
    ]]
    public_channel_url = settings.public_channel(lang)
    if public_channel_url:
        rows.insert(0, [InlineKeyboardButton(text=f"📢 {t(lang, 'public_channel')}", url=public_channel_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


REGION_NAMES = {
    "ua": "Україна", "cis": "Східна Європа", "latam": "Латинська Америка",
    "eu": "Європа / Британія", "us": "США / Канада", "global": "Інший регіон",
}


def region_confirm_kb(lang: str, market: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✓ {t(lang, 'region_confirm')} · {REGION_NAMES[market]}", callback_data=f"region:set:{market}")],
        [InlineKeyboardButton(text=t(lang, "region_change"), callback_data="region:choose")],
    ])


def region_choose_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"region:set:{code}")]
        for code, name in REGION_NAMES.items() if code in MARKETS
    ])


def premium_kb(
    lang: str,
    market: str,
    show_manage: bool = False,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"⚡ {product_title(lang, 'plus')} · {price(market, 'plus')} ⭐",
                callback_data="pay:plus",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔥 {product_title(lang, 'pro')} · {price(market, 'pro')} ⭐",
                callback_data="pay:pro",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🚀 {product_title(lang, 'ultra')} · {price(market, 'ultra')} ⭐",
                callback_data="pay:ultra",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"💎 {product_title(lang, 'black')} · {price(market, 'black')} ⭐",
                callback_data="pay:black",
            )
        ],
    ]

    if show_manage:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Manage subscription",
                    callback_data="subscription:manage",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=f"← {t(lang, 'menu')}",
                callback_data="nav:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_kb(
    url: str,
    product_code: str,
    lang: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⭐ {product_title(lang, product_code)}",
                    url=url,
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"← {t(lang, 'premium')}",
                    callback_data="nav:premium",
                )
            ],
        ]
    )


def subscription_kb(lang: str, recurring: bool) -> InlineKeyboardMarkup:
    rows = []
    if recurring:
        rows.append([InlineKeyboardButton(text="Cancel renewal", callback_data="subscription:cancel")])
    else:
        rows.append([InlineKeyboardButton(text="Resume renewal", callback_data="subscription:resume")])
    rows.append([InlineKeyboardButton(text=f"← {t(lang, 'menu')}", callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
