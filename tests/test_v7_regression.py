"""Static checks for V7 paths we cannot call against production Telegram here."""
import ast
from pathlib import Path

from config import settings
from monetization import PRICE_MATRIX, make_payload, parse_payment_details, amount_matches_invoice


def _function_body(path: str, func: str) -> str:
    text = Path(path).read_text(encoding='utf-8')
    module = ast.parse(text)
    function = next(n for n in module.body if isinstance(n, ast.AsyncFunctionDef) and n.name == func)
    return ast.get_source_segment(text, function)


def test_pre_checkout_does_not_depend_on_network():
    fn = _function_body('handlers.py', 'pre_checkout')
    assert 'store.' not in fn
    assert '_public_membership' not in fn
    assert '_private_access_available' not in fn
    assert 'query.answer(' in fn


def test_payment_recovery_admin_notice_and_access_flow():
    fn = _function_body('handlers.py', 'apply_paid_receipt')
    assert 'record_payment(' in fn
    assert 'CRITICAL paid charge not activated' in fn
    assert '_create_private_invite' in fn
    assert 'notify_admin' in fn


def test_channel_join_updates_membership_flag():
    fn = _function_body('handlers.py', 'private_channel_member_update')
    assert 'channel_member=new_status' in fn
    assert 'not premium_is_active(user)' in fn


def test_restricted_automations_are_default():
    assert settings.marketing_mode == 'limited'
    worker = _function_body('main.py', 'followup_loop')
    assert 'job_type not in' in worker
    assert '"cold_daily"' not in worker.split('job_type not in',1)[1].split('await store.finish_job',1)[0]


def test_new_signed_invoice_stable():
    for market, tiers in PRICE_MATRIX.items():
        for tier, amount in tiers.items():
            details = parse_payment_details(make_payload(12345, tier, market), 12345)
            assert details is not None
            assert details.amount == amount
            assert amount_matches_invoice(details, amount)
            assert not amount_matches_invoice(details, amount + 1)
