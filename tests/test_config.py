from config import telegram_chat_ref


def test_public_channel_links_work_for_membership_check():
    assert telegram_chat_ref("https://t.me/example_channel") == "@example_channel"
    assert telegram_chat_ref("@example_channel") == "@example_channel"
    assert telegram_chat_ref("-1001234567890") == -1001234567890


def test_private_invite_link_is_not_a_chat_ref():
    assert telegram_chat_ref("https://t.me/+abcdef") is None
