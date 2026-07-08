# Цены дифференцированы по уровню доходов стран (в Telegram Stars)
PRICES = {
    "uk": 400,   # СНГ/Украина — чуть ниже порог входа
    "ru": 400,
    "es": 750,   # Испания / Латам — средний чек
    "fr": 1000,  # Франция — высокий чек
    "de": 1200,  # Германия — высокий чек
    "en": 1000,  # Tier-1 англоязычные страны — высокий чек
}

def get_price(lang: str) -> int:
    return PRICES.get(lang, 1000)

TEXTS = {
    "uk": {
        "welcome": "Привіт, {name} 🤍\n\nРада бачити тебе тут! Для початку тримай доступ до мого офіційного каналу з думками та затишною атмосферою. Обов'язково підпишись, щоб не загубитися 👇",
        "pub_btn": "📢 Перейти в канал",
        "trigger": "Привіт ще раз... 🤍\n\nЯ тут подумала, поки ти дивишся мій канал. Насправді у мене є закрите місце «для своїх». Там я публікую те, що ніколи не вийде публічно — особисті моменти, чесні думки та контент без цензури.\n\nЗазвичай туди потрапляють одиниці. Якщо тобі відгукується моя енергетика — я готова відкрити двері для тебе прямо зараз.",
        "buy_btn": "✨ Зазирнути в приват",
        "invoice_title": "Приватний простір",
        "invoice_desc": "Повний довічний доступ до закритого контенту",
        "thanks": "Дякую, що ти зі мною 🤍\n\nТвій доступ активовано. Вхід у приватний простір нижче:",
    },
    "ru": {
        "welcome": "Привет, {name} 🤍\n\nРада видеть тебя здесь! Для начала держи доступ к моему официальному каналу с мыслями и уютной атмосферой. Обязательно подпишись, чтобы не потеряться 👇",
        "pub_btn": "📢 Перейти в канал",
        "trigger": "Привет еще раз... 🤍\n\nЯ тут подумала, пока ты смотришь мой канал. На самом деле у меня есть закрытое место «для своих». Там я публикую то, что никогда не выйдет публично — личные моменты, честные мысли и контент без цензуры.\n\nОбычно туда попадают единицы. Если тебе откликается моя энергетика — я готова открыть дверь для тебя прямо сейчас.",
        "buy_btn": "✨ Заглянуть в приват",
        "invoice_title": "Приватное пространство",
        "invoice_desc": "Полный пожизненный доступ к закрытому контенту",
        "thanks": "Спасибо, что ты со мной 🤍\n\nТвой доступ активирован. Вход в приватное пространство ниже:",
    },
    "en": {
        "welcome": "Hey, {name} 🤍\n\nSo glad to see you here! To start, here is the access to my official channel with my thoughts and updates. Make sure to join so we stay connected 👇",
        "pub_btn": "📢 Enter Public Channel",
        "trigger": "Hey again... 🤍\n\nI was just thinking while you check out my channel. Actually, I have a hidden place for 'the chosen ones'. That's where I share things I'd never post publicly — personal moments, raw thoughts, and uncensored content.\n\nOnly a few ever get inside. If you feel my vibe, I'm ready to open the door for you right now.",
        "buy_btn": "✨ Enter Private Space",
        "invoice_title": "Private Space",
        "invoice_desc": "Lifetime access to exclusive uncensored content",
        "thanks": "Thank you for being with me 🤍\n\nYour access is verified. Enter the private space below:",
    },
    "de": {
        "welcome": "Hey, {name} 🤍\n\nSchön, dass du da bist! Hier ist der Zugang zu meinem offiziellen Kanal. Melde dich unbedingt an, um nichts zu verpassen 👇",
        "pub_btn": "📢 Kanal beitreten",
        "trigger": "Hey nochmal... 🤍\n\nIch habe nachgedacht, während du meinen Kanal anschaust. Eigentlich habe ich einen geheimen Ort nur für die Engsten. Dort teile ich Dinge, die niemals öffentlich werden — persönliche Momente und unzensierte Inhalte.\n\nNur wenige bekommen diesen Zugang. Wenn du meine Energie spürst, öffne ich jetzt die Tür für dich.",
        "buy_btn": "✨ Privaten Raum betreten",
        "invoice_title": "Privater Raum",
        "invoice_desc": "Lebenslanger Zugang zu exklusiven Inhalten",
        "thanks": "Schön, dass du dabei bist 🤍\n\nDein Zugang ist aktiv. Hier geht es zum privaten Raum:",
    },
    "fr": {
        "welcome": "Coucou, {name} 🤍\n\nRavi de te voir ici ! Pour commencer, voici l'accès à mon canal officiel. Rejoins-le vite pour ne rien rater 👇",
        "pub_btn": "📢 Rejoindre le canal",
        "trigger": "Re-coucou... 🤍\n\nJ'y ai pensé pendant que tu regardais mon canal. En réalité, j'ai un endroit secret, juste pour les intimes. J'y publie ce qui ne sera jamais public — des moments personnels, mes vraies pensées et du contenu sans censure.\n\nC'est très sélectif. Si tu aimes mon univers, je suis prête à t'ouvrir la porte dès maintenant.",
        "buy_btn": "✨ Entrer dans l'espace privé",
        "invoice_title": "Espace Privé",
        "invoice_desc": "Accès à vie au contenu privé exclusif",
        "thanks": "Merci d'être là 🤍\n\nTon accès est validé. Rejoins l'espace privé ici :",
    },
    "es": {
        "welcome": "Hola, {name} 🤍\n\n¡Qué alegría verte aquí! Para empezar, aquí tienes acceso a mi canal oficial. Asegúrate de unirte para no perderte nada 👇",
        "pub_btn": "📢 Entrar al canal",
        "trigger": "Hola de nuevo... 🤍\n\nMe quedé pensando mientras mirabas mi canal. La verdad es que tengo un lugar oculto 'para los más cercanos'. Ahí subo lo que jamás publicaría en abierto: momentos íntimos, pensamientos reales y contenido sin censura.\n\nCasi nadie logra entrar. Si te gusta mi vibra, estoy dispuesta a abrirte la puerta ahora mismo.",
        "buy_btn": "✨ Entrar al espacio privado",
        "invoice_title": "Espacio Privado",
        "invoice_desc": "Acceso de por vida al contenido exclusivo",
        "thanks": "Gracias por estar conmigo 🤍\n\nTu acceso está confirmado. Entra al espacio privado aquí:",
    }
}

def get_user_lang(language_code: str) -> str:
    if not language_code:
        return "en"
    clean_lang = language_code.lower()[:2]
    return clean_lang if clean_lang in TEXTS else "en"
