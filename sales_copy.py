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
    "cold_6h": {
        "uk": (
            "{name}ти кудись зник) Я тебе ще чекаю 💕 Якщо захочеш зайти — кнопка нижче.",
            "{name}котик, ти загубився? 👀 Я тут, якщо що. Можеш зайти нижче.",
        ),
        "ru": (
            "{name}ты куда-то пропал) Я тебя ещё жду 💕 Если захочешь зайти — кнопка ниже.",
            "{name}котик, ты потерялся? 👀 Я тут, если что. Можешь зайти ниже.",
        ),
        "en": (
            "{name}you disappeared on me) I'm still here 💕 If you want to come back, the button is below.",
            "{name}did you get lost? 👀 I'm still here if you want to check it out.",
        ),
        "de": (
            "{name}du bist irgendwie verschwunden) Ich bin noch da 💕 Wenn du zurückkommen willst, ist der Button unten.",
            "{name}hast du dich verlaufen? 👀 Ich bin noch hier, wenn du reinschauen willst.",
        ),
        "fr": (
            "{name}tu as un peu disparu) Je suis toujours là 💕 Si tu veux revenir, le bouton est en dessous.",
            "{name}tu t'es perdu ? 👀 Je suis toujours là si tu veux jeter un œil.",
        ),
        "es": (
            "{name}desapareciste un poco) Sigo aquí 💕 Si quieres volver, el botón está abajo.",
            "{name}¿te perdiste? 👀 Sigo aquí por si quieres echar un vistazo.",
        ),
    },
    "cold_24h": {
        "uk": (
            "{name}нагадую про себе 👀 Ти так і не заглянув. Якщо цікаво — я залишила кнопку нижче.",
            "{name}я тебе ще не забула)) Якщо хотів зайти — усе нижче 💕",
        ),
        "ru": (
            "{name}напоминаю о себе 👀 Ты так и не заглянул. Если интересно — я оставила кнопку ниже.",
            "{name}я тебя ещё не забыла)) Если хотел зайти — всё ниже 💕",
        ),
        "en": (
            "{name}just reminding you I'm here 👀 You never checked it out. I left the button below.",
            "{name}I didn't forget about you)) If you still wanted to join, everything is below 💕",
        ),
        "de": (
            "{name}nur eine kleine Erinnerung 👀 Du hast noch gar nicht reingeschaut. Der Button ist unten.",
            "{name}ich habe dich noch nicht vergessen)) Wenn du noch rein willst, ist alles unten 💕",
        ),
        "fr": (
            "{name}petit rappel 👀 Tu n'as toujours pas regardé. Je laisse le bouton en dessous.",
            "{name}je ne t'ai pas oublié)) Si tu voulais toujours entrer, tout est en dessous 💕",
        ),
        "es": (
            "{name}un pequeño recordatorio 👀 Todavía no has entrado a mirar. Te dejo el botón abajo.",
            "{name}no me he olvidado de ti)) Si todavía querías entrar, está todo abajo 💕",
        ),
    },
    "cold_daily": {
        "uk": (
            "{name}котик, я тебе ще чекаю 👀 Якщо сьогодні захочеш заглянути — кнопка нижче.",
            "{name}я тут)) Раптом сьогодні саме той день, коли ти все ж зайдеш 💕",
            "{name}коротке нагадування від мене 👀 Якщо цікаво — можеш зайти нижче.",
            "{name}не загублю тебе так легко)) Я все ще тут 💕",
        ),
        "ru": (
            "{name}котик, я тебя ещё жду 👀 Если сегодня захочешь заглянуть — кнопка ниже.",
            "{name}я тут)) Вдруг сегодня тот самый день, когда ты всё-таки зайдёшь 💕",
            "{name}короткое напоминание от меня 👀 Если интересно — можешь зайти ниже.",
            "{name}не потеряю тебя так легко)) Я всё ещё тут 💕",
        ),
        "en": (
            "{name}I'm still waiting for you 👀 If you feel like checking it out today, the button is below.",
            "{name}I'm still here)) Maybe today's the day you finally take a look 💕",
            "{name}a tiny reminder from me 👀 If you're curious, you can open it below.",
            "{name}not letting you disappear that easily)) I'm still here 💕",
        ),
        "de": (
            "{name}ich warte noch auf dich 👀 Wenn du heute reinschauen willst, ist der Button unten.",
            "{name}ich bin noch da)) Vielleicht schaust du heute endlich mal rein 💕",
            "{name}eine kleine Erinnerung von mir 👀 Wenn du neugierig bist, kannst du unten öffnen.",
            "{name}so leicht lasse ich dich nicht verschwinden)) Ich bin noch da 💕",
        ),
        "fr": (
            "{name}je t'attends toujours 👀 Si tu veux regarder aujourd'hui, le bouton est en dessous.",
            "{name}je suis toujours là)) Peut-être qu'aujourd'hui tu viendras enfin voir 💕",
            "{name}un petit rappel de ma part 👀 Si tu es curieux, tu peux ouvrir ci-dessous.",
            "{name}je ne te laisse pas disparaître si facilement)) Je suis toujours là 💕",
        ),
        "es": (
            "{name}todavía te estoy esperando 👀 Si hoy quieres echar un vistazo, el botón está abajo.",
            "{name}sigo aquí)) Quizá hoy sea el día en que por fin entres a mirar 💕",
            "{name}un pequeño recordatorio mío 👀 Si tienes curiosidad, puedes abrirlo abajo.",
            "{name}no voy a dejar que desaparezcas tan fácil)) Sigo aquí 💕",
        ),
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
    "checkout_5m": {
        "uk": (
            "{name}бачу, оплата не завершилась 👀 Якщо просто відволікся — залишаю кнопку тут.",
            "{name}ти був уже за крок від доступу) Якщо передумав — ок, а якщо просто не встиг, кнопка нижче.",
        ),
        "ru": (
            "{name}вижу, оплата не завершилась 👀 Если просто отвлёкся — оставляю кнопку тут.",
            "{name}ты был уже в шаге от доступа) Если передумал — ок, а если просто не успел, кнопка ниже.",
        ),
        "en": (
            "{name}I can see the payment wasn't completed 👀 If you just got distracted, the button is still below.",
            "{name}you were one step away from access) If you still want it, the button is below.",
        ),
        "de": (
            "{name}die Zahlung wurde noch nicht abgeschlossen 👀 Falls du nur abgelenkt warst, ist der Button noch unten.",
            "{name}du warst nur noch einen Schritt vom Zugang entfernt) Wenn du noch willst, ist der Button unten.",
        ),
        "fr": (
            "{name}le paiement n'a pas été terminé 👀 Si tu as simplement été interrompu, le bouton est toujours en dessous.",
            "{name}tu étais à un pas de l'accès) Si tu le veux toujours, le bouton est en dessous.",
        ),
        "es": (
            "{name}el pago no se terminó 👀 Si simplemente te distrajiste, el botón sigue abajo.",
            "{name}estabas a un paso del acceso) Si todavía lo quieres, el botón está abajo.",
        ),
    },
    "checkout_30m": {
        "uk": (
            "{name}залишу оплату тут ще раз, раптом не дійшли руки 👀",
            "{name}якщо доступ ще актуальний — та сама оплата все ще відкрита нижче.",
        ),
        "ru": (
            "{name}оставлю оплату тут ещё раз, вдруг просто руки не дошли 👀",
            "{name}если доступ ещё актуален — та же оплата всё ещё открыта ниже.",
        ),
        "en": (
            "{name}I'll leave the payment here once more in case you simply didn't get back to it 👀",
            "{name}if access is still relevant, the same payment is still open below.",
        ),
        "de": (
            "{name}ich lasse die Zahlung noch einmal hier, falls du einfach nicht dazu gekommen bist 👀",
            "{name}wenn du den Zugang noch möchtest, ist dieselbe Zahlung unten noch offen.",
        ),
        "fr": (
            "{name}je laisse le paiement ici une nouvelle fois, au cas où tu n'aurais simplement pas eu le temps 👀",
            "{name}si l'accès t'intéresse toujours, le même paiement est encore disponible ci-dessous.",
        ),
        "es": (
            "{name}dejo el pago aquí una vez más por si simplemente no tuviste tiempo 👀",
            "{name}si el acceso todavía te interesa, el mismo pago sigue disponible abajo.",
        ),
    },
    "checkout_3h": {
        "uk": (
            "{name}нагадую про доступ) Посилання ще працює, залишаю його нижче.",
            "{name}якщо ще хотів зайти — посилання на оплату поки активне 👀",
        ),
        "ru": (
            "{name}напомню про доступ) Ссылка ещё работает, оставляю её ниже.",
            "{name}если ещё хотел зайти — ссылка на оплату пока активна 👀",
        ),
        "en": (
            "{name}quick access reminder) The payment link is still active, so I'm leaving it below.",
            "{name}if you still wanted to join, the payment link is still active 👀",
        ),
        "de": (
            "{name}kurze Erinnerung an den Zugang) Der Zahlungslink ist noch aktiv und bleibt unten.",
            "{name}wenn du noch rein wolltest, ist der Zahlungslink weiterhin aktiv 👀",
        ),
        "fr": (
            "{name}petit rappel pour l'accès) Le lien de paiement est toujours actif, je le laisse ci-dessous.",
            "{name}si tu voulais toujours entrer, le lien de paiement est encore actif 👀",
        ),
        "es": (
            "{name}un recordatorio rápido del acceso) El enlace de pago sigue activo y lo dejo abajo.",
            "{name}si todavía querías entrar, el enlace de pago sigue activo 👀",
        ),
    },
    "checkout_12h": {
        "uk": (
            "{name}посилання ще активне. Якщо доступ потрібен — можеш завершити оплату нижче.",
            "{name}ще не пізно) Залишаю ту саму оплату нижче, якщо це ще актуально.",
        ),
        "ru": (
            "{name}ссылка ещё активна. Если доступ нужен — можешь завершить оплату ниже.",
            "{name}ещё не поздно) Оставляю ту же оплату ниже, если это всё ещё актуально.",
        ),
        "en": (
            "{name}the link is still active. If you still want access, you can finish the payment below.",
            "{name}it's not too late) I'm leaving the same payment below if it's still relevant.",
        ),
        "de": (
            "{name}der Link ist noch aktiv. Wenn du den Zugang noch möchtest, kannst du die Zahlung unten abschließen.",
            "{name}es ist noch nicht zu spät) Dieselbe Zahlung ist unten noch verfügbar.",
        ),
        "fr": (
            "{name}le lien est toujours actif. Si tu veux encore l'accès, tu peux terminer le paiement ci-dessous.",
            "{name}il n'est pas trop tard) Le même paiement est encore disponible ci-dessous.",
        ),
        "es": (
            "{name}el enlace sigue activo. Si todavía quieres acceso, puedes completar el pago abajo.",
            "{name}todavía estás a tiempo) El mismo pago sigue disponible abajo.",
        ),
    },
    "checkout_23h": {
        "uk": (
            "{name}це посилання на оплату стане неактуальним приблизно за годину. Якщо ще хотів зайти — краще завершити зараз 👀",
        ),
        "ru": (
            "{name}эта ссылка на оплату станет неактуальной примерно через час. Если ещё хотел зайти — лучше завершить сейчас 👀",
        ),
        "en": (
            "{name}this payment link will expire in about an hour. If you still want access, it's better to finish it now 👀",
        ),
        "de": (
            "{name}dieser Zahlungslink läuft in ungefähr einer Stunde ab. Wenn du den Zugang noch möchtest, schließe ihn besser jetzt ab 👀",
        ),
        "fr": (
            "{name}ce lien de paiement expire dans environ une heure. Si tu veux toujours l'accès, mieux vaut terminer maintenant 👀",
        ),
        "es": (
            "{name}este enlace de pago caduca en aproximadamente una hora. Si todavía quieres acceso, es mejor terminar ahora 👀",
        ),
    },
    "checkout_daily": {
        "uk": (
            "{name}якщо доступ ще актуальний — нову оплату можна відкрити кнопкою нижче 👀",
            "{name}коротко нагадую про доступ) Якщо ще хочеш зайти — обери оплату нижче.",
            "{name}залишаю кнопку тут на випадок, якщо вирішиш повернутися.",
            "{name}доступ усе ще можна оформити — кнопка нижче.",
        ),
        "ru": (
            "{name}если доступ ещё актуален — новую оплату можно открыть кнопкой ниже 👀",
            "{name}коротко напомню про доступ) Если ещё хочешь зайти — открой оплату ниже.",
            "{name}оставляю кнопку тут на случай, если решишь вернуться.",
            "{name}доступ всё ещё можно оформить — кнопка ниже.",
        ),
        "en": (
            "{name}if access is still relevant, you can open a fresh payment with the button below 👀",
            "{name}quick access reminder) If you still want to join, open a fresh payment below.",
            "{name}I'm leaving the button here in case you decide to come back.",
            "{name}access is still available — the button is below.",
        ),
        "de": (
            "{name}wenn du den Zugang noch möchtest, kannst du unten eine neue Zahlung öffnen 👀",
            "{name}kurze Erinnerung) Wenn du noch rein willst, öffne unten eine neue Zahlung.",
            "{name}ich lasse den Button hier, falls du später zurückkommen möchtest.",
            "{name}der Zugang ist weiterhin verfügbar — der Button ist unten.",
        ),
        "fr": (
            "{name}si l'accès t'intéresse toujours, tu peux ouvrir un nouveau paiement avec le bouton ci-dessous 👀",
            "{name}petit rappel) Si tu veux toujours entrer, ouvre un nouveau paiement ci-dessous.",
            "{name}je laisse le bouton ici au cas où tu déciderais de revenir.",
            "{name}l'accès est toujours disponible — le bouton est en dessous.",
        ),
        "es": (
            "{name}si el acceso todavía te interesa, puedes abrir un pago nuevo con el botón de abajo 👀",
            "{name}un recordatorio rápido) Si todavía quieres entrar, abre un pago nuevo abajo.",
            "{name}dejo el botón aquí por si decides volver más tarde.",
            "{name}el acceso sigue disponible — el botón está abajo.",
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
