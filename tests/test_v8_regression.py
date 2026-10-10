from pathlib import Path

from monetization import MARKETS, PRICE_MATRIX, price
from sales_copy import FOLLOWUPS


def test_asia_market_exists_with_expected_prices():
    assert "asia" in MARKETS
    assert PRICE_MATRIX["asia"] == {"plus": 150, "pro": 350, "ultra": 750, "black": 2500}
    assert price("asia", "pro") == 350


def test_limited_followups_use_v9_event_driven_rescue():
    handlers = Path("handlers.py").read_text(encoding="utf-8")
    main = Path("main.py").read_text(encoding="utf-8")
    assert '"checkout_10m"' in handlers
    assert '"checkout_12h"' in handlers
    assert '{"gate_6h", "offer_3h", "checkout_10m", "checkout_12h", "buyer_checkin_10m"}' in main
    assert "stars" in FOLLOWUPS["checkout_10m"]["en"][0].lower()


def test_paid_access_keyboard_has_only_one_chat_button():
    source = Path("keyboards.py").read_text(encoding="utf-8")
    start = source.index("def access_kb")
    end = source.index("def subscription_kb", start)
    block = source[start:end]
    assert block.count('callback_data="nav:paid_chat"') == 1


def test_manual_chat_has_no_automatic_reply_runtime():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "reply_ai" not in source
    assert "delayed_reply_ai_loop" not in source


def test_successful_payment_sends_clear_receipt_and_admin_prompt():
    handlers = Path("handlers.py").read_text(encoding="utf-8")
    texts = Path("texts.py").read_text(encoding="utf-8")
    assert '"payment_success"' in texts
    assert 't(\n        lang,\n        "payment_success"' in handlers
    assert "Можно сразу написать покупателю вручную" in handlers


def test_all_market_plan_prices_match_single_star_pack_steps():
    allowed = {100, 150, 250, 350, 500, 750, 1000, 1500, 2500, 5000}
    for market, plans in PRICE_MATRIX.items():
        assert set(plans.values()).issubset(allowed), market


def test_admin_functions_from_current_release_are_preserved():
    source = Path("handlers.py").read_text(encoding="utf-8")
    names = {
        "admin_help", "admin_panel_callback", "admin_set_region", "admin_set_language",
        "admin_followups", "admin_note", "admin_user_card", "admin_history",
        "admin_stats", "admin_diag", "admin_jobs", "admin_reply_queue", "admin_calls",
        "admin_call_done", "admin_call_cancel", "admin_send_to_user", "admin_quick_reply",
        "admin_broadcast", "admin_ticket_text_reply", "admin_ticket_media_reply",
    }
    for name in names:
        assert f"async def {name}(" in source


def test_paid_user_pending_message_is_not_cleared_on_payment():
    source = Path("handlers.py").read_text(encoding="utf-8")
    start = source.index("@router.message(F.successful_payment)")
    end = source.index("@router.chat_member()", start)
    payment_block = source[start:end]
    assert "store.cancel_jobs(message.from_user.id, MARKETING_JOB_TYPES)" in payment_block
    assert "store.clear_pending_reply(message.from_user.id)" not in payment_block


def test_cold_followup_does_not_interrupt_engaged_users():
    source = Path("main.py").read_text(encoding="utf-8")
    assert 'stage in {"engaged", "offer_seen", "checkout_started", "checkout_abandoned", "paid"}' in source
