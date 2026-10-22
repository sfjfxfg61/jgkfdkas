from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest


def register(db, uid=1, lang="ru", ref="direct"):
    return db.execute(
        "select v4_register(%s,%s,%s,%s,%s)", (uid, "Ник", "username", lang, ref)
    ).fetchone()[0]


def pay(db, charge="charge1", uid=1, plan="secret", days=30, amount=100):
    return db.execute(
        "select v4_apply_payment(%s,%s,%s,%s,%s,%s,%s)",
        (uid, charge, "signed-payload-" + charge, amount, plan, days, "cis"),
    ).fetchone()[0]


def test_migration_repeatable_and_legacy_access(db):
    db.execute(
        (
            Path(__file__).resolve().parents[1] / "migrations/001_victoria_v4.sql"
        ).read_text()
    )
    u = db.execute("select v4_sync_access(99)").fetchone()[0]
    assert (
        u["is_paid"]
        and datetime.fromisoformat(u["premium_until"]).astimezone(timezone.utc).year
        == 2099
    )


def test_supported_languages_and_preserved_first_source(db):
    for i, lg in enumerate(("uk", "ru", "en", "de", "fr", "es", "pt", "it"), 100):
        u = register(db, i, lg, "source1")
        assert u["lang"] == lg
        v = register(db, i, "en", "source2")
        assert v["lang"] == lg and v["ref"] == "source1"
    assert register(db, 500, None)["acquisition_lang"] is None


def test_payment_atomic_dedupe_extension_and_tier_rights(db):
    register(db)
    a = pay(db, plan="daddy")
    b = pay(db, plan="daddy")
    assert not a["duplicate"] and b["duplicate"]
    assert a["user"]["premium_until"] == b["user"]["premium_until"]
    assert (
        db.execute("select count(*) from payments where user_id=1").fetchone()[0] == 1
    )
    assert a["user"]["calls_until"]
    low = pay(db, charge="low", plan="secret")
    assert low["user"]["subscription_tier"] == "daddy"
    extended = pay(db, charge="renew", plan="daddy")
    assert datetime.fromisoformat(
        extended["receipt"]["entitlement_until"]
    ) - datetime.fromisoformat(a["receipt"]["entitlement_until"]) == timedelta(days=30)


def test_refund_idempotent_retains_other_access(db):
    register(db)
    pay(db, plan="daddy")
    pay(db, charge="low", plan="secret")
    u = db.execute("select v4_refund(1,'charge1')").fetchone()[0]
    assert (
        u["is_paid"] and u["subscription_tier"] == "secret" and u["calls_until"] is None
    )
    u2 = db.execute("select v4_refund(1,'charge1')").fetchone()[0]
    assert u == u2
    replay = pay(db, plan="daddy")
    assert replay["duplicate"] and not replay["user"]["calls_until"]


def test_commission_transaction_rollback(db):
    db.execute(
        "insert into traffic_partners(telegram_user_id,code,display_name) values(888,'partner','Partner')"
    )
    register(db, ref="partner")
    pay(db)
    pay(db)
    assert db.execute(
        "select count(*),sum(commission_stars) from traffic_commissions"
    ).fetchone() == (1, 30)
    register(db, uid=2)
    with pytest.raises(Exception):
        with db.transaction():
            db.execute(
                "select v4_apply_payment(2,'charge1','other',100,'secret',30,'cis')"
            )
    assert (
        db.execute("select count(*) from payments where user_id=2").fetchone()[0] == 0
    )


def test_start_only_one_delayed_job(db):
    register(db)
    for _ in range(3):
        db.execute("select v4_start(1)")
    row = db.execute(
        "select scheduled_at,created_at from automation_jobs where user_id=1"
    ).fetchone()
    assert row[0] - row[1] == timedelta(hours=1)
    assert (
        db.execute("select count(*) from automation_jobs where user_id=1").fetchone()[0]
        == 1
    )


def test_atomic_claim_and_lease_recovery(db):
    register(db)
    db.execute("select v4_start(1)")
    db.execute(
        "update automation_jobs set scheduled_at=now()-interval '1 second' where user_id=1"
    )
    a = db.execute("select * from v4_claim_jobs('worker-a',10)").fetchall()
    assert len(a) == 1
    assert db.execute("select * from v4_claim_jobs('worker-b',10)").fetchall() == []
    db.execute(
        "update automation_jobs set locked_at=now()-interval '6 minutes' where user_id=1"
    )
    assert len(db.execute("select * from v4_claim_jobs('worker-b',10)").fetchall()) == 1


