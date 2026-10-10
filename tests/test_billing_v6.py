"""Regression tests for repricing existing Telegram Stars subscriptions."""
import hashlib
import hmac
import time

from config import settings
from monetization import (
    LEGACY_PRICE_MATRIX, MARKETS, PRICE_MATRIX, PRODUCTS,
    amount_matches_invoice, default_market, make_payload,
    parse_payment_details, price,
)


def _legacy_payload(version: str, user: int, product: str, market: str, expiry: int | None = None) -> str:
    if version == "v5":
        assert expiry is not None
        body = f"v5:{user}:{product}:{market}:{expiry}"
    else:
        body = f"{version}:{user}:{product}:{market}"
    signature = hmac.new(settings.bot_token.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{body}:{signature}"


def test_current_prices_match_agreed_region_bands():
    for market in {"ua", "cis", "latam"}:
        assert [price(market, code) for code in PRODUCTS] == [150, 350, 750, 2500]
    for market in {"eu", "us", "global"}:
        assert [price(market, code) for code in PRODUCTS] == [250, 500, 1000, 2500]
    assert set(PRICE_MATRIX) == set(LEGACY_PRICE_MATRIX) == MARKETS


def test_location_is_never_guessed_from_language():
    for language in ("uk", "ru", "en", "es", "de", "fr", "xx"):
        assert default_market(language) == "global"


def test_v6_signed_invoice_keeps_original_amount_even_after_price_change(monkeypatch):
    payload = make_payload(123, "pro", "eu")
    signed = parse_payment_details(payload, 123)
    assert signed is not None
    assert signed.amount == 500
    assert amount_matches_invoice(signed, 500)
    assert not amount_matches_invoice(signed, 1399)
    monkeypatch.setitem(PRICE_MATRIX["eu"], "pro", 599)
    assert amount_matches_invoice(parse_payment_details(payload, 123), 500)
    assert parse_payment_details(payload + "z", 123) is None
    assert parse_payment_details(payload, 333) is None


def test_v5_invoices_and_renewals_keep_legacy_prices():
    original = _legacy_payload("v5", 456, "black", "us", int(time.time()) + 60)
    old = parse_payment_details(original, 456)
    assert old is not None and old.amount is None
    assert amount_matches_invoice(old, 9999)
    assert not amount_matches_invoice(old, 2000)
    expired = _legacy_payload("v5", 456, "black", "us", int(time.time()) - 60)
    assert parse_payment_details(expired, 456) is None
    renewed = parse_payment_details(expired, 456, allow_expired=True)
    assert renewed is not None and amount_matches_invoice(renewed, 9999)


def test_old_v2_to_v4_payloads_remain_recognized():
    for version in ("v2", "v3", "v4"):
        payload = _legacy_payload(version, 11, "plus", "ua")
        detail = parse_payment_details(payload, 11)
        assert detail is not None and detail.version == version
        assert amount_matches_invoice(detail, 249)
        assert amount_matches_invoice(detail, 150)
