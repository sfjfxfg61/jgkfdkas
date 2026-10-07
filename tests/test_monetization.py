from monetization import MARKETS, PRODUCTS, make_payload, parse_payload, price


def test_every_market_has_every_product():
    for market in MARKETS:
        for code in PRODUCTS:
            assert price(market, code) > 0


def test_invoice_payload_roundtrip_and_tamper_rejected():
    payload = make_payload(12345, "pro", "ua")
    parsed = parse_payload(payload, 12345)
    assert parsed is not None
    product, market = parsed
    assert product.code == "pro"
    assert market == "ua"
    assert parse_payload(payload + "x", 12345) is None
    assert parse_payload(payload, 99999) is None
