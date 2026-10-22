"""Small server-aggregated reports. No message/event history downloads."""

import html
import math
import time


def ratio(n, d):
    return f"{100 * n / d:.1f}%" if d else "—"


def chunks(lines):
    out = []
    current = ""
    for line in "\n".join(lines).splitlines():
        if len(current) + len(line) + 1 > 3500:
            out.append(current)
            current = ""
        current += line + "\n"
    if current:
        out.append(current.rstrip())
    return out


def wilson(k, n):
    if not n:
        return (0, 1)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    delta = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return center - delta, center + delta


def ab_result(rows):
    arms = {r["label"]: r for r in rows if r["kind"] == "ab"}
    if not all(x in arms for x in ("A", "B")):
        return "A/B: идёт сбор данных."
    a, b = arms["A"], arms["B"]
    # Cohort conversion is an indicator, not a claim of statistical significance.
    if min(a["users"], b["users"]) < 100 or min(a["buyers"], b["buyers"]) < 10:
        return "A/B: данных мало; победитель ещё не определён (минимум 100 человек и 10 покупателей в каждой группе)."
    ca, cb = wilson(a["buyers"], a["users"]), wilson(b["buyers"], b["users"])
    if ca[0] > cb[1]:
        winner = "A"
    elif cb[0] > ca[1]:
        winner = "B"
    else:
        return "A/B: убедимого различия пока нет (95% интервалы пересекаются)."
    return f"A/B: вариант {winner} показывает более высокую конверсию; проверь также Stars на пользователя и языковой состав."


_cache = {}


async def detailed_report(store, cfg, now=None):
    key = id(store)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < 30:
        d = cached[1]
    else:
        d = await store.rpc("v4_analytics", p_admin=cfg.admin_id)
        _cache[key] = (time.monotonic(), d)
    lines = [
        "📊 <b>VICTORIA — АНАЛИТИКА</b>",
        f"Пользователи: <b>{d['users']}</b> · новых за 7д: {d['new7']} · заблокировали: {d['blocked']}",
        f"Открыли тарифы: <b>{d['offers']}</b> → нажали оплату: <b>{d['clicks']}</b> → подтвердили checkout: <b>{d['checkouts']}</b>",
        f"Покупатели: <b>{d['buyers']}</b> · покупок: <b>{d['purchases']}</b>",
        f"Выручка: <b>{d['stars']} ⭐</b> · возвраты: {d['refunds']} ⭐",
        f"Конверсия в покупателя: {ratio(d['buyers'], d['users'])} · Stars/пользователь: {d['stars'] / max(d['users'], 1):.2f}",
        f"Сообщений: {d['messages']} · ответов: {d['replies']} · ждут ответа: {d['pending']}",
        f"Напоминаний: {d['reminders']}",
        "<b>Языки · язык первого входа</b>",
    ]
    for kind, title in [
        ("language", None),
        ("ab", "A/B · приветствие и оформление"),
        ("source", "Источники"),
        ("market", "Рынки"),
    ]:
        if title:
            lines.append("<b>" + title + "</b>")
        rows = sorted(
            (r for r in d["segments"] if r["kind"] == kind),
            key=lambda r: r["users"],
            reverse=True,
        )
        for r in rows[:30]:
            lines.append(
                f"{html.escape(r['label'])}: {r['users']} → {r['offers']} → {r['clicks']} → {r['buyers']} покупателей · "
                f"{r['purchases']} покупок · {r['stars']} ⭐ · {ratio(r['buyers'], r['users'])}"
            )
    lines += [
        ab_result(d["segments"]),
        "Период: вся сохранённая база. Языки/источники — когорты регистрации, выручка после возвратов. Старые неизвестные этапы не восстанавливаются догадками.",
        "Клики измеряются кнопками бота; прямые ссылки из старых сообщений видны только на этапе pre-checkout. Stars — валовая выручка, не чистая прибыль.",
    ]
    return chunks(lines)
