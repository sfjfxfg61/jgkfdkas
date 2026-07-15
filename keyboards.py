# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from texts import TEXTS, get_tariff_price

def welcome_kb(lang: str, pub_url: str) -> InlineKeyboardMarkup:
    """Стартовая клавиатура: подписка + проверка + выбор языка"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=TEXTS[lang]["pub_btn"], url=pub_url)],
        [InlineKeyboardButton(text=TEXTS[lang]["check_btn"], callback_data=f"chk_{lang}")],
        [InlineKeyboardButton(text="🌍 Language / Мова", callback_data="lng_change")]
    ])

def languages_kb() -> InlineKeyboardMarkup:
    """Клавиатура смены языка (сокращенные callback_data для экономии памяти)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lng_set_uk"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lng_set_ru")
        ],
        [
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lng_set_en"),
            InlineKeyboardButton(text="🇪🇸 Español", callback_data="lng_set_es")
        ],
        [
            InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lng_set_de"),
            InlineKeyboardButton(text="🇫🇷 Français", callback_data="lng_set_fr")
        ]
    ])

def trigger_kb(lang: str) -> InlineKeyboardMarkup:
    """
    Генерация трех кнопок тарифов (Эффект Компромисса).
    Callback-данные сжаты до предела ('pay_{tier}_{lang}'), чтобы не перегружать память Telegram.
    """
    p_test = get_tariff_price(lang, "test")
    p_life = get_tariff_price(lang, "lifetime")
    p_vip = get_tariff_price(lang, "vip")

    t_test = TEXTS[lang]["tier_test"]
    t_life = TEXTS[lang]["tier_lifetime"]
    t_vip = TEXTS[lang]["tier_vip"]

    return InlineKeyboardMarkup(inline_keyboard=[
        # 1. Дешевый тариф (Тест)
        [InlineKeyboardButton(text=f"{t_test} — {p_test} ★", callback_data=f"pay_test_{lang}")],
        # 2. Компромиссный тариф (Наша цель - выделен огнем!)
        [InlineKeyboardButton(text=f"{t_life} — {p_life} ★ 🔥", callback_data=f"pay_life_{lang}")],
        # 3. Дорогой тариф (Якорь)
        [InlineKeyboardButton(text=f"{t_vip} — {p_vip} ★", callback_data=f"pay_vip_{lang}")]
    ])

def admin_user_kb(user_id: int, is_paid: bool) -> InlineKeyboardMarkup:
    """Управление доступом пользователя из панели администратора"""
    action = "take" if is_paid else "give"
    text = "🔴 Забрать доступ" if is_paid else "🟢 Выдать доступ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"adm_tgl_{action}_{user_id}")]
    ])
