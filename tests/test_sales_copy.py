from sales_copy import FOLLOWUPS, QUICK_REPLIES, followup_text, quick_reply


def test_copy_exists_for_all_languages():
    langs = {"uk", "ru", "en", "de", "fr", "es"}
    for bank in QUICK_REPLIES.values():
        assert langs.issubset(bank)
    for bank in FOLLOWUPS.values():
        assert langs.issubset(bank)


def test_copy_is_deterministic_per_user_and_context():
    assert quick_reply("uk", "private", 123) == quick_reply("uk", "private", 123)
    assert followup_text("ru", "checkout_30m", 123, "Рома") == followup_text("ru", "checkout_30m", 123, "Рома")
