PRICES = {
    "uk": 400,
    "ru": 400,
    "es": 750,
    "fr": 1000,
    "de": 1200,
    "en": 1000,
}

def get_price(lang: str) -> int:
    return PRICES.get(lang, 1000)

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
            "Якщо ти готовий побачити мене справжньою — твої двері відчинені прямо зараз."
        ),
        "buy_btn": "✨ Зазирнути у приватний простір",
        "invoice_title": "Приватний простір",
        "invoice_desc": "Повний пожиттєвий доступ до закритих матеріалів без цензури.",
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
        )
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
            "Если ты готов увидеть меня настоящую — твоя дверь открыта прямо сейчас."
        ),
        "buy_btn": "✨ Заглянуть в приватное пространство",
        "invoice_title": "Приватное пространство",
        "invoice_desc": "Полный пожизненный доступ к закрытым материалам без цензуры.",
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
        )
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
            "🔑 <i>Only a select few are allowed inside.</i> If you feel my energy and "
            "want to see the real me — your door is open right now."
        ),
        "buy_btn": "✨ Enter Private Space",
        "invoice_title": "Private Space",
        "invoice_desc": "Full lifetime access to exclusive uncensored content.",
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
        )
    },
    "de": {
        "welcome": (
            "Hallo, {name} 🤍\n\n"
            "Schön, dass du da bist. Deine Beitrittsanfrage wurde empfangen.\n\n"
            "Um das System zu aktivieren und zu bestätigen, dass dein Profil echt ist, "
            "musst du einen einfachen Schritt abschließen:\n\n"
            "📢 <b>Abonniere meinen offiziellen Kanal</b> mit meinen Gedanken und meiner Ästhetik, "
            "und klicke dann auf die Schaltfläche unten 👇"
        ),
        "pub_btn": "📢 Kanal beitreten",
        "check_btn": "Ich bin beigetreten, was jetzt? 🤍",
        "checking": (
            "⏳ <b>Profil wird analysiert...</b>\n\n"
            "Bitte warte einen Moment. Das System überprüft dein Abonnement "
            "und bereitet deinen persönlichen Zugang vor."
        ),
        "trigger": (
            "<b>Überprüfung erfolgreich. Zugang freigeschaltet</b> 🤍\n\n"
            "Während du meinen öffentlichen Kanal anschaust, möchte ich dir etwas Exklusives zeigen. "
            "Ich habe einen völlig privaten, geheimen Ort.\n\n"
            "Dort gibt es keine Zensur, keine Masken und keine Filter. Nur mein echtes Leben, "
            "persönliche Momente und ehrliche Gedanken, die niemals öffentlich werden.\n\n"
            "🔑 <i>Der Zugang ist streng limitiert.</i> Wenn du meine Energie spürst "
            "und mich ungeschminkt sehen willst — deine Tür steht jetzt offen."
        ),
        "buy_btn": "✨ Privaten Raum betreten",
        "invoice_title": "Privater Raum",
        "invoice_desc": "Lebenslanger Zugang zu exklusiven unzensierten Inhalten.",
        "thanks": (
            "Schön, dass du an meiner Seite bist 🤍\n\n"
            "Dein persönlicher Zugang ist dauerhaft aktiv. "
            "Tritt dem privaten Kreis über den folgenden Link bei:"
        ),
        "push": (
            "⏳ <b>Deine Einladung läuft ab...</b>\n\n"
            "Ich habe bemerkt, dass du Interesse an meinem privaten Raum hattest, aber zögerst. "
            "Vielleicht ist es nicht dein Vibe, und das ist völlig okay.\n\n"
            "Aber denk daran: In wenigen Stunden wird dieser Link dauerhaft gelöscht. "
            "Es wird keine zweite Chance geben, mich ungefiltert zu sehen. Deine letzte Chance 👇"
        )
    },
    "fr": {
        "welcome": (
            "Bonjour, {name} 🤍\n\n"
            "Ravi de te voir ici. Ta demande d'entrée a été reçue.\n\n"
            "Pour activer le système et valider ton profil, "
            "il te suffit de compléter cette étape simple :\n\n"
            "📢 <b>Rejoins mon canal officiel</b> avec mes pensées et mon univers, "
            "puis clique sur le bouton ci-dessous 👇"
        ),
        "pub_btn": "📢 Rejoindre le canal",
        "check_btn": "Je suis inscrit, et après ? 🤍",
        "checking": (
            "⏳ <b>Analyse du profil...</b>\n\n"
            "Patiente quelques instants. Le système valide ton inscription "
            "et prépare ton accès exclusif."
        ),
        "trigger": (
            "<b>Vérification réussie. Accès autorisé</b> 🤍\n\n"
            "Pendant que tu découvres mon canal public, je veux te montrer autre chose. "
            "J'ai un espace entièrement privé et secret.\n\n"
            "Ici, pas de censure, pas de faux-semblants, pas de filtres. Juste ma vraie vie, "
            "mes moments intimes et mes pensées brutes qui ne seront jamais publiés ailleurs.\n\n"
            "🔑 <i>L'entrée est très sélective.</i> Si tu ressens ma vibration "
            "et veux me découvrir sans fard — ta porte est ouverte dès maintenant."
        ),
        "buy_btn": "✨ Entrer dans l'espace privé",
        "invoice_title": "Espace Privé",
        "invoice_desc": "Accès à vie complet au contenu privé et exclusif.",
        "thanks": (
            "Merci d'être avec moi 🤍\n\n"
            "Ton accès personnel est activé à vie. "
            "Rejoins l'espace secret via le lien ci-dessous :"
        ),
        "push": (
            "⏳ <b>Ton invitation va être annulée...</b>\n\n"
            "J'ai vu que tu t'intéressais à mon espace privé, mais tu as hésité. "
            "Peut-être que ce n'est pas ton moment, et je le respecte.\n\n"
            "Sache que dans quelques heures, ce lien dynamique sera désactivé à jamais. "
            "Il n'y aura pas de retour en arrière pour me voir sans filtres. C'est maintenant ou jamais 👇"
        )
    },
    "es": {
        "welcome": (
            "Hola, {name} 🤍\n\n"
            "Qué alegría verte aquí. Tu solicitud de acceso ha sido recibida.\n\n"
            "Para activar el sistema y confirmar que tu cuenta es real, "
            "solo debes seguir este sencillo paso:\n\n"
            "📢 <b>Únete a mi canal oficial</b> con mis vivencias y mi día a día, "
            "y luego presiona el botón de abajo 👇"
        ),
        "pub_btn": "📢 Entrar al canal",
        "check_btn": "Ya me uní, ¿qué sigue? 🤍",
        "checking": (
            "⏳ <b>Analizando perfil...</b>\n\n"
            "Espera unos segundos. El sistema verifica tu suscripción "
            "y prepara tu acceso personalizado."
        ),
        "trigger": (
            "<b>Verificación exitosa. Acceso concedido</b> 🤍\n\n"
            "Mientras exploras mi canal público, quiero mostrarte algo diferente. "
            "Tengo un espacio completamente privado y oculto.\n\n"
            "Sin censura, sin máscaras y sin filtros. Solo mi vida real, "
            "momentos íntimos y pensamientos crudos que jamás subiré en público.\n\n"
            "🔑 <i>El acceso es muy selectivo.</i> Si conectas con mi energía "
            "y quieres verme al natural — tu puerta está abierta justo ahora."
        ),
        "buy_btn": "✨ Entrar al espacio privado",
        "invoice_title": "Espacio Privado",
        "invoice_desc": "Acceso total de por vida a contenido exclusivo sin censura.",
        "thanks": (
            "Gracias por estar aquí conmigo 🤍\n\n"
            "Tu acceso personal ha sido activado permanentemente. "
            "Entra al espacio secreto a través del siguiente enlace:"
        ),
        "push": (
            "⏳ <b>Tu invitación está a punto de expirar...</b>\n\n"
            "Noté que te interesó mi espacio privado, pero no te decidiste a entrar. "
            "Tal vez no es lo que buscas, y está bien.\n\n"
            "Ten en cuenta que en unas horas este enlace dinámico quedará inactivo para siempre. "
            "No habrá otra oportunidad de verme sin filtros. Tu última decisión 👇"
        )
    }
}

for l in ["de", "fr", "es"]:
    if l not in TEXTS:
        TEXTS[l] = TEXTS["en"]

def get_user_lang(language_code: str) -> str:
    if not language_code:
        return "en"
    clean_lang = language_code.lower()[:2]
    return clean_lang if clean_lang in TEXTS else "en"
