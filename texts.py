from __future__ import annotations


TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "access_requires_plan": "Для входа в закрытый канал сначала нужен активный доступ.",
        "payment_support": "Заявка по оплате передана в поддержку. Опиши проблему следующим сообщением.",
        "call_requires_plan": "Заявка на звонок доступна в личном тарифе.", "call_limit": "Две заявки на этот период уже использованы.", "call_requested": "Заявка получена. Я напишу, чтобы согласовать время.",
        "channel_join": "Подать заявку на вход в канал", "channel_unavailable": "Доступ в канал временно недоступен. Напиши в поддержку.",
        "region_prompt": "Выбери регион для отображения цен. Мы предложили вариант по языку Telegram. Выбор делается один раз при входе.",
        "region_confirm": "Подтвердить", "region_change": "Выбрать другой регион",
        "region_choose": "Выбери свой регион:", "region_already_set": "Регион уже выбран.",
        "region_first": "Сначала выбери регион в /start.",
        "welcome": "Привет, <b>{name}</b>. Я Вика. Просто напиши, что у тебя на уме — отвечу здесь.",
        "menu": "Напиши мне сообщение или выбери действие:",
        "premium": "Доступ",
        "public_channel": "Telegram-канал",
        "about_button": "Инфо",
        "about": (
            "<b>О сервисе</b>\n\nВика — виртуальный AI-собеседник. Ответы создаёт языковая модель, "
            "поэтому она может ошибаться. Сообщения сохраняются для истории и памяти. "
            "Сервис не выдаёт AI за человека и не заменяет близких или специалистов."
        ),
        "not_ready": "Нажми /start, и можно сразу общаться.",
        "ai_error": "Сейчас не получилось ответить. Попробуй ещё раз через минуту.",
        "premium_nudge": "Если хочешь больше сообщений и более сильную память — загляни в Premium ✨",
        "channel_nudge": "Кстати, в Telegram-канале есть ещё материалы и обновления 📢",
        "reminder_d1": "Как прошёл твой день? Можешь написать буквально пару слов — я подхвачу разговор.",
        "reminder_d3": "Давно не переписывались. Что нового произошло за эти дни?",
        "reminder_d7": "Если захочешь вернуться — просто напиши, что сейчас больше всего занимает мысли.",
    },
    "uk": {
        "access_requires_plan": "Для вступу до приватного каналу потрібен активний доступ.",
        "payment_support": "Запит щодо оплати передано підтримці. Опиши проблему наступним повідомленням.",
        "call_requires_plan": "Заявка на дзвінок доступна в особистому тарифі.", "call_limit": "Дві заявки на цей період вже використано.", "call_requested": "Заявку отримано. Я напишу, щоб узгодити час.",
        "channel_join": "Подати заявку на вступ до каналу", "channel_unavailable": "Доступ до каналу тимчасово недоступний. Напиши в підтримку.",
        "region_prompt": "Обери регіон для показу цін. Ми запропонували варіант за мовою Telegram. Вибір робиться один раз на початку.",
        "region_confirm": "Підтвердити", "region_change": "Обрати інший регіон",
        "region_choose": "Обери свій регіон:", "region_already_set": "Регіон уже обрано.",
        "region_first": "Спочатку обери регіон через /start.",
        "welcome": "Привіт, <b>{name}</b>. Я Віка. Просто напиши, що в тебе на думці — відповім тут.",
        "menu": "Напиши мені повідомлення або обери дію:",
        "premium": "Доступ",
        "public_channel": "Telegram-канал",
        "about_button": "Інфо",
        "about": (
            "<b>Про сервіс</b>\n\nВіка — віртуальний AI-співрозмовник. Відповіді створює мовна модель, "
            "тому вона може помилятися. Повідомлення зберігаються для історії та пам'яті. "
            "Сервіс не видає AI за людину й не замінює близьких або фахівців."
        ),
        "not_ready": "Натисни /start — і можна одразу спілкуватися.",
        "ai_error": "Зараз не вдалося відповісти. Спробуй ще раз за хвилину.",
        "premium_nudge": "Якщо хочеш більше повідомлень і сильнішу пам'ять — зазирни в Premium ✨",
        "channel_nudge": "До речі, у Telegram-каналі є ще матеріали й оновлення 📢",
        "reminder_d1": "Як минув твій день? Можеш написати буквально кілька слів — я підхоплю розмову.",
        "reminder_d3": "Давно не переписувалися. Що нового сталося за ці дні?",
        "reminder_d7": "Якщо захочеш повернутися — просто напиши, що зараз найбільше займає думки.",
    },
    "en": {
        "access_requires_plan": "You need an active plan to join the private channel.",
        "payment_support": "Your payment request reached support. Describe the issue in your next message.",
        "call_requires_plan": "Call requests are available with the personal plan.", "call_limit": "Both call requests for this period have been used.", "call_requested": "Request received. I'll message you to arrange a time.",
        "channel_join": "Request access to the channel", "channel_unavailable": "Channel access is temporarily unavailable. Contact support.",
        "region_prompt": "Choose a region to show prices. We suggested one based on your Telegram language. This choice is made once when you start.",
        "region_confirm": "Confirm", "region_change": "Choose another region",
        "region_choose": "Choose your region:", "region_already_set": "Your region is already set.",
        "region_first": "Choose a region with /start first.",
        "welcome": "Hi, <b>{name}</b>. I'm Vika. Just tell me what's on your mind and I'll reply here.",
        "menu": "Send me a message or choose an option:",
        "premium": "Access",
        "public_channel": "Telegram channel",
        "about_button": "Info",
        "about": (
            "<b>About the service</b>\n\nVika is a virtual AI conversation assistant. Replies are generated by a "
            "language model and may be wrong. Messages are stored for conversation history and memory. "
            "The service does not present AI as human or replace people or qualified professionals."
        ),
        "not_ready": "Tap /start and you can chat right away.",
        "ai_error": "I couldn't reply just now. Please try again in a minute.",
        "premium_nudge": "Want more messages and stronger memory? Take a look at Premium ✨",
        "channel_nudge": "By the way, the Telegram channel has more content and updates 📢",
        "reminder_d1": "How did your day go? A few words are enough — I'll pick up the conversation.",
        "reminder_d3": "It's been a few days. What's new with you?",
        "reminder_d7": "Whenever you want to return, just tell me what's been on your mind lately.",
    },
    "es": {
        "access_requires_plan": "Necesitas un plan activo para acceder al canal privado.",
        "payment_support": "Tu solicitud llegó a soporte. Describe el problema en el siguiente mensaje.",
        "call_requires_plan": "Las llamadas están disponibles con el plan personal.", "call_limit": "Ya usaste las dos solicitudes de este período.", "call_requested": "Solicitud recibida. Te escribiré para acordar la hora.",
        "channel_join": "Solicitar acceso al canal", "channel_unavailable": "El acceso al canal no está disponible ahora. Contacta con soporte.",
        "region_prompt": "Elige una región para ver los precios. Sugerimos una según tu idioma de Telegram. Solo se elige al empezar.",
        "region_confirm": "Confirmar", "region_change": "Elegir otra región",
        "region_choose": "Elige tu región:", "region_already_set": "La región ya está elegida.",
        "region_first": "Primero elige una región con /start.",
        "welcome": "Hola, <b>{name}</b>. Soy Vika. Cuéntame qué tienes en mente y te responderé aquí.",
        "menu": "Envíame un mensaje o elige una opción:",
        "premium": "Acceso",
        "public_channel": "Canal de Telegram",
        "about_button": "Información",
        "about": (
            "<b>Sobre el servicio</b>\n\nVika es una asistente virtual de conversación con IA. Las respuestas "
            "las genera un modelo de lenguaje y pueden contener errores. Los mensajes se guardan para el historial "
            "y la memoria. El servicio no presenta la IA como una persona ni sustituye a personas o profesionales."
        ),
        "not_ready": "Pulsa /start y podrás conversar de inmediato.",
        "ai_error": "No pude responder ahora. Inténtalo de nuevo en un minuto.",
        "premium_nudge": "¿Quieres más mensajes y mejor memoria? Descubre Premium ✨",
        "channel_nudge": "Por cierto, el canal de Telegram tiene más contenido y novedades 📢",
        "reminder_d1": "¿Cómo fue tu día? Bastan unas palabras para retomar la conversación.",
        "reminder_d3": "Han pasado unos días. ¿Qué hay de nuevo?",
        "reminder_d7": "Cuando quieras volver, cuéntame qué has tenido en mente últimamente.",
    },
    "de": {
        "access_requires_plan": "Für den privaten Kanal brauchst du einen aktiven Tarif.",
        "payment_support": "Deine Zahlungsanfrage ist beim Support. Beschreibe das Problem in der nächsten Nachricht.",
        "call_requires_plan": "Anrufe sind im persönlichen Tarif verfügbar.", "call_limit": "Die zwei Anfragen für diesen Zeitraum sind verbraucht.", "call_requested": "Anfrage erhalten. Ich schreibe dir, um einen Termin zu vereinbaren.",
        "channel_join": "Kanalzugang anfragen", "channel_unavailable": "Kanalzugang ist derzeit nicht verfügbar. Kontaktiere den Support.",
        "region_prompt": "Wähle eine Region für die Preise. Wir haben eine anhand deiner Telegram-Sprache vorgeschlagen. Diese Wahl erfolgt einmal beim Start.",
        "region_confirm": "Bestätigen", "region_change": "Andere Region wählen",
        "region_choose": "Wähle deine Region:", "region_already_set": "Die Region wurde bereits gewählt.",
        "region_first": "Wähle zuerst eine Region mit /start.",
        "welcome": "Hallo, <b>{name}</b>. Ich bin Vika. Schreib einfach, was dich beschäftigt — ich antworte hier.",
        "menu": "Schreib mir eine Nachricht oder wähle eine Option:",
        "premium": "Zugang",
        "public_channel": "Telegram-Kanal",
        "about_button": "Info",
        "about": (
            "<b>Über den Dienst</b>\n\nVika ist eine virtuelle KI-Gesprächsassistentin. Antworten werden von "
            "einem Sprachmodell erzeugt und können falsch sein. Nachrichten werden für Verlauf und Erinnerung "
            "gespeichert. Der Dienst gibt KI nicht als Menschen aus und ersetzt keine Menschen oder Fachpersonen."
        ),
        "not_ready": "Tippe auf /start, dann kannst du sofort schreiben.",
        "ai_error": "Ich konnte gerade nicht antworten. Versuche es in einer Minute erneut.",
        "premium_nudge": "Mehr Nachrichten und stärkere Erinnerung? Schau dir Premium an ✨",
        "channel_nudge": "Im Telegram-Kanal gibt es übrigens weitere Inhalte und Updates 📢",
        "reminder_d1": "Wie war dein Tag? Ein paar Worte reichen, um das Gespräch fortzusetzen.",
        "reminder_d3": "Ein paar Tage sind vergangen. Was gibt es Neues?",
        "reminder_d7": "Wenn du zurückkommen möchtest, schreib einfach, was dich zuletzt beschäftigt hat.",
    },
    "fr": {
        "access_requires_plan": "Un forfait actif est nécessaire pour accéder au canal privé.",
        "payment_support": "Ta demande a été transmise à l'assistance. Décris le problème dans le prochain message.",
        "call_requires_plan": "Les appels sont inclus dans la formule personnelle.", "call_limit": "Les deux demandes pour cette période ont été utilisées.", "call_requested": "Demande reçue. Je t'écrirai pour convenir d'une heure.",
        "channel_join": "Demander l'accès au canal", "channel_unavailable": "L'accès au canal est temporairement indisponible. Contacte l'assistance.",
        "region_prompt": "Choisis une région pour afficher les prix. Nous en avons suggéré une selon ta langue Telegram. Ce choix se fait une seule fois au départ.",
        "region_confirm": "Confirmer", "region_change": "Choisir une autre région",
        "region_choose": "Choisis ta région :", "region_already_set": "La région est déjà choisie.",
        "region_first": "Choisis d'abord une région avec /start.",
        "welcome": "Bonjour, <b>{name}</b>. Je suis Vika. Écris simplement ce que tu as en tête, je répondrai ici.",
        "menu": "Envoie-moi un message ou choisis une option :",
        "premium": "Accès",
        "public_channel": "Canal Telegram",
        "about_button": "Infos",
        "about": (
            "<b>À propos du service</b>\n\nVika est une assistante virtuelle de conversation basée sur l'IA. "
            "Les réponses sont générées par un modèle de langage et peuvent être erronées. Les messages sont "
            "conservés pour l'historique et la mémoire. Le service ne présente pas l'IA comme une personne et "
            "ne remplace ni les proches ni les professionnels."
        ),
        "not_ready": "Appuie sur /start et tu pourras discuter immédiatement.",
        "ai_error": "Je n'ai pas pu répondre. Réessaie dans une minute.",
        "premium_nudge": "Tu veux plus de messages et une meilleure mémoire ? Découvre Premium ✨",
        "channel_nudge": "Au fait, le canal Telegram contient d'autres contenus et actualités 📢",
        "reminder_d1": "Comment s'est passée ta journée ? Quelques mots suffisent pour reprendre la conversation.",
        "reminder_d3": "Quelques jours ont passé. Quoi de neuf ?",
        "reminder_d7": "Quand tu voudras revenir, écris simplement ce qui t'occupe l'esprit en ce moment.",
    },
}


