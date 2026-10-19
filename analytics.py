"""Paginated, read-only reports on existing tables; no schema changes."""
from __future__ import annotations
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import html
from catalog import active


def stamp(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def ratio(n, d):
    return f'{100*n/d:.1f}%' if d else '—'


def breakdown(counter):
    return '\n'.join(f'• {html.escape(str(k))}: {v}' for k, v in counter.most_common()) or '—'


def chunks(lines):
    out, current = [], ''
    for line in '\n'.join(lines).splitlines():
        # Values in reports have no raw user message bodies.
        for offset in range(0, max(len(line), 1), 3000):
            part = line[offset:offset + 3000]
            if len(current) + len(part) + 1 > 3500:
                out.append(current); current = ''
            current += part + '\n'
    if current:
        out.append(current.rstrip())
    return out


async def detailed_report(store, cfg, now=None):
    now = now or datetime.now(timezone.utc)
    users, payments, events, messages, pending = await asyncio.gather(
        store.all_rows('users', '*', {'order': 'user_id.asc'}, None),
        store.all_rows('payments', '*', {'order': 'id.asc'}, None),
        store.all_rows('events', 'id,user_id,event,properties,created_at', {'order': 'id.asc'}, None),
        store.all_rows('messages', 'id,user_id,role,created_at', {'order': 'id.asc'}, None),
        store.all_rows('pending_replies', 'user_id,updated_at', {'order': 'user_id.asc'}, None),
    )
    # System/admin users are not customer metrics.
    users = [u for u in users if int(u['user_id']) != cfg.admin_id]
    ids = {int(u['user_id']) for u in users}
    payments = [p for p in payments if int(p['user_id']) in ids]
    events = [e for e in events if int(e['user_id']) in ids]
    messages = [m for m in messages if int(m['user_id']) in ids]
    pending = [p for p in pending if int(p['user_id']) in ids]
    valid = [p for p in payments if not p.get('refunded_at')]
    refunds = [p for p in payments if p.get('refunded_at')]
    stars = [p for p in valid if p.get('currency') == 'XTR']
    revenue = sum(int(p['amount']) for p in stars)
    buyers = {int(p['user_id']) for p in stars}
    enabled = [u for u in users if not u.get('blocked')]
    paying = [u for u in users if active(u)]
    lines = ['📊 <b>Victoria · подробная статистика</b>',
        f'Срез UTC: {now:%Y-%m-%d %H:%M}',
        '<b>Аудитория · вся база</b>',
        f'Всего: {len(users)} · доступны боту: {len(enabled)}',
        f'Заблокировали бота: {len(users)-len(enabled)} ({ratio(len(users)-len(enabled),len(users))})',
        f'Активный доступ: {len(paying)} · исторический is_paid: {sum(bool(u.get("is_paid")) for u in users)}',
        f'Активные тарифы:\n{breakdown(Counter(u.get("subscription_tier") or "unknown" for u in paying))}',
        f'Отмечены членами приватного канала: {sum(bool(u.get("channel_member")) for u in users)}',
        f'Отмечены членами публичного канала: {sum(bool(u.get("public_channel_member")) for u in users)}',
        f'Подтвердили регион: {sum(bool(u.get("region_confirmed")) for u in users)}',
        f'Ждут ответа: {len(pending)}',
        '<b>Деньги · журнал payments</b>',
        f'Действительных записей: {len(valid)} · XTR: {len(stars)} · покупателей XTR: {len(buyers)}',
        f'Выручка после исключения возвратов: {revenue} ⭐',
        f'Возвращено XTR: {sum(int(p["amount"]) for p in refunds if p.get("currency") == "XTR")} ⭐ · записей возврата: {len(refunds)}',
        f'ARPPU: {revenue/len(buyers):.1f} ⭐' if buyers else 'ARPPU: —',
        f'ARPU: {revenue/len(users):.1f} ⭐' if users else 'ARPU: —',
        f'Средний платёж: {revenue/len(stars):.1f} ⭐' if stars else 'Средний платёж: —',
        f'Покупатель / вся база: {ratio(len(buyers), len(users))}',
        f'Повторные покупатели: {sum(n>1 for n in Counter(p["user_id"] for p in stars).values())}',
        f'Выручка по тарифам:\n{breakdown(Counter(dict(sum_by(stars,"plan"))))}',
        f'Выручка по рынкам платежа:\n{breakdown(Counter(dict(sum_by(stars,"market"))))}',
        '<b>Сообщения · сохранённая история</b>',
        f'Пользовательских: {sum(m["role"]=="user" for m in messages)} · ответов: {sum(m["role"]=="assistant" for m in messages)}',
        f'Писали хотя бы раз: {len({m["user_id"] for m in messages if m["role"]=="user"})}',
    ]
    for days, label in [(1, '24 часа'), (7, '7 дней'), (30, '30 дней')]:
        cutoff = now - timedelta(days=days)
        recent = lambda r: cutoff <= stamp(r.get('created_at')) <= now
        ev = [e for e in events if recent(e)]
        ledger = [p for p in stars if recent(p)]
        ms = [m for m in messages if recent(m)]
        counts = Counter(e['event'] for e in ev)
        unique = lambda key: {e['user_id'] for e in ev if e['event'] == key}
        start, offer, checkout, paid = [unique(k) for k in
            ('simple_start', 'simple_offer_seen', 'simple_checkout', 'simple_payment_success')]
        lines += [f'<b>За {label}</b>',
            f'Новых пользователей: {sum(recent(u) for u in users)}',
            f'Последняя активность в периоде: {sum(cutoff <= stamp(u.get("last_active_at")) <= now for u in users)}',
            f'Платежей XTR: {len(ledger)} · покупателей: {len({p["user_id"] for p in ledger})} · {sum(int(p["amount"]) for p in ledger)} ⭐',
            f'Сообщений от пользователей: {sum(m["role"]=="user" for m in ms)} · ответов: {sum(m["role"]=="assistant" for m in ms)}',
            f'Писали: {len({m["user_id"] for m in ms if m["role"]=="user"})}',
            f'Напоминаний отправлено: {counts["simple_reminder_sent"]} · получателей: {len(unique("simple_reminder_sent"))}',
            f'Ошибок напоминаний: {counts["simple_reminder_failed"]} · блокировок при отправке: {counts["simple_reminder_blocked"]} · rate limit: {counts["simple_reminder_rate_limited"]}',
            f'Ссылок создано: {counts["simple_invite_created"]} · отправлено: {counts["simple_invite_sent"]} · ошибок создания: {counts["simple_invite_failed"]} · вступлений одобрено: {counts["simple_join_approved"]}',
            f'Воронка событий · уникальные: start {len(start)} → тарифы {len(offer)} → счёт {len(checkout)} → оплата {len(paid)}',
            f'Среди открывших тарифы: переход к счёту {ratio(len(offer & checkout),len(offer))}; оплата {ratio(len(offer & paid),len(offer))}',
            f'Среди получивших счёт: оплата {ratio(len(checkout & paid),len(checkout))}',
        ]
    lines += ['<b>Сегменты всей базы</b>', f'Языки:\n{breakdown(Counter(u.get("lang") or "unknown" for u in users))}',
        f'Рынки профилей:\n{breakdown(Counter(u.get("market") or "unknown" for u in users))}',
        f'Этапы продаж:\n{breakdown(Counter(u.get("sales_stage") or "unknown" for u in users))}',
        f'Источники первого запуска:\n{breakdown(Counter(str(u.get("ref") or "direct")[:100] for u in users))}',
        '<b>Ограничения измерения</b>',
        'События simple_* отражают новую версию. Старые записи events не приравниваются к новым этапам.',
        'Конверсии — пересечения пользователей в периоде, без доказательства порядка этапов; это не когортная воронка.',
        'Исторические флаги членства не заменяют проверку Telegram. Активность — по last_active_at, переписка — по messages.',
        'Старый доступ без записи payments сохраняется, но выручка для него неизвестна. Stars не равны выведенным деньгам.',
        'Все таблицы прочитаны с пагинацией без ограничения числа записей. Отчёт не является транзакционным снимком.',
    ]
    return chunks(lines)


def sum_by(payments, field):
    totals = Counter()
    for p in payments:
        totals[str(p.get(field) or 'unknown')[:100]] += int(p['amount'])
    return totals.items()
