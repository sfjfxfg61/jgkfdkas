from words import LANGS, WORDS, t, telegram_language
from main import summary_text, menu, language_keyboard
from catalog import NEW_CODES


def test_eight_languages_and_names():
    assert set(LANGS) == {"uk", "ru", "en", "de", "fr", "es", "pt", "it"}
    assert t("ru", "button_secret") == "💌 Наш секретик"
    assert t("ru", "button_mistress") == "👑 Моя повелительница"
    assert t("ru", "button_daddy") == "🥺 VIP-папочка"
    assert "татусь" in t("uk", "button_daddy") and "Daddy" in t("en", "button_daddy")


def test_all_active_flows_have_explicit_translations():
    keys = [
        "gate",
        "continue",
        "payment_terms",
        "vip_offer",
        "vip_terms",
        "expiry",
        "call_button",
        "call_sent",
        "call_locked",
        "public_channel",
        "hello",
        "paid",
        "join",
        "not_paid",
        "invoice_error",
        "payment_success",
        "access_error",
        "ask_support",
        "support_received",
    ]
    keys += ["button_" + c for c in NEW_CODES] + ["invoice_" + c for c in NEW_CODES]
    for lg in LANGS:
        assert all(k in WORDS[lg] for k in keys), lg
        text = summary_text(lg)
        assert "{" not in text and "30" in text
        assert t(lg, "button_daddy") in text
        assert "forever" not in text.lower() and "навсегда" not in text.lower()


def test_detection_and_no_notification_toggle():
    assert telegram_language("pt-BR") == "pt"
    assert telegram_language("it_IT") == "it"
    assert telegram_language("UA") == "uk"
    assert telegram_language("ja") is None
    assert len(language_keyboard().inline_keyboard) == 4
    assert not any(
        "notify" in (b.callback_data or "")
        for row in menu("ru").inline_keyboard
        for b in row
    )
