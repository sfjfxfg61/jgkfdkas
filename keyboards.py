from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from texts import TEXTS

def welcome_kb(lang: str, pub_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["pub_btn"], url=pub_url)],
            [InlineKeyboardButton(text=TEXTS[lang]["check_btn"], callback_data=f"check_sub_{lang}")],
            [InlineKeyboardButton(text="🌐 Language / Язык", callback_data="change_lang")]
        ]
    )

def trigger_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["buy_btn"], callback_data=f"buy_trigger_{lang}")]
        ]
    )

def languages_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="set_lang_uk"),
             InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
             InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="set_lang_de")],
            [InlineKeyboardButton(text="🇫🇷 Français", callback_data="set_lang_fr"),
             InlineKeyboardButton(text="🇪🇸 Español", callback_data="set_lang_es")]
        ]
    )
