import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from aiogram.types import Message, User, Chat, SuccessfulPayment, CallbackQuery
import handlers
import channel_access
import reliability
from reliability import Journal
from middlewares import SlidingWindowRateLimit
from database import SupabaseStore, job_lease
from config import settings
from monetization import make_payload, parse_payment_details, product_description


def msg(payment=False):
    data = dict(message_id=1,date=datetime.now(timezone.utc),chat=Chat(id=41,type='private'),from_user=User(id=41,is_bot=False,first_name='Test',language_code='en'))
    if payment:
        data['successful_payment']=SuccessfulPayment(currency='XTR',total_amount=250,invoice_payload=make_payload(41,'plus','global'),telegram_payment_charge_id='charge-1',provider_payment_charge_id='',is_recurring=True,is_first_recurring=True)
    else:data['text']='hello'
    return Message(**data)

@pytest.mark.asyncio
async def test_financial_message_bypasses_exhausted_limiter():
    limiter=SlidingWindowRateLimit(max_events=1)
    handler=AsyncMock()
    await limiter(handler,msg(),{})
    await limiter(handler,msg(True),{})
    assert handler.await_count==2

@pytest.mark.asyncio
async def test_failed_channel_ban_never_clears_membership(monkeypatch):
    monkeypatch.setattr(handlers,'_private_channel_id',AsyncMock(return_value=-1001))
    monkeypatch.setattr(handlers.store,'update_user',AsyncMock())
    bot=NS(ban_chat_member=AsyncMock(side_effect=RuntimeError('Telegram down')),unban_chat_member=AsyncMock())
    with pytest.raises(RuntimeError):await handlers.remove_channel_access(bot,41)
    handlers.store.update_user.assert_not_awaited()

@pytest.mark.asyncio
async def test_successful_channel_removal_clears_membership(monkeypatch):
    monkeypatch.setattr(handlers,'_private_channel_id',AsyncMock(return_value=-1001))
    monkeypatch.setattr(handlers.store,'update_user',AsyncMock())
    monkeypatch.setattr(handlers.store,'track_event',AsyncMock())
    bot=NS(ban_chat_member=AsyncMock(),unban_chat_member=AsyncMock())
    await handlers.remove_channel_access(bot,41)
    handlers.store.update_user.assert_awaited_once_with(41,channel_member=False)

@pytest.mark.asyncio
async def test_unknown_private_join_is_removed(monkeypatch):
    monkeypatch.setattr(handlers,'_private_channel_id',AsyncMock(return_value=-1001))
    monkeypatch.setattr(handlers.store,'get_user',AsyncMock(return_value=None))
    event=NS(chat=NS(id=-1001),old_chat_member=NS(status='left'),new_chat_member=NS(status='member',user=NS(id=41,is_bot=False)))
    bot=NS(ban_chat_member=AsyncMock(),unban_chat_member=AsyncMock())
    await handlers.private_channel_member_update(event,bot)
    bot.ban_chat_member.assert_awaited_once_with(-1001,41)

