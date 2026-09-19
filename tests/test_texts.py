from texts import TEXTS, t


def test_all_supported_locales_have_core_interface_copy() -> None:
    required = {
        "welcome", "menu", "premium", "public_channel", "about_button", "about",
        "not_ready", "ai_error", "premium_nudge", "channel_nudge", "proactive",
    }
    for lang in ("ru", "uk", "en", "es", "de", "fr"):
        assert required <= TEXTS[lang].keys()
        assert t(lang, "menu") != "menu"
