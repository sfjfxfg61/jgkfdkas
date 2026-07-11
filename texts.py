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
            "Рада бачити тебе тут! Для початку тримай доступ до мого офіційного каналу з думками та затишною атмосферою.\n\n"
            "⚠️ <b>Обов'язково підпишись</b>, а потім натисни кнопку нижче, щоб система підтвердила твій вхід і відкрила наступний крок 👇"
        ),
        "pub_btn": "📢 Перейти в канал",
        "check_btn": "Я підписався, що далі? 🤍",
        "checking": "Перевіряю твою підписку... ⏳\n\nЗачекай буквально 1-2 хвилини, я готую для тебе дещо особливе. Не вимикай сповіщення.",
        "trigger": (
            "Я все перевірила... Ти всередині 🤍\n\n"
            "Поки ти дивишся мій канал, я хочу відкрити тобі дещо більше. У мене є закрите місце «для своїх». "
            "Там я публікую те, що ніколи не вийде публічно — особисті моменти, чесні думки та контент без цензури.\n\n"
            "Зазвичай туди потрапляють одиниці, і я тримаю цей доступ закритим від зайвих очей. "
            "Якщо тобі відгукується моя енергетика — я готова впустити тебе прямо зараз."
        ),
        "buy_btn": "✨ Зазирнути в приват",
        "invoice_title": "Приватний простір",
        "invoice_desc": "Повний довічний доступ до закритих матеріалів",
        "thanks": "Дякую, що ти зі мною 🤍\n\nTвій доступ активовано. Вхід у приватний простір нижче:",
    },
    "ru": {
        "welcome": (
            "Привет, {name} 🤍\n\n"
            "Рада видеть тебя здесь! Для начала держи доступ к моему официальному каналу с мыслями и уютной атмосферой.\n\n"
            "⚠️ <b>Обязательно подпишись</b>, а затем нажми кнопку ниже, чтобы система подтвердила твой вход и открыла следующий шаг 👇"
        ),
        "pub_btn": "📢 Перейти в канал",
        "check_btn": "Я подписался, что дальше? 🤍",
        "checking": "Проверяю твою подписку... ⏳\n\nПодожди буквально 1-2 минуты, я готовлю для тебя кое-что особенное. Не выключай уведомления.",
        "trigger": (
            "Я всё проверила... Ты внутри 🤍\n\n"
            "Пока ты смотришь мой канал, я хочу открыть тебе кое-что большее. У меня есть закрытое место «для своих». "
            "Там я публикую то, что никогда не выйдет публично — личные моменты, честные мысли и контент без цензуры.\n\n"
            "Обычно туда попадают единицы, и я держу этот доступ закрытым от лишних глаз. "
            "Если тебе откликается моя энергетика — я готова впустить тебя прямо сейчас."
        ),
        "buy_btn": "✨ Заглянуть в приват",
        "invoice_title": "Приватное пространство",
        "invoice_desc": "Полный пожизненный access к закрытым материалам",
        "thanks": "Спасибо, что ты со мной 🤍\n\nТвой доступ активирован. Вход в приватное пространство ниже:",
    },
    "en": {
        "welcome": (
            "Hey, {name} 🤍\n\n"
            "So glad to see you here! To start, here is the access to my official channel with my thoughts and lifestyle updates.\n\n"
            "⚠️ <b>Make sure to join</b>, then press the button below so the system can verify your profile and open the next step 👇"
        ),
        "pub_btn": "📢 Enter Public Channel",
        "check_btn": "I have joined, what's next? 🤍",
        "checking": "Verifying your subscription... ⏳\n\nGive me 1-2 minutes, I am preparing something special for you. Keep your notifications on.",
        "trigger": (
            "Everything is verified... You are in 🤍\n\n"
            "While you check out my channel, I want to show you something bigger. Actually, I have a hidden place for 'the chosen ones'. "
            "That's where I share things I'd never post publicly — personal moments, raw thoughts, and uncensored content.\n\n"
            "Only a few ever get inside. If you feel my vibe, I'm ready to open the door for you right now."
        ),
        "buy_btn": "✨ Enter Private Space",
        "invoice_title": "Private Space",
        "invoice_desc": "Lifetime access to exclusive uncensored content",
        "thanks": "Thank you for being with me 🤍\n\nYour access is verified. Enter the private space below:",
    },
    "de": {
        "welcome": (
            "Hey, {name} 🤍\n\n"
            "Schön, dass du da bist! Hier ist der Zugang zu meinem offiziellen Kanal mit meinen Gedanken und meiner Ästhetik.\n\n"
            "⚠️ <b>Tritt dem Kanal bei</b>, und klicke dann auf die Schaltfläche unten, damit das System deinen Zugang bestätigen kann 👇"
        ),
        "pub_btn": "📢 Kanal beitreten",
        "check_btn": "Ich bin beigetreten, was kommt jetzt? 🤍",
        "checking": "Abonnement wird überprüft... ⏳\n\nWarte 1-2 Minuten, ich bereite etwas Besonderes für dich vor. Schalte die Benachrichtigungen nicht aus.",
        "trigger": (
            "Alles überprüft... Du bist drin 🤍\n\n"
            "Während du meinen Kanal anschaust, möchte ich dir etwas Größeres zeigen. Ich habe einen geheimen Ort nur für uns. "
            "Dort teile ich Dinge, die niemals öffentlich werden — persönliche Momente und unzensierte Inhalte.\n\n"
            "Nur wenige bekommen diesen Zugang. Wenn du meine Energie spürst, öffne ich jetzt die Tür für dich."
        ),
        "buy_btn": "✨ Privaten Raum betreten",
        "invoice_title": "Privater Raum",
        "invoice_desc": "Lebenslanger Zugang zu exklusiven Inhalten",
        "thanks": "Schön, dass du dabei bist 🤍\n\nDein Zugang ist aktiv. Willkommen im privaten Kreis:",
    },
    "fr": {
        "welcome": (
            "Coucou, {name} 🤍\n\n"
            "Ravi de te voir ici ! Pour commencer, voici l'accès à mon canal officiel avec mes pensées et mon univers.\n\n"
            "⚠️ <b>Rejoins le canal</b>, puis appuie sur le bouton ci-dessous pour que le système valide ton accès 👇"
        ),
        "pub_btn": "📢 Rejoindre le canal",
        "check_btn": "Je suis inscrit, et après ? 🤍",
        "checking": "Vérification de ton inscription... ⏳\n\nPatiente 1 à 2 minutes, je prépare quelque chose de spécial pour toi. Reste connecté.",
        "trigger": (
            "Tout est validé... Tu y es 🤍\n\n"
            "Pendant que tu découvres mon canal, je veux t'ouvrir un espace plus grand. En réalité, j'ai un endroit secret, juste pour les intimes. "
            "J'y publie ce qui ne sera jamais public — des moments personnels, mes vraies pensées et du contenu sans censure.\n\n"
            "C'est très sélectif. Si tu aimes mon univers, je suis prête à t'ouvrir la porte dès maintenant."
        ),
        "buy_btn": "✨ Entrer dans l'espace privé",
        "invoice_title": "Espace Privé",
        "invoice_desc": "Accès à vie au contenu privé exclusif",
        "thanks": "Merci d'être là 🤍\n\nTon accès est validé. Bienvenue dans notre cercle secret :",
    },
    "es": {
        "welcome": (
            "Hola, {name} 🤍\n\n"
            "¡Qué alegría verte aquí! Para empezar, aquí tienes acceso a mi canal oficial con mis pensamientos y mi día a día.\n\n"
            "⚠️ <b>Asegúrate de unirte</b>, y luego presiona el botón de abajo para que el sistema confirme tu entrada 👇"
        ),
        "pub_btn": "📢 Entrar al canal",
        "check_btn": "Ya me uní, ¿qué sigue? 🤍",
        "checking": "Verificando tu suscripción... ⏳\n\nEspera 1-2 minutos, estoy preparando algo muy especial para ti. No apagues las notificaciones.",
        "trigger": (
            "Todo verificado... Ya estás dentro 🤍\n\n"
            "Mientras miras mi canal, quiero mostrarte algo más grande. La verdad es que tengo un lugar oculto 'para los elegidos'. "
            "Ahí subo lo que jamás publicaría en abierto: momentos íntimos, pensamientos reales y contenido sin censura.\n\n"
            "Casi nadie logra entrar. Si te gusta mi vibra, estoy dispuesta a abrirte la puerta ahora mismo."
        ),
        "buy_btn": "✨ Entrar al espacio privado",
        "invoice_title": "Espacio Privado",
        "invoice_desc": "Acceso de por vida al contenido exclusivo",
        "thanks": "Gracias por estar conmigo 🤍\n\nTu acceso está confirmado. Bienvenido a nuestro círculo secreto:",
    }
}

def get_user_lang(language_code: str) -> str:
    if not language_code:
        return "en"
    clean_lang = language_code.lower()[:2]
    return clean_lang if clean_lang in TEXTS else "en"