@pytest.mark.asyncio
async def test_paid_service_works_without_public_gate(monkeypatch):
    monkeypatch.setattr(handlers,'_public_membership',AsyncMock(side_effect=AssertionError('gate should not run')))
    user={'is_premium':True,'premium_until':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    assert await handlers._ensure_public_for_message(msg(),NS(),user)

@pytest.mark.asyncio
async def test_unpaid_join_request_is_declined(monkeypatch):
    monkeypatch.setattr(handlers,'_private_channel_id',AsyncMock(return_value=-1001))
    monkeypatch.setattr(handlers.store,'get_user',AsyncMock(return_value=None))
    bot=NS(approve_chat_join_request=AsyncMock(),decline_chat_join_request=AsyncMock())
    await handlers.paid_channel_join(NS(chat=NS(id=-1001),from_user=NS(id=41)),bot)
    bot.decline_chat_join_request.assert_awaited_once_with(-1001,41)
    bot.approve_chat_join_request.assert_not_awaited()

@pytest.mark.asyncio
async def test_paid_receipt_persisted_before_any_activation(monkeypatch,tmp_path):
    j=Journal(tmp_path)
    monkeypatch.setattr(handlers,'journal',j)
    async def fail(message,bot):
        assert len(j.pending('receipts'))==1
        raise RuntimeError('DB down')
    monkeypatch.setattr(handlers,'apply_paid_receipt',fail)
    with pytest.raises(RuntimeError):await handlers.successful_payment(msg(True),NS())
    j.close()
    reopened=Journal(tmp_path)
    assert reopened.pending('receipts')[0]['charge']=='charge-1'
    reopened.close()

@pytest.mark.asyncio
async def test_receipt_completed_only_after_success(monkeypatch,tmp_path):
    j=Journal(tmp_path);monkeypatch.setattr(handlers,'journal',j)
    monkeypatch.setattr(handlers,'apply_paid_receipt',AsyncMock())
    await handlers.successful_payment(msg(True),NS())
    assert j.pending('receipts')==[]
    j.close()

@pytest.mark.asyncio
async def test_admin_notice_retries_and_dedupes(monkeypatch,tmp_path):
    j=Journal(tmp_path);monkeypatch.setattr(reliability,'journal',j)
    monkeypatch.setattr(settings.__class__,'admin_id',99)
    bot=NS(send_message=AsyncMock(side_effect=RuntimeError('Telegram offline')))
    await reliability.notify_admin(bot,'paid:1','Payment')
    assert len(j.pending('notices'))==1
    bot.send_message=AsyncMock()
    await reliability.deliver_notices(bot)
    await reliability.notify_admin(bot,'paid:1','Payment')
    bot.send_message.assert_awaited_once()
    assert not j.pending('notices')
    j.close()

@pytest.mark.asyncio
async def test_every_new_checkout_click_has_own_notice(monkeypatch):
    monkeypatch.setattr(settings.__class__,'admin_id',99)
    notify=AsyncMock();monkeypatch.setattr(handlers,'notify_admin',notify)
    user=User(id=41,is_bot=False,first_name='Test')
    for cid in ('one','two'):
        await handlers._admin_payment_click(NS(),CallbackQuery(id=cid,from_user=user,chat_instance='x'),{},'pro',500)
    assert [c.args[1] for c in notify.await_args_list]==['checkout:one','checkout:two']

@pytest.mark.asyncio
async def test_lease_is_checked_on_retry_and_finish(monkeypatch):
    db=SupabaseStore();db._request=AsyncMock(return_value=[])
    token=job_lease.set(('worker-one','2026-10-10T10:00:00+00:00'))
    try:
        await db.retry_job(1,'error')
        await db.finish_job(1,'sent')
        for call in db._request.await_args_list:
            assert '&locked_by=eq.worker-one&locked_at=eq.' in call.args[1]
    finally:job_lease.reset(token)

@pytest.mark.asyncio
async def test_pending_reply_delete_is_bounded_by_send_start():
    db=SupabaseStore();db._request=AsyncMock(return_value=[])
    await db.clear_pending_reply(41,'2026-10-10T10:00:00+00:00')
    assert '&updated_at=lte.' in db._request.await_args.args[1]

@pytest.mark.asyncio
async def test_activation_has_no_optional_post_rpc_update(monkeypatch):
    db=SupabaseStore();db._request=AsyncMock(return_value={'duplicate':False});db.update_user=AsyncMock(side_effect=RuntimeError())
    result=await db.record_payment(41,'charge','payload',250,'plus','global',30,True)
    assert not result['duplicate']
    db.update_user.assert_not_awaited()

@pytest.mark.asyncio
async def test_call_list_requests_period_end_as_column():
    db=SupabaseStore();db._request=AsyncMock(return_value=[])
    await db.pending_calls()
    path=db._request.await_args.args[1]
    assert 'select=id,user_id,created_at,period_end&' in path
    assert '&period_end&' not in path

@pytest.mark.asyncio
async def test_private_sales_require_restrict_permission(monkeypatch):
    monkeypatch.setattr(channel_access,'channel_capabilities',AsyncMock(return_value=channel_access.ChannelCapabilities(resolvable=True,can_invite=True,can_restrict=False)))
    assert not await channel_access.private_access_available(NS())


def test_video_calls_localized_without_quota():
    for lang in ('ru','uk','en','de','fr','es'):
        desc=product_description(lang,'black')
        assert '20' not in desc
        assert desc

@pytest.mark.asyncio
async def test_database_read_failure_does_not_prevent_activation(monkeypatch,tmp_path):
    monkeypatch.setattr(handlers,'journal',Journal(tmp_path))
    monkeypatch.setattr(handlers.store,'get_user',AsyncMock(side_effect=RuntimeError('temporary read failure')))
    record=AsyncMock(return_value={'duplicate':False,'premium_until':'2030-01-01'})
    monkeypatch.setattr(handlers.store,'record_payment',record)
    monkeypatch.setattr(handlers.store,'cancel_jobs',AsyncMock())
    monkeypatch.setattr(handlers.store,'track_event',AsyncMock())
    monkeypatch.setattr(handlers.store,'latest_event',AsyncMock(return_value=None))
    monkeypatch.setattr(handlers.store,'schedule_job',AsyncMock())
    monkeypatch.setattr(handlers,'notify_admin',AsyncMock())
    monkeypatch.setattr(handlers,'_create_private_invite',AsyncMock(return_value='https://t.me/+test'))
    bot=NS(send_message=AsyncMock())
    await handlers.apply_paid_receipt(msg(True),bot)
    record.assert_awaited_once()
    bot.send_message.assert_awaited_once()
    handlers.journal.close()


def test_rotated_key_accepts_legacy_only_for_confirmed_receipts(monkeypatch):
    import hashlib,hmac
    old=make_payload(41,'plus','global')
    previous=settings.invoice_signing_key
    monkeypatch.setattr(settings.__class__,'invoice_signing_key','new-secret')
    monkeypatch.setattr(settings.__class__,'legacy_invoice_signing_key',previous)
    assert parse_payment_details(old,41) is None
    assert parse_payment_details(old,41,allow_expired=True) is not None
    parts=old.split(':');parts[4]='1';body=':'.join(parts[:-1]);parts[-1]=hmac.new(previous.encode(),body.encode(),hashlib.sha256).hexdigest()[:20]
    assert parse_payment_details(':'.join(parts),41,allow_expired=True) is None

@pytest.mark.asyncio
async def test_canceled_lease_prevents_send(monkeypatch):
    import main
    monkeypatch.setattr(main.store,'job_is_current',AsyncMock(return_value=False))
    bot=NS(send_message=AsyncMock())
    assert not await main._send_job_message(bot,{'user_id':41,'job_type':'offer_3h'},41,'offer')
    bot.send_message.assert_not_awaited()
