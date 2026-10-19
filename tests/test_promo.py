from catalog import new_payload, parse_invoice, signature

def test_promo_valid_and_signed():
    p = new_payload(42, 'vip', 'eu', now=100000, promo_until=107200)
    assert parse_invoice(p, 42, 500, allow_expired=True).amount == 500
    assert parse_invoice(p, 42, 1000, allow_expired=True) is None
    assert parse_invoice(p, 43, 500, allow_expired=True) is None

def test_promo_rejects_invalid_duration():
    assert new_payload(42, 'vip', 'eu', now=100000, promo_until=108000).startswith('simple2:')
    assert new_payload(42, 'vip', 'ua', now=100000, promo_until=107200).startswith('simple2:')
