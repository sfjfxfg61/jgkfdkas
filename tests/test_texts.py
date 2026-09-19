from texts import TEXTS, t


def test_all_supported_locales_have_core_interface_copy() -> None:
    required = {
        "intro", "begin", "choose_style", "style_warm", "style_playful", "style_calm",
        "ready", "menu", "chat", "profile", "memory", "settings", "premium", "not_ready",
        "chat_prompt", "ai_error", "profile_text", "memories_empty", "memories_title",
        "settings_text", "on", "off", "toggle_proactive", "change_style", "clear_memory",
        "clear_confirm", "clear_yes", "cancel", "cleared", "about", "proactive",
    }
    for lang in ("ru", "uk", "en", "es", "de", "fr"):
        assert required <= TEXTS[lang].keys()
        assert t(lang, "menu") != "menu"