def test_cleanup_archives_and_keeps_financial_records(db):
    register(db)
    pay(db)
    db.execute(
        "insert into messages(user_id,role,content,created_at) values(1,'user','old',now()-interval '181 days')"
    )
    db.execute(
        "insert into events(user_id,event,created_at) values(1,'simple_offer_seen',now()-interval '91 days')"
    )
    db.execute(
        "insert into automation_jobs(user_id,job_type,status,scheduled_at,dedupe_key,created_at,last_error) values(1,'v4_daily','failed',now(),'old-daily',now()-interval '91 days','TestError')"
    )
    result = db.execute("select v4_cleanup()").fetchone()[0]
    assert (
        db.execute("select last_error from automation_errors_archive").fetchone()[0]
        == "TestError"
    )
    assert (
        db.execute(
            "select count(*) from automation_jobs where dedupe_key='old-daily'"
        ).fetchone()[0]
        == 0
    )
    assert result["archived_messages"] == 1 and result["archived_events"] == 1
    assert (
        db.execute("select content from messages_archive where user_id=1").fetchone()[0]
        == "old"
    )
    assert (
        db.execute("select count(*) from messages where user_id=1").fetchone()[0] == 0
    )
    assert (
        db.execute("select count(*) from payments where user_id=1").fetchone()[0] == 1
    )
    data = db.execute("select v4_analytics(999999)").fetchone()[0]
    assert data["offers"] == 1 and data["messages"] == 1 and data["stars"] == 100


def test_queue_scheduling_and_metrics(db):
    register(db)
    db.execute(
        "update users set next_reminder_at=now()-interval '1 day' where user_id=1"
    )
    db.execute("select v4_schedule('UTC','00:00',999999)")
    db.execute("select v4_schedule('UTC','00:00',999999)")
    assert (
        db.execute(
            "select count(*) from automation_jobs where user_id=1 and job_type='v4_daily'"
        ).fetchone()[0]
        == 1
    )
    assert db.execute("select v4_metrics()").fetchone()[0]["version"] == 4


def test_update_journal_and_security(db):
    db.execute("insert into telegram_updates(update_id,body) values(1,'{}'),(2,'{}')")
    assert len(db.execute("select * from v4_claim_updates('one',1)").fetchall()) == 1
    assert len(db.execute("select * from v4_claim_updates('two',2)").fetchall()) == 1
    assert (
        db.execute(
            "select has_function_privilege('anon','v4_apply_payment(bigint,text,text,integer,text,integer,text)','execute')"
        ).fetchone()[0]
        is False
    )


def test_call_request_rights_and_dedupe(db):
    register(db)
    pay(db, plan="secret")
    assert not db.execute("select v4_request_call(1)").fetchone()[0]["allowed"]
    pay(db, charge="VIP", plan="daddy")
    a = db.execute("select v4_request_call(1)").fetchone()[0]
    b = db.execute("select v4_request_call(1)").fetchone()[0]
    assert a["allowed"] and a["created"] and not b["created"] and a["id"] == b["id"]


def test_lifetime_channel_plus_monthly_vip_downgrades_when_vip_ends(db):
    register(db)
    pay(db, charge="old-lifetime", plan="forever", days=36500)
    vip = pay(db, charge="vip", plan="daddy")
    assert vip["user"]["subscription_tier"] == "daddy"
    assert (
        datetime.fromisoformat(vip["user"]["premium_until"])
        .astimezone(timezone.utc)
        .year
        == 2099
    )
    db.execute(
        "update access_grants set ends_at=now()-interval '1 second' where user_id=1 and tier='daddy'"
    )
    u = db.execute("select v4_sync_access(1)").fetchone()[0]
    assert (
        u["is_paid"]
        and u["subscription_tier"] == "forever"
        and u["calls_until"] is None
    )


def test_notification_setting_cannot_disable_access_revocation(db):
    register(db)
    db.execute(
        "insert into automation_jobs(user_id,job_type,scheduled_at,dedupe_key) values(1,'v4_revoke',now(),'revoke'),(1,'v4_daily',now(),'daily')"
    )
    rows = db.execute("select job_type from v4_claim_jobs('one',5,false)").fetchall()
    assert rows == [("v4_revoke",)]


def test_refund_commissions_excluded_without_deleting_financial_history(db):
    db.execute(
        "insert into traffic_partners(telegram_user_id,code,display_name) values(888,'partner','Partner')"
    )
    register(db, ref="partner")
    pay(db)
    before = db.execute("select v4_partners()").fetchone()[0]
    assert before[0]["earned"] == 30
    db.execute("select v4_refund(1,'charge1')")
    after = db.execute("select v4_partners()").fetchone()[0]
    assert after[0]["earned"] == 0 and after[0]["purchases"] == 0
    assert db.execute("select count(*) from traffic_commissions").fetchone()[0] == 1
