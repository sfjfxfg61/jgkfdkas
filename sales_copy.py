from __future__ import annotations

import hashlib


def _first_name(name: str | None) -> str:
    value = (name or "").strip()
    if not value or value in {"-", ".", "?", "None"}:
        return ""
    return value[:40]


def _stable_pick(items: tuple[str, ...], seed: str) -> str:
    if not items:
        return ""
    digest = hashlib.sha256(seed.encode("utf-8", "ignore")).digest()
    return items[int.from_bytes(digest[:4], "big") % len(items)]


QUICK_REPLIES: dict[str, dict[str, tuple[str, ...]]] = {
    "private": {
        "uk": (
            "Ну зайдеш — побачиш)) Там я викладаю більше, ніж у відкритому каналі 🤭",
            "Так, зайдеш та побачиш все)) Я ж не можу одразу весь приват розповісти 🙈",
            "У приваті цікавіше) Не буду псувати тобі сюрприз 🤭",
        ),
        "ru": (
            "Ну зайдёшь — увидишь)) Там я выкладываю больше, чем в открытом канале 🤭",
            "Зайдёшь и сам всё увидишь)) Не могу же я сразу весь приват рассказать 🙈",
            "В привате интереснее) Не буду тебе весь сюрприз портить 🤭",
        ),
        "en": (
            "You'll see when you join)) I post more there than in the public channel 🤭",
            "Join and you'll see for yourself)) I'm not giving away the whole private channel now 🙈",
        ),
        "de": ("Komm rein, dann siehst du es)) Privat poste ich einfach mehr als öffentlich 🤭",),
        "fr": ("Entre et tu verras)) Je poste simplement plus dans le privé que sur le canal public 🤭",),
        "es": ("Entra y lo verás)) En privado publico más que en el canal público 🤭",),
    },
    "content": {
        "uk": (
            "Котик, усе буде, я жінка працьовита, не підведу)",
            "Контент буде поповнюватися) Я не збираюся закидати приват після оплати 🤭",
            "Та буде що подивитися)) І нове теж буду додавати 💕",
        ),
        "ru": (
            "Котик, всё будет, я женщина работящая, не подведу)",
            "Контент будет пополняться) Я не собираюсь забрасывать приват после оплаты 🤭",
            "Будет что посмотреть)) И новое тоже буду добавлять 💕",
        ),
        "en": (
            "There'll be plenty to see)) And I'll keep adding new stuff too 💕",
            "I'm not planning to abandon the private channel after you join)) I'll keep it active 🤭",
        ),
        "de": ("Da kommt noch mehr)) Ich werde den privaten Kanal weiter aktiv halten 💕",),
        "fr": ("Il y aura de quoi voir)) Et je continuerai à ajouter du nouveau 💕",),
        "es": ("Habrá bastante que ver)) Y seguiré añadiendo cosas nuevas 💕",),
    },
    "expensive": {
        "uk": (
            "Дешевші варіанти знайти можна, звісно) Але я не хочу робити приват «аби був». Якщо заходиш до мене — хочу, щоб воно того вартувало.",
            "Розумію) Тому й зробила кілька форматів. Якщо не потрібен чат — бери просто приват, він найдоступніший.",
        ),
        "ru": (
            "Дешевле варианты найти можно, конечно) Но я не хочу делать приват «лишь бы был». Если заходишь ко мне — хочу, чтобы оно того стоило.",
            "Понимаю) Поэтому и сделала несколько форматов. Если чат не нужен — бери просто приват, он самый доступный.",
        ),
        "en": (
            "I get it) That's why I made a few options. If you don't need chat, the private-channel plan is the simplest one.",
            "Sure, there are cheaper channels around) I just don't want mine to feel empty after you join.",
        ),
        "de": ("Verstehe ich) Deshalb gibt es mehrere Optionen. Wenn du keinen Chat brauchst, nimm einfach den privaten Kanal.",),
        "fr": ("Je comprends) C'est pour ça qu'il y a plusieurs formules. Si tu n'as pas besoin du chat, prends simplement le canal privé.",),
        "es": ("Lo entiendo) Por eso hay varias opciones. Si no necesitas chat, el canal privado es la opción más sencilla.",),
    },
    "buy": {
        "uk": ("Натисни «Приват» → обери формат → оплати Stars. Після оплати бот одразу відкриє тобі доступ)",),
        "ru": ("Нажми «Приват» → выбери формат → оплати Stars. После оплаты бот сразу откроет тебе доступ)",),
        "en": ("Tap Private → choose a format → pay with Stars. The bot unlocks your access right after payment)",),
        "de": ("Tippe auf Privat → wähle ein Format → bezahle mit Stars. Danach wird dein Zugang direkt freigeschaltet)",),
        "fr": ("Appuie sur Privé → choisis une formule → paie en Stars. L'accès s'ouvre juste après le paiement)",),
        "es": ("Pulsa Privado → elige una opción → paga con Stars. El acceso se abre justo después del pago)",),
    },
    "later": {
        "uk": (
            "Добре, не буду тиснути) Якщо захочеш — ти знаєш, де мене знайти 💕",
            "Та без проблем) Дозрієш — заходь 🤭",
        ),
        "ru": (
            "Хорошо, давить не буду) Захочешь — ты знаешь, где меня найти 💕",
            "Да без проблем) Созреешь — заходи 🤭",
        ),
        "en": ("No pressure) If you want it later, you know where to find me 💕",),
        "de": ("Kein Druck) Wenn du später willst, weißt du ja, wo du mich findest 💕",),
        "fr": ("Pas de pression) Si tu veux plus tard, tu sais où me trouver 💕",),
        "es": ("Sin presión) Si luego te apetece, ya sabes dónde encontrarme 💕",),
    },
}


