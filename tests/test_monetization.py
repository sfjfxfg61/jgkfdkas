from monetization import (
    ENTITLEMENTS,
    PRICE_MATRIX,
    PRODUCTS,
    default_market,
    make_payload,
    parse_payload,
    paywall_text,
)


def test_market_selection_uses_language_only() -> None:
    assert default_market("en", "us_creator42") == "us"
    assert default_market("en", "eu_launch") == "us"
    assert default_market("es") == "latam"
    assert default_market("uk") == "ua"
    assert default_market("en") == "us"


def test_signed_payload_round_trip_and_tamper_rejection() -> None:
    payload = make_payload(42, "pro", "us")
    parsed = parse_payload(payload, 42)
    assert parsed is not None
    product, market = parsed
    assert product.code == "pro"
    assert market == "us"
    assert parse_payload(payload, 41) is None
    assert parse_payload(payload.replace(":us:", ":eu:"), 42) is None


def test_product_entitlements_increase_and_prices_fit_stars_limit() -> None:
    assert all(not hasattr(value, "daily_messages") for value in ENTITLEMENTS.values())
    assert all(product.duration_days == 30 and product.recurring for product in PRODUCTS.values())
    recurring_codes = [code for code, product in PRODUCTS.items() if product.recurring]
    assert all(0 < prices[code] <= 10_000 for prices in PRICE_MATRIX.values() for code in recurring_codes)


def test_us_has_high_value_annual_offer_and_localized_paywalls() -> None:
    assert PRICE_MATRIX["us"]["black"] == 9_999
    assert PRICE_MATRIX["us"]["pro"] > PRICE_MATRIX["global"]["pro"]
    for lang in ("ru", "uk", "en", "es", "de", "fr"):
        text = paywall_text(lang, "us")
        assert "9" in text
        assert "⭐" in text
        assert "messages per day" not in text
