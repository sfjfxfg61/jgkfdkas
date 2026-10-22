from catalog import new_payload, parse_invoice, promo_price, plans


def test_promo_all_markets_signed_and_expiring():
    for market in ("ua", "cis", "global", "eu", "latam"):
        p = new_payload(42, "daddy", market, now=100000, promo_until=107200)
        amount = promo_price(market)
        assert amount < plans(market)["daddy"].stars
        assert parse_invoice(p, 42, amount, allow_expired=True).code == "daddy"
        assert parse_invoice(p, 42, amount) is None
        assert parse_invoice(p, 43, amount, allow_expired=True) is None


def test_manual_custom_price_is_signed():
    p = new_payload(42, "mistress", "eu", custom_amount=333)
    assert parse_invoice(p, 42, 333).amount == 333
    assert parse_invoice(p, 42, 500) is None
