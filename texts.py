# texts.py

# Сетка тарифов для разных ГЕО (в Telegram Stars)
# test: 7 дней, lifetime: навсегда (основной), vip: премиум-якорь (создает контраст цен)
TARIFF_PRICES = {
    "uk": {"test": 250, "lifetime": 400, "vip": 1200},
    "ru": {"test": 250, "lifetime": 400, "vip": 1200},
    "en": {"test": 600, "lifetime": 1000, "vip": 3000},
    "es": {"test": 450, "lifetime": 750, "vip": 2200},
    "fr": {"test": 600, "lifetime": 1000, "vip": 3000},
    "de": {"test": 700, "lifetime": 1200, "vip": 3500},
}

def get_tariff_price(lang: str, tier: str) -> int:
    """Безопасное и быстрое получение цены тарифа с фоллбеком на английский"""
    geos = TARIFF_PRICES.get(lang, TARIFF_PRICES["en"])
    return geos.get(tier, geos["lifetime"])

TEXTS = {
    "uk": {
        "welcome": (
            "Привіт, {name} 🤍\n\n"
            "Рада бачити тебе тут. Твій запит на вхід прийнято.\n\n"
            "Щоб активувати систему та підтвердити, що твій профіль є реальним, "
            "тобі необхідно зробити один простий крок:\n\n"
            "📢 <b>Підпишись на мій офіційний канал</b> із моїми думками та атмосферою, "
            "а потім натисни кнопку нижче. Це відкриє наступний етап 👇"
        ),
        "pub_btn": "📢 Приєднатися до каналу",
        "check_btn": "Я підписався, що далі? 🤍",
        "checking": (
            "⏳ <b>Аналіз профілю...</b>\n\n"
            "Зачекайте декілька секунд. Система перевіряє активність вашого акаунту "
            "та готує персональний доступ. Не вимикайте сповіщення."
        ),
        "trigger": (
            "<b>Перевірку пройдено. Доступ відкрито</b> 🤍\n\n"
            "Поки ти знайомишся з моїм публічним каналом, я хочу показати тобі дещо інше. "
            "У мене є повністю закритий, приватний простір.\n\n"
            "Там немає цензури, масок чи спроб подобатися усім. Тільки моє справжнє життя, "
            "особисті моменти та думки, які ніколи не з'являться на публіці.\n\n"
            "🔑 <i>Доступ туди обмежений. Я впускаю лише тих, хто відчуває мою енергетику.</i> "
            "Обери свій формат участі нижче 👇"
        ),
        "invoice_title": "Приватний простір ({tier_name})",
        "invoice_desc": "Доступ до закритих матеріалів без цензури за обраним тарифом.",
        "thanks": (
            "Дякую, що ти зі мною 🤍\n\n"
            "Твій персональний доступ активовано назавжди. "
            "Вхід у закритий простір знаходиться за посиланням нижче:"
        ),
        "push": (
            "⏳ <b>Твоє запрошення анулюється...</b>\n\n"
            "Я помітила, що ти зацікавився моїм приватним простором, але так і не наважився зробити крок. "
            "Можливо, це просто не твоє, і це нормально.\n\n"
            "Але май на увазі: через декілька годин це динамічне посилання буде видалено системою. "
            "Другої спроби потрапити туди та побачити мене без фільтрів не буде. Твій останній шанс 👇"
        ),
        "tier_test": "⏳ Тест-драйв (7 днів)",
        "tier_lifetime": "💎 Безліміт НАВЖИВНО",
        "tier_vip": "👑 VIP (Доступ + Особистий чат)",
        "select_tier_text": "🏷 <b>Оберіть формат доступу:</b>"
    },
    "ru": {
        "welcome": (
            "Привет, {name} 🤍\n\n"
            "Рада видеть тебя здесь. Твой запрос на вход принят.\n\n"
            "Чтобы активировать систему и подтвердить, что твой профиль реален, "
            "тебе необходимо сделать один простой шаг:\n\n"
            "📢 <b>Подпишись на мой официальный канал</b> с моими мыслями и атмосферой, "
            "а затем нажми кнопку ниже. Это откроет следующий этап 👇"
        ),
        "pub_btn": "📢 Присоединиться к каналу",
        "check_btn": "Я подписался, что дальше? 🤍",
        "checking": (
            "⏳ <b>Анализ профиля...</b>\n\n"
            "Подождите несколько секунд. Система проверяет активность вашего аккаунта "
            "и готовит персональный доступ. Не выключайте уведомления."
        ),
        "trigger": (
            "<b>Проверка пройдена. Доступ открыт</b> 🤍\n\n"
            "Пока ты знакомишься с моим публичным каналом, я хочу показать тебе кое-что другое. "
            "У меня есть полностью закрытое, приватное пространство.\n\n"
            "Там нет цензуры, масок или попыток нравиться всем. Только моя настоящая жизнь, "
            "личные моменты и мысли, которые никогда не появятся публично.\n\n"
            "🔑 <i>Доступ туда строго ограничен. Я впускаю только тех, кто чувствует мою энергетику.</i> "
            "Выбери свой формат участия ниже 👇"
        ),
        "invoice_title": "Приватное пространство ({tier_name})",
        "invoice_desc": "Доступ к закрытым материалам без цензуры по выбранному тарифу.",
        "thanks": (
            "Спасибо, что ты со мной 🤍\n\n"
            "Твой персональный доступ активирован навсегда. "
            "Вход в закрытое пространство находится по ссылке ниже:"
        ),
        "push": (
            "⏳ <b>Твоё приглашение аннулируется...</b>\n\n"
            "Я заметила, что ты заинтересовался моим приватным пространством, но так и не решился сделать шаг. "
            "Возможно, это просто не твоё, и это нормально.\n\n"
            "Но имей в виду: через несколько часов эта динамическая ссылка будет удалена системой. "
            "Второй попытки попасть туда и увидеть меня без фильтров уже не будет. Твой последний шанс 👇"
        ),
        "tier_test": "⏳ Тест-драйв (7 дней)",
        "tier_lifetime": "💎 Безлимит НАВСЕГДА",
        "tier_vip": "👑 VIP (Доступ + Личный чат)",
        "select_tier_text": "🏷 <b>Выберите формат доступа:</b>"
    },
    "en": {
        "welcome": (
            "Hey, {name} 🤍\n\n"
            "So glad to see you here. Your entry request has been received.\n\n"
            "To activate the system and verify that your profile is real, "
            "you need to complete one simple step:\n\n"
            "📢 <b>Subscribe to my official channel</b> with my thoughts and atmosphere, "
            "then click the button below. This will unlock the next stage 👇"
        ),
        "pub_btn": "📢 Join the Channel",
        "check_btn": "I'm subscribed, what's next? 🤍",
        "checking": (
            "⏳ <b>Analyzing profile...</b>\n\n"
            "Please wait a few seconds. The system is verifying your subscription "
            "and preparing your personal access. Keep notifications on."
        ),
        "trigger": (
            "<b>Verification successful. Access granted</b> 🤍\n\n"
            "While you are exploring my public channel, I want to show you something else. "
            "I have a completely private, hidden space.\n\n"
            "No censorship, no filters, and no trying to please everyone. Just my real life, "
            "personal moments, and raw thoughts that will never be shared publicly.\n\n"
            "🔑 <i>Only a select few are allowed inside.</i> Choose your access level below 👇"
        ),
        "invoice_title": "Private Space ({tier_name})",
        "invoice_desc": "Access to exclusive uncensored content based on your choice.",
        "thanks": (
            "Thank you for being with me 🤍\n\n"
            "Your personal access has been activated permanently. "
            "Enter your private space via the link below:"
        ),
        "push": (
            "⏳ <b>Your invitation is expiring...</b>\n\n"
            "I noticed you showed interest in my private space but hesitated to enter. "
            "Maybe it's just not your vibe, and that's totally fine.\n\n"
            "But keep in mind: in a few hours, this invitation link will be permanently deactivated. "
            "There won't be a second chance to see me unfiltered. Your final call 👇"
        ),
        "tier_test": "⏳ Trial Pass (7 Days)",
        "tier_lifetime": "💎 Lifetime Access",
        "tier_vip": "👑 VIP Access + Private Chat",
        "select_tier_text": "🏷 <b>Choose your access level:</b>"
    },
    "es": {
        "welcome": (
            "Hola, {name} 🤍\n\n"
            "Qué alegría verte aquí. Tu solicitud de entrada ha sido recibida.\n\n"
            "Para activar el sistema y verificar que tu perfil es real, "
            "debes completar un paso muy sencillo:\n\n"
            "📢 <b>Suscríbete a mi canal oficial</b> con mis pensamientos y vibra, "
            "luego haz clic en el botón de abajo. Esto desbloqueará la siguiente etapa 👇"
        ),
        "pub_btn": "📢 Unirse al Canal",
        "check_btn": "Ya me suscribí, ¿qué sigue? 🤍",
        "checking": (
            "⏳ <b>Analizando perfil...</b>\n\n"
            "Por favor, espera unos segundos. El sistema está verificando tu suscripción "
            "y preparando tu acceso personal. No apagues las notificaciones."
        ),
        "trigger": (
            "<b>Verificación exitosa. Acceso concedido</b> 🤍\n\n"
            "Mientras exploras mi canal público, quiero mostrarte algo diferente. "
            "Tengo un espacio completamente privado y oculto.\n\n"
            "Sin censura, sin filtros y sin intentar complacer a todos. Solo mi vida real, "
            "momentos personales y pensamientos puros que nunca compartiré en público.\n\n"
            "🔑 <i>El acceso es muy limitado. Solo dejo entrar a quienes sienten mi energía.</i> "
            "Elige tu nivel de acceso abajo 👇"
        ),
        "invoice_title": "Espacio Privado ({tier_name})",
        "invoice_desc": "Acceso a contenido exclusivo sin censura según el plan elegido.",
        "thanks": (
            "Gracias por estar conmigo 🤍\n\n"
            "Tu acceso personal ha sido activado para siempre. "
            "Entra a tu espacio privado a través del enlace de abajo:"
        ),
        "push": (
            "⏳ <b>Tu invitación está por expirar...</b>\n\n"
            "Noté que te interesó mi espacio privado, pero dudaste en entrar. "
            "Tal vez no sea tu estilo, y eso está totalmente bien.\n\n"
            "Pero ten en cuenta: en unas pocas horas, este enlace de invitación se desactivará. "
            "No habrá una segunda oportunidad para verme sin filtros. Tu última decisión 👇"
        ),
        "tier_test": "⏳ Pase de Prueba (7 Días)",
        "tier_lifetime": "💎 Acceso de por Vida",
        "tier_vip": "👑 Acceso VIP + Chat Privado",
        "select_tier_text": "🏷 <b>Elige tu nivel de acceso:</b>"
    },
    "fr": {
        "welcome": (
            "Salut, {name} 🤍\n\n"
            "Ravi de te voir ici. Ta demande d'accès a bien été reçue.\n\n"
            "Pour activer le système et prouver que ton profil est réel, "
            "tu dois accomplir une étape très simple :\n\n"
            "📢 <b>Abonne-toi à mon canal officiel</b> pour t'imprégner de mes pensées et de mon univers, "
            "puis clique sur le bouton ci-dessous. Cela débloquera la suite 👇"
        ),
        "pub_btn": "📢 Rejoindre le Canal",
        "check_btn": "Je suis abonné, et après ? 🤍",
        "checking": (
            "⏳ <b>Analyse du profil...</b>\n\n"
            "Veuillez patienter quelques secondes. Le système vérifie votre abonnement "
            "et prépare votre accès personnalisé. Restez connecté."
        ),
        "trigger": (
            "<b>Vérification réussie. Accès accordé</b> 🤍\n\n"
            "Pendant que tu découvres mon canal public, je veux te montrer autre chose. "
            "J'ai créé un espace entièrement privé et secret.\n\n"
            "Pas de censure, pas de filtres, et aucune envie de plaire à tout le monde. Juste ma vraie vie, "
            "mes moments intimes et mes pensées brutes qui ne seront jamais publiés ailleurs.\n\n"
            "🔑 <i>L'accès est très restreint. Je ne laisse entrer que ceux qui partagent ma vibe.</i> "
            "Choisis ton niveau d'accès ci-dessous 👇"
        ),
        "invoice_title": "Espace Privé ({tier_name})",
        "invoice_desc": "Accès au contenu exclusif sans censure selon le plan choisi.",
        "thanks": (
            "Merci d'être avec moi 🤍\n\n"
            "Ton accès personnel a été activé définitivement. "
            "Rejoins ton espace privé via le lien ci-dessous :"
        ),
        "push": (
            "⏳ <b>Ton invitation va expirer...</b>\n\n"
            "J'ai remarqué que tu t'intéressais à mon espace privé, mais que tu as hésité. "
            "Peut-être que ce n'est pas pour toi, et c'est tout à fait normal.\n\n"
            "Sache cependant que dans quelques heures, ce lien d'invitation sera désactivé. "
            "Il n'y aura pas de seconde chance pour me voir sans filtre. Ton dernier choix 👇"
        ),
        "tier_test": "⏳ Pass d'Essai (7 Jours)",
        "tier_lifetime": "💎 Accès à Vie",
        "tier_vip": "👑 Accès VIP + Chat Privé",
        "select_tier_text": "🏷 <b>Choisis ton niveau d'accès :</b>"
    },
    "de": {
        "welcome": (
            "Hallo, {name} 🤍\n\n"
            "Schön, dass du da bist. Deine Beitrittsanfrage wurde empfangen.\n\n"
            "Um das System zu aktivieren und zu bestätigen, dass dein Profil echt ist, "
            "musst du nur einen einfachen Schritt machen:\n\n"
            "📢 <b>Abonniere meinen offiziellen Kanal</b> mit meinen Gedanken und meiner Atmosphäre, "
            "und klicke dann auf den Button unten. Das schaltet den nächsten Schritt frei 👇"
        ),
        "pub_btn": "📢 Kanal beitreten",
        "check_btn": "Ich habe abonniert, was jetzt? 🤍",
        "checking": (
            "⏳ <b>Profil-Analyse...</b>\n\n"
            "Bitte warte einige Sekunden. Das System überprüft dein Abonnement "
            "und bereitet deinen persönlichen Zugang vor. Benachrichtigungen nicht ausschalten."
        ),
        "trigger": (
            "<b>Verifizierung erfolgreich. Zugang gewährt</b> 🤍\n\n"
            "Während du meinen öffentlichen Kanal erkundest, möchte ich dir etwas anderes zeigen. "
            "Ich habe einen völlig privaten, exklusiven Bereich.\n\n"
            "Ohne Zensur, ohne Filter und ohne den Versuch, allen zu gefallen. Nur mein echtes Leben, "
            "persönliche Momente und Gedanken, die niemals öffentlich geteilt werden.\n\n"
            "🔑 <i>Der Zugang ist streng limitiert. Nur für diejenigen, die meine Energie spüren.</i> "
            "Wähle jetzt deinen Zugang 👇"
        ),
        "invoice_title": "Privater Bereich ({tier_name})",
        "invoice_desc": "Zugang zu exklusiven, unzensierten Inhalten basierend auf deiner Wahl.",
        "thanks": (
            "Danke, dass du bei mir bist 🤍\n\n"
            "Dein persönlicher Zugang wurde dauerhaft freigeschaltet. "
            "Tritt deinem privaten Bereich über den Link unten bei:"
        ),
        "push": (
            "⏳ <b>Deine Einladung läuft ab...</b>\n\n"
            "Ich habe bemerkt, dass du Interesse an meinem privaten Bereich hattest, aber gezögert hast. "
            "Vielleicht ist es nicht dein Ding, und das ist völlig okay.\n\n"
            "Aber denke daran: In wenigen Stunden wird dieser Einladungslink dauerhaft deaktiviert. "
            "Es gibt keine zweite Chance, mich völlig ungefiltert zu sehen. Deine letzte Chance 👇"
        ),
        "tier_test": "⏳ Testzugang (7 Tage)",
        "tier_lifetime": "💎 Lebenslanger Zugang",
        "tier_vip": "👑 VIP-Zugang + Privater Chat",
        "select_tier_text": "🏷 <b>Wähle deine Zugangsstufe:</b>"
    }
}

def get_text(lang: str, key: str) -> str:
    """
    Умный и ультра-быстрый фоллбек.
    Если перевод для данного языка отсутствует, мгновенно отдает английскую версию.
    """
    locale = TEXTS.get(lang, TEXTS["en"])
    return locale.get(key, TEXTS["en"].get(key, ""))

def get_user_lang(language_code: str) -> str:
    """Определение языка пользователя с защитой от пустых значений"""
    if not language_code:
        return "en"
    clean_lang = language_code.lower()[:2]
    return clean_lang if clean_lang in TEXTS else "en"