FOLLOWUPS: dict[str, dict[str, tuple[str, ...]]] = {
    "gate_6h": {
        "uk": ("Щоб продовжити, підпишись на відкритий канал і натисни «Я підписався» нижче 💕",),
        "ru": ("Чтобы продолжить, подпишись на открытый канал и нажми «Я подписался» ниже 💕",),
        "en": ("To continue, join the public channel and tap “I joined” below 💕",),
        "de": ("Um weiterzumachen, tritt dem öffentlichen Kanal bei und tippe unten auf „Ich bin dabei“ 💕",),
        "fr": ("Pour continuer, rejoins le canal public puis appuie sur « J'ai rejoint » ci-dessous 💕",),
        "es": ("Para continuar, únete al canal público y pulsa « Ya me uní » abajo 💕",),
    },
    "cold_6h": {
        "uk": ("Якщо хотів повернутися — кнопка нижче 👀",),
        "ru": ("Если хотел вернуться — кнопка ниже 👀",),
        "en": ("If you meant to come back, the button is below 👀",),
        "de": ("Falls du zurückkommen wolltest, ist der Button unten 👀",),
        "fr": ("Si tu voulais revenir, le bouton est ci-dessous 👀",),
        "es": ("Si querías volver, el botón está abajo 👀",),
    },
    "cold_24h": {
        "uk": ("Якщо хотів повернутися — залишила кнопку нижче 👀 Якщо ні, усе ок)",),
        "ru": ("Если хотел вернуться — оставила кнопку ниже 👀 Если нет, всё ок)",),
        "en": ("If you meant to come back, I left the button below 👀 If not, no worries)",),
        "de": ("Falls du noch zurückkommen wolltest, ist der Button unten 👀 Wenn nicht, kein Problem)",),
        "fr": ("Si tu voulais revenir, je laisse le bouton ci-dessous 👀 Sinon, aucun souci)",),
        "es": ("Si querías volver, dejé el botón abajo 👀 Si no, no pasa nada)",),
    },
    "cold_daily": {
        "uk": ("Якщо доступ ще цікавий — кнопка нижче. Якщо ні, більше не турбуватиму 💕",),
        "ru": ("Если доступ ещё интересен — кнопка ниже. Если нет, больше не буду отвлекать 💕",),
        "en": ("If access is still relevant, the button is below. If not, I won't keep reminding you 💕",),
        "de": ("Wenn der Zugang noch interessant ist, ist der Button unten. Sonst erinnere ich dich nicht weiter 💕",),
        "fr": ("Si l'accès t'intéresse encore, le bouton est ci-dessous. Sinon, je n'insisterai pas 💕",),
        "es": ("Si el acceso todavía te interesa, el botón está abajo. Si no, no insistiré 💕",),
    },
    "offer_3h": {
        "uk": ("Якщо вагаєшся між форматами — я б почала з каналу + чату ⭐ Якщо питання в ціні або Stars, просто напиши мені.",),
        "ru": ("Если выбираешь между форматами — я бы начала с канала + чата ⭐ Если вопрос в цене или Stars, просто напиши мне.",),
        "en": ("If you're choosing between the plans, I'd start with Channel + Chat ⭐ If the price or Stars are the issue, just message me.",),
        "de": ("Wenn du zwischen den Tarifen wählst, würde ich mit Kanal + Chat starten ⭐ Bei Fragen zu Preis oder Stars schreib mir einfach.",),
        "fr": ("Si tu hésites entre les formules, je commencerais par Canal + chat ⭐ Si le prix ou les Stars posent question, écris-moi.",),
        "es": ("Si estás eligiendo entre los planes, yo empezaría con Canal + chat ⭐ Si el precio o las Stars te frenan, escríbeme.",),
    },
    "offer_12h": {
        "uk": ("Ще вирішуєш? Якщо питання в ціні, Stars або оплаті — напиши мені. Тарифи залишила нижче 💕",),
        "ru": ("Ещё решаешь? Если вопрос в цене, Stars или оплате — напиши мне. Тарифы оставила ниже 💕",),
        "en": ("Still deciding? If the price, Stars or payment is unclear, message me. I left the plans below 💕",),
        "de": ("Noch unsicher? Wenn Preis, Stars oder Zahlung unklar sind, schreib mir. Die Tarife sind unten 💕",),
        "fr": ("Tu hésites encore ? Si le prix, les Stars ou le paiement ne sont pas clairs, écris-moi. Les formules sont ci-dessous 💕",),
        "es": ("¿Aún lo estás pensando? Si el precio, las Stars o el pago no están claros, escríbeme. Dejé los planes abajo 💕",),
    },
    "offer_48h": {
        "uk": ("Залишу вибір тарифів тут. Якщо є питання — просто напиши 💕",),
        "ru": ("Оставлю выбор тарифов тут. Если есть вопрос — просто напиши 💕",),
        "en": ("I'll leave the plans here. If you have a question, just message me 💕",),
        "de": ("Ich lasse die Tarife hier. Wenn du eine Frage hast, schreib mir einfach 💕",),
        "fr": ("Je laisse les formules ici. Si tu as une question, écris-moi 💕",),
        "es": ("Dejo los planes aquí. Si tienes alguna pregunta, escríbeme 💕",),
    },
    "offer_daily": {
        "uk": ("Якщо тарифи ще актуальні — вони нижче. Якщо ні, більше не нагадуватиму 💕",),
        "ru": ("Если тарифы ещё актуальны — они ниже. Если нет, больше не буду напоминать 💕",),
        "en": ("If the plans are still relevant, they're below. If not, I won't keep reminding you 💕",),
        "de": ("Wenn die Tarife noch relevant sind, findest du sie unten. Sonst erinnere ich dich nicht weiter 💕",),
        "fr": ("Si les formules t'intéressent encore, elles sont ci-dessous. Sinon, je n'insisterai pas 💕",),
        "es": ("Si los planes todavía te interesan, están abajo. Si no, no insistiré 💕",),
    },
    "checkout_5m": {
        "uk": ("Оплата ще не завершилась. Якщо просто відволікся — можеш повернутися кнопкою нижче.",),
        "ru": ("Оплата ещё не завершилась. Если просто отвлёкся — можешь вернуться кнопкой ниже.",),
        "en": ("The payment hasn't completed yet. If you just got distracted, you can return with the button below.",),
        "de": ("Die Zahlung ist noch nicht abgeschlossen. Falls du nur abgelenkt warst, kannst du unten zurückkehren.",),
        "fr": ("Le paiement n'est pas encore terminé. Si tu as été interrompu, tu peux reprendre ci-dessous.",),
        "es": ("El pago aún no se completó. Si te distrajiste, puedes volver con el botón de abajo.",),
    },
    "checkout_10m": {
        "uk": ("Схоже, оплата не завершилась. Якщо Telegram не показав потрібний пакет Stars або щось зависло — напиши мені, допоможу. Кнопка оплати нижче 💕",),
        "ru": ("Похоже, оплата не завершилась. Если Telegram не показал нужный пакет Stars или что-то зависло — напиши мне, помогу. Кнопка оплаты ниже 💕",),
        "en": ("Looks like the payment didn't finish. If Telegram didn't show the right Stars pack or something got stuck, message me and I'll help. The payment button is below 💕",),
        "de": ("Die Zahlung scheint nicht abgeschlossen zu sein. Wenn Telegram das passende Stars-Paket nicht zeigt oder etwas hängt, schreib mir. Der Zahlungsbutton ist unten 💕",),
        "fr": ("Le paiement semble ne pas s'être terminé. Si Telegram n'affiche pas le bon pack de Stars ou si quelque chose bloque, écris-moi. Le bouton est ci-dessous 💕",),
        "es": ("Parece que el pago no terminó. Si Telegram no mostró el paquete de Stars adecuado o algo se quedó bloqueado, escríbeme. El botón está abajo 💕",),
    },
    "checkout_30m": {
        "uk": ("Оплата не завершилась. Якщо Telegram показав помилку або незрозуміло зі Stars — напиши мені, допоможу. Повторити можна нижче 💕",),
        "ru": ("Оплата не завершилась. Если Telegram показал ошибку или непонятно со Stars — напиши мне, помогу. Повторить можно ниже 💕",),
        "en": ("The payment didn't complete. If Telegram showed an error or Stars were confusing, message me and I'll help. You can retry below 💕",),
        "de": ("Die Zahlung wurde nicht abgeschlossen. Wenn Telegram einen Fehler gezeigt hat oder Stars unklar sind, schreib mir. Unten kannst du es erneut versuchen 💕",),
        "fr": ("Le paiement n'a pas abouti. Si Telegram a affiché une erreur ou si les Stars ne sont pas claires, écris-moi. Tu peux réessayer ci-dessous 💕",),
        "es": ("El pago no se completó. Si Telegram mostró un error o las Stars no quedaron claras, escríbeme. Puedes intentarlo de nuevo abajo 💕",),
    },
    "checkout_3h": {
        "uk": ("Якщо оплата ще актуальна — посилання нижче. Якщо щось не працює, напиши мені.",),
        "ru": ("Если оплата ещё актуальна — ссылка ниже. Если что-то не работает, напиши мне.",),
        "en": ("If the payment is still relevant, the link is below. If something isn't working, message me.",),
        "de": ("Wenn die Zahlung noch relevant ist, ist der Link unten. Bei Problemen schreib mir.",),
        "fr": ("Si le paiement est toujours d'actualité, le lien est ci-dessous. En cas de problème, écris-moi.",),
        "es": ("Si el pago sigue siendo relevante, el enlace está abajo. Si algo no funciona, escríbeme.",),
    },
    "checkout_12h": {
        "uk": ("Залишу останнє нагадування про цю оплату на сьогодні. Якщо доступ ще потрібен — кнопка нижче; якщо щось завадило оплатити, напиши мені 💕",),
        "ru": ("Оставлю последнее напоминание об этой оплате на сегодня. Если доступ ещё нужен — кнопка ниже; если что-то помешало оплатить, напиши мне 💕",),
        "en": ("One last reminder about this checkout today. If you still want access, the button is below; if something stopped the payment, message me 💕",),
        "de": ("Eine letzte Erinnerung zu dieser Zahlung für heute. Wenn du den Zugang noch möchtest, ist der Button unten; bei Problemen schreib mir 💕",),
        "fr": ("Un dernier rappel pour ce paiement aujourd'hui. Si tu veux toujours l'accès, le bouton est ci-dessous ; s'il y a eu un problème, écris-moi 💕",),
        "es": ("Un último recordatorio sobre este pago por hoy. Si todavía quieres acceso, el botón está abajo; si hubo algún problema, escríbeme 💕",),
    },
    "checkout_23h": {
        "uk": ("Це посилання скоро закінчиться. Якщо ще хочеш доступ — можеш завершити оплату нижче.",),
        "ru": ("Эта ссылка скоро закончится. Если ещё хочешь доступ — можешь завершить оплату ниже.",),
        "en": ("This payment link will expire soon. If you still want access, you can finish below.",),
        "de": ("Dieser Zahlungslink läuft bald ab. Wenn du den Zugang noch möchtest, kannst du unten abschließen.",),
        "fr": ("Ce lien de paiement expirera bientôt. Si tu veux toujours l'accès, tu peux terminer ci-dessous.",),
        "es": ("Este enlace de pago caducará pronto. Si todavía quieres acceso, puedes terminar abajo.",),
    },
    "buyer_checkin_10m": {
        "uk": ("Все відкрилося нормально після оплати? 💕 Якщо приват або чат не відкривається — напиши сюди, я перевірю.",),
        "ru": ("Всё нормально открылось после оплаты? 💕 Если приват или чат не открывается — напиши сюда, я проверю.",),
        "en": ("Did everything open correctly after payment? 💕 If the private channel or chat isn't working, message me here and I'll check it.",),
        "de": ("Hat nach der Zahlung alles funktioniert? 💕 Wenn der private Kanal oder Chat nicht aufgeht, schreib mir hier, dann prüfe ich es.",),
        "fr": ("Tout s'est bien ouvert après le paiement ? 💕 Si le canal privé ou le chat ne fonctionne pas, écris-moi ici et je vérifierai.",),
        "es": ("¿Se abrió todo bien después del pago? 💕 Si el canal privado o el chat no funcionan, escríbeme aquí y lo revisaré.",),
    },
    "checkout_daily": {
        "uk": ("Якщо доступ ще актуальний — нову оплату можна відкрити нижче. Якщо ні, більше не нагадуватиму.", "Якщо вирішиш повернутися пізніше — свіжа оплата відкривається кнопкою нижче."),
        "ru": ("Если доступ ещё актуален — новую оплату можно открыть ниже. Если нет, больше не буду напоминать.", "Если решишь вернуться позже — свежую оплату можно открыть кнопкой ниже."),
        "en": ("If access is still relevant, you can open a fresh payment below. If not, I won't keep reminding you.", "If you decide to come back later, you can open a fresh payment with the button below."),
        "de": ("Wenn der Zugang noch relevant ist, kannst du unten eine neue Zahlung öffnen. Sonst erinnere ich dich nicht weiter.", "Wenn du später zurückkommen möchtest, kannst du unten eine neue Zahlung öffnen."),
        "fr": ("Si l'accès t'intéresse encore, tu peux ouvrir un nouveau paiement ci-dessous. Sinon, je n'insisterai pas.", "Si tu reviens plus tard, tu pourras ouvrir un nouveau paiement avec le bouton ci-dessous."),
        "es": ("Si el acceso todavía te interesa, puedes abrir un pago nuevo abajo. Si no, no insistiré.", "Si decides volver más tarde, puedes abrir un pago nuevo con el botón de abajo."),
    },
}

def quick_reply(lang: str, kind: str, user_id: int, first_name: str | None = None) -> str:
    bank = QUICK_REPLIES.get(kind) or QUICK_REPLIES["later"]
    variants = bank.get(lang) or bank["en"]
    body = _stable_pick(variants, f"quick:{user_id}:{kind}")
    # Keep quick replies natural: don't force the name into every message.
    return body


def followup_text(
    lang: str,
    job_type: str,
    user_id: int,
    first_name: str | None = None,
    variant_seed: str | int | None = None,
) -> str:
    bank = FOLLOWUPS.get(job_type) or FOLLOWUPS["offer_48h"]
    variants = bank.get(lang) or bank["en"]
    body = _stable_pick(variants, f"followup:{user_id}:{job_type}:{variant_seed or ''}")
    name = _first_name(first_name)
    prefix = f"{name}, " if name else ""
    return body.format(name=prefix)
