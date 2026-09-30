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
        "uk": ("{name}ти загубився?) Підпишись на мій канал і натисни «Я підписався» — тоді пущу далі 💕",),
        "ru": ("{name}ты потерялся?) Подпишись на мой канал и нажми «Я подписался» — тогда пущу дальше 💕",),
        "en": ("{name}did you get lost?) Join my channel and tap “I joined” — then I'll let you in 💕",),
        "de": ("{name}bist du verloren gegangen?) Tritt meinem Kanal bei und tippe auf „Ich bin dabei“ 💕",),
        "fr": ("{name}tu t'es perdu ?) Rejoins mon canal et appuie sur « J'ai rejoint » 💕",),
        "es": ("{name}¿te perdiste?) Únete a mi canal y pulsa « Ya me uní » 💕",),
    },
    "offer_12h": {
        "uk": (
            "{name}ти так і не вибрав формат 👀 Якщо хочеш просто приват — бери перший. Якщо хочеш ще й писати мені — другий 💕",
            "{name}бачила, ти дивився приват, але так і не зайшов) Якщо не знаєш, що обрати — напиши мені, підкажу.",
        ),
        "ru": (
            "{name}ты так и не выбрал формат 👀 Если хочешь просто приват — бери первый. Если хочешь ещё и писать мне — второй 💕",
            "{name}видела, ты смотрел приват, но так и не зашёл) Если не знаешь, что выбрать — напиши мне, подскажу.",
        ),
        "en": (
            "{name}you still haven't picked one 👀 If you only want the private channel, take the first option. If you want to message me too, take the second 💕",
            "{name}I saw you checking the private options but you didn't join) If you're unsure, message me and I'll help you choose.",
        ),
        "de": ("{name}du hast noch nichts gewählt 👀 Nur privater Kanal = erste Option; mit Chat = zweite 💕",),
        "fr": ("{name}tu n'as toujours rien choisi 👀 Canal privé seulement = première formule ; avec chat = deuxième 💕",),
        "es": ("{name}todavía no elegiste 👀 Solo canal privado = primera opción; con chat = segunda 💕",),
    },
    "offer_48h": {
        "uk": ("Залишу кнопку тут)) Якщо ще хочеш зайти в приват — вона нижче 💕",),
        "ru": ("Оставлю кнопку тут)) Если ещё хочешь зайти в приват — она ниже 💕",),
        "en": ("I'll leave the button here)) If you still want the private channel, it's below 💕",),
        "de": ("Ich lasse den Button einfach hier)) Wenn du noch privat rein willst, ist er unten 💕",),
        "fr": ("Je laisse simplement le bouton ici)) Si tu veux toujours le privé, il est en dessous 💕",),
        "es": ("Dejo el botón aquí)) Si todavía quieres entrar al privado, está abajo 💕",),
    },
    "offer_daily": {
        "uk": (
            "{name}нагадую про приват, раптом учора просто не дійшли руки 👀 Кнопка нижче.",
            "{name}якщо приват ще цікавий — залишаю доступ до вибору нижче 💕",
            "{name}ти ще можеш зайти) Якщо актуально — обери формат нижче.",
            "{name}коротко нагадую про приват 👀 Якщо хочеш — усе ще можна зайти.",
        ),
        "ru": (
            "{name}напоминаю про приват, вдруг вчера просто руки не дошли 👀 Кнопка ниже.",
            "{name}если приват ещё интересен — оставляю выбор ниже 💕",
            "{name}ты ещё можешь зайти) Если актуально — выбери формат ниже.",
            "{name}коротко напомню про приват 👀 Если хочешь — всё ещё можно зайти.",
        ),
        "en": (
            "{name}quick reminder about the private channel in case yesterday just got busy 👀 The button is below.",
            "{name}if you're still interested, I left the private options below 💕",
            "{name}you can still join) If you want to, choose a format below.",
            "{name}just a quick private-channel reminder 👀 You can still join below.",
        ),
        "de": (
            "{name}kleine Erinnerung an den privaten Kanal, falls du gestern einfach keine Zeit hattest 👀 Der Button ist unten.",
            "{name}wenn du noch Interesse hast, findest du die Optionen unten 💕",
            "{name}du kannst noch reinkommen) Wenn du willst, wähle unten eine Option.",
            "{name}nur eine kurze Erinnerung 👀 Der private Zugang ist weiterhin verfügbar.",
        ),
        "fr": (
            "{name}petit rappel pour le canal privé, au cas où tu n'aurais simplement pas eu le temps hier 👀 Le bouton est en dessous.",
            "{name}si ça t'intéresse toujours, je te laisse les formules en dessous 💕",
            "{name}tu peux toujours entrer) Si tu veux, choisis une formule ci-dessous.",
            "{name}juste un petit rappel 👀 L'accès privé est toujours disponible.",
        ),
        "es": (
            "{name}un pequeño recordatorio del canal privado, por si ayer simplemente no tuviste tiempo 👀 El botón está abajo.",
            "{name}si todavía te interesa, te dejo las opciones abajo 💕",
            "{name}todavía puedes entrar) Si quieres, elige una opción abajo.",
            "{name}solo un recordatorio rápido 👀 El acceso privado sigue disponible.",
        ),
    },
    "checkout_30m": {
        "uk": ("{name}я бачила, ти вже майже зайшов, але оплата не завершилась 👀 Якщо щось не спрацювало — напиши мені.",),
        "ru": ("{name}я видела, ты уже почти зашёл, но оплата не завершилась 👀 Если что-то не сработало — напиши мне.",),
        "en": ("{name}I saw you almost joined, but the payment didn't finish 👀 If something went wrong, message me.",),
        "de": ("{name}du warst fast drin, aber die Zahlung wurde nicht beendet 👀 Wenn etwas nicht funktioniert hat, schreib mir.",),
        "fr": ("{name}j'ai vu que tu étais presque entré, mais le paiement n'a pas été terminé 👀 Si quelque chose a bloqué, écris-moi.",),
        "es": ("{name}vi que casi entraste, pero el pago no se terminó 👀 Si algo falló, escríbeme.",),
    },
    "checkout_6h": {
        "uk": ("{name}ти ж майже дійшов до кінця 😅 Я залишила те саме посилання нижче, якщо ще хочеш зайти.",),
        "ru": ("{name}ты же почти дошёл до конца 😅 Я оставила ту же ссылку ниже, если ещё хочешь зайти.",),
        "en": ("{name}you were almost done 😅 I left the same payment link below in case you still want to join.",),
        "de": ("{name}du warst fast fertig 😅 Ich habe denselben Zahlungslink unten gelassen, falls du noch rein möchtest.",),
        "fr": ("{name}tu avais presque fini 😅 J'ai laissé le même lien de paiement en dessous si tu veux toujours entrer.",),
        "es": ("{name}casi habías terminado 😅 Dejé el mismo enlace de pago abajo por si todavía quieres entrar.",),
    },
    "checkout_23h": {
        "uk": ("{name}ще маленьке нагадування: це посилання на оплату стане неактуальним приблизно за годину. Якщо хотів зайти — краще не відкладати 👀",),
        "ru": ("{name}ещё маленькое напоминание: эта ссылка на оплату станет неактуальной примерно через час. Если хотел зайти — лучше не откладывать 👀",),
        "en": ("{name}one small reminder: this payment link expires in about an hour. If you still wanted to join, don't leave it too late 👀",),
        "de": ("{name}kleine Erinnerung: Dieser Zahlungslink läuft in ungefähr einer Stunde ab. Wenn du noch rein willst, warte besser nicht zu lange 👀",),
        "fr": ("{name}petit rappel : ce lien de paiement expire dans environ une heure. Si tu veux toujours entrer, n'attends pas trop 👀",),
        "es": ("{name}un pequeño recordatorio: este enlace de pago caduca en aproximadamente una hora. Si todavía quieres entrar, no lo dejes para más tarde 👀",),
    },
    "checkout_daily": {
        "uk": (
            "{name}учорашнє посилання вже закрилось. Якщо ще хочеш зайти — можу відкрити нову оплату нижче 💕",
            "{name}якщо приват ще актуальний — натисни нижче, і бот відкриє нову оплату 👀",
            "{name}нагадую на всякий випадок) Якщо ще хочеш зайти — нове посилання можна відкрити кнопкою нижче.",
            "{name}ти ще можеш зайти в приват 💕 Натисни нижче — створиться нова оплата.",
        ),
        "ru": (
            "{name}вчерашняя ссылка уже закрылась. Если ещё хочешь зайти — новую оплату можно открыть ниже 💕",
            "{name}если приват ещё актуален — нажми ниже, и бот откроет новую оплату 👀",
            "{name}напоминаю на всякий случай) Если ещё хочешь зайти — новую ссылку можно открыть кнопкой ниже.",
            "{name}ты ещё можешь зайти в приват 💕 Нажми ниже — создастся новая оплата.",
        ),
        "en": (
            "{name}yesterday's payment link has expired. If you still want to join, you can open a fresh one below 💕",
            "{name}if the private channel is still on your mind, tap below and the bot will open a new payment 👀",
            "{name}just a reminder in case you still want in) You can open a fresh payment link below.",
            "{name}you can still join the private channel 💕 Tap below to create a new payment.",
        ),
        "de": (
            "{name}der gestrige Zahlungslink ist abgelaufen. Wenn du noch rein willst, kannst du unten einen neuen öffnen 💕",
            "{name}wenn der private Kanal noch interessant ist, tippe unten und der Bot öffnet eine neue Zahlung 👀",
            "{name}nur zur Erinnerung) Wenn du noch rein willst, kannst du unten einen neuen Zahlungslink öffnen.",
            "{name}du kannst noch in den privaten Kanal 💕 Tippe unten für eine neue Zahlung.",
        ),
        "fr": (
            "{name}le lien de paiement d'hier a expiré. Si tu veux toujours entrer, tu peux en ouvrir un nouveau ci-dessous 💕",
            "{name}si le privé t'intéresse toujours, appuie ci-dessous et le bot ouvrira un nouveau paiement 👀",
            "{name}petit rappel au cas où) Si tu veux toujours entrer, tu peux ouvrir un nouveau lien de paiement ci-dessous.",
            "{name}tu peux toujours rejoindre le canal privé 💕 Appuie ci-dessous pour créer un nouveau paiement.",
        ),
        "es": (
            "{name}el enlace de pago de ayer ya caducó. Si todavía quieres entrar, puedes abrir uno nuevo abajo 💕",
            "{name}si el privado todavía te interesa, pulsa abajo y el bot abrirá un pago nuevo 👀",
            "{name}solo un recordatorio por si todavía quieres entrar) Puedes abrir un enlace de pago nuevo abajo.",
            "{name}todavía puedes entrar al canal privado 💕 Pulsa abajo para crear un pago nuevo.",
        ),
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