# Short, specific prompts with a single action. No false urgency or guilt framing.
REMINDER_COPY = {
    "ru": (
        "Ответить", "Можно начать с одного сообщения: о чём тебе сейчас интересно поговорить?",
        "Если удобнее, просто напиши тему — начнём с неё.",
        "Чат открыт, когда понадобится. Можешь написать одно слово или вопрос.",
        "Мы остановились на твоём сообщении. Хочешь продолжить ту тему или начать новую?",
        "Можно вернуться с одной короткой мыслью. Что бы ты хотел обсудить сейчас?",
        "Если захочешь продолжить разговор, напиши здесь в любое время.",
    ),
    "uk": (
        "Відповісти", "Можна почати з одного повідомлення: про що тобі зараз цікаво поговорити?",
        "Якщо зручніше, просто напиши тему — почнемо з неї.",
        "Чат відкритий, коли знадобиться. Можеш написати одне слово або запитання.",
        "Ми зупинилися на твоєму повідомленні. Продовжимо цю тему чи почнемо нову?",
        "Можна повернутися з однією короткою думкою. Що ти хотів би обговорити зараз?",
        "Якщо захочеш продовжити розмову, напиши тут будь-коли.",
    ),
    "en": (
        "Reply", "You can start with one message: what would you like to talk about?",
        "If it's easier, send just a topic and we'll start there.",
        "This chat is here when you need it. A question or a single word is enough.",
        "We left off at your last message. Continue that topic or start a new one?",
        "One short thought is enough to pick things up. What is on your mind now?",
        "You can continue this conversation here whenever you like.",
    ),
    "es": (
        "Responder", "Puedes empezar con un mensaje: ¿de qué te gustaría hablar?",
        "Si te resulta más fácil, escribe solo un tema y empezamos por ahí.",
        "Este chat sigue aquí cuando lo necesites. Basta con una pregunta o una palabra.",
        "Nos quedamos en tu último mensaje. ¿Seguimos con ese tema o empezamos otro?",
        "Una idea breve basta para retomar. ¿Qué te gustaría comentar ahora?",
        "Cuando quieras continuar, puedes escribir aquí.",
    ),
    "de": (
        "Antworten", "Du kannst mit einer Nachricht beginnen: Worüber möchtest du sprechen?",
        "Wenn es einfacher ist, schreib nur ein Thema, und wir fangen dort an.",
        "Dieser Chat ist da, wenn du ihn brauchst. Ein Wort oder eine Frage reicht.",
        "Wir waren bei deiner letzten Nachricht stehen geblieben. Dieses Thema oder ein neues?",
        "Ein kurzer Gedanke reicht, um weiterzumachen. Was beschäftigt dich gerade?",
        "Wenn du weiterreden möchtest, kannst du jederzeit hier schreiben.",
    ),
    "fr": (
        "Répondre", "Tu peux commencer par un message : de quoi aimerais-tu parler ?",
        "Si c'est plus simple, écris juste un sujet et on commencera par là.",
        "Ce chat reste disponible quand tu en as besoin. Un mot ou une question suffit.",
        "On s'était arrêté à ton dernier message. On reprend ce sujet ou un autre ?",
        "Une courte idée suffit pour reprendre. De quoi aimerais-tu parler maintenant ?",
        "Tu peux reprendre cette conversation ici quand tu veux.",
    ),
}
for locale, copy in REMINDER_COPY.items():
    TEXTS[locale].update(dict(zip(
        ("reminder_cta", "reminder_new_d1", "reminder_new_d3", "reminder_new_d7",
         "reminder_chat_d1", "reminder_chat_d3", "reminder_chat_d7"), copy,
    )))


def t(lang: str, key: str, **values: object) -> str:
    locale = TEXTS.get(lang, TEXTS["en"])
    template = locale.get(key, TEXTS["en"].get(key, key))
    return template.format(**values)
