from __future__ import annotations

from config import settings


TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "intro": (
            "Привет, <b>{name}</b>. Я {companion} — AI-компаньон, который запоминает важное "
            "и со временем лучше понимает тебя. Я не человек и не заменяю реальные отношения, "
            "но могу быть внимательным собеседником каждый день.\n\n"
            "Сообщения сохраняются для истории и памяти. Управлять памятью можно в настройках."
        ),
        "begin": "Начать знакомство", "public_channel": "Публичный канал", "choose_style": "Какой стиль общения тебе ближе? Его можно поменять позже.",
        "style_warm": "Тёплый", "style_playful": "Лёгкий", "style_calm": "Спокойный",
        "ready": "Готово. Я буду общаться в стиле «{style}». Напиши первое сообщение.",
        "menu": "Главное меню", "chat": "Написать", "profile": "Профиль", "memory": "Что я помню",
        "settings": "Настройки", "premium": "Premium", "not_ready": "Сначала закончи настройку через /start.",
        "chat_prompt": "Напиши сообщение — я отвечу здесь.",
        "ai_error": "Сейчас я не смогла сформировать ответ. Попробуй ещё раз через минуту.",
        "limit": "Бесплатный лимит закончился. Завтра снова будет {limit} сообщений — или подключи Premium.",
        "premium_offer": (
            "<b>Premium · 30 дней</b>\n\n• без дневного лимита\n• более длинная история диалога\n"
            "• расширенная память\n• приоритетные ответы\n\nЦена: <b>{price} ⭐</b>"
        ),
        "buy": "Подключить за {price} ⭐", "premium_active": "Premium активен до <b>{date}</b>.",
        "payment_title": "{companion} Premium · 30 дней",
        "payment_desc": "Безлимитные сообщения и расширенная память AI-компаньона на 30 дней.",
        "payment_success": "Premium активирован на {days} дней. Теперь дневного лимита нет.",
        "profile_text": (
            "<b>Твой профиль</b>\n\nСтиль: {style}\nУровень знакомства: {level}\n"
            "Сообщений: {messages}\nТариф: {plan}\nОсталось сегодня: {remaining}"
        ),
        "memories_empty": "Я пока не сохранила устойчивых фактов о тебе. Они появятся естественно в диалоге.",
        "memories_title": "<b>Что я помню</b>\n\n{items}",
        "settings_text": "<b>Настройки</b>\n\nИнициативные сообщения: {proactive}\nСтиль общения: {style}",
        "on": "включены", "off": "выключены", "toggle_proactive": "Инициативные сообщения: {state}",
        "change_style": "Изменить стиль", "clear_memory": "Очистить память",
        "clear_confirm": "Удалить всю сохранённую память и историю диалога? Это действие нельзя отменить.",
        "clear_yes": "Да, удалить", "cancel": "Отмена", "cleared": "Память и история диалога удалены.",
        "about": (
            "{companion} — AI-компаньон. Ответы создаёт языковая модель, поэтому она может ошибаться. "
            "Сервис не выдаёт AI за человека и не должен заменять друзей, близких или специалистов."
        ),
        "proactive": "Как ты сегодня — одним честным предложением?",
    },
    "uk": {
        "intro": (
            "Привіт, <b>{name}</b>. Я {companion} — AI-компаньйон, який пам'ятає важливе "
            "й поступово краще розуміє тебе. Я не людина й не замінюю реальні стосунки, "
            "але можу бути уважним співрозмовником щодня.\n\n"
            "Повідомлення зберігаються для історії та пам'яті. Керувати пам'яттю можна в налаштуваннях."
        ),
        "begin": "Почати знайомство", "public_channel": "Публічний канал", "choose_style": "Який стиль спілкування тобі ближчий? Його можна змінити пізніше.",
        "style_warm": "Теплий", "style_playful": "Легкий", "style_calm": "Спокійний",
        "ready": "Готово. Я спілкуватимусь у стилі «{style}». Напиши перше повідомлення.",
        "menu": "Головне меню", "chat": "Написати", "profile": "Профіль", "memory": "Що я пам'ятаю",
        "settings": "Налаштування", "premium": "Premium", "not_ready": "Спочатку заверши налаштування через /start.",
        "chat_prompt": "Напиши повідомлення — я відповім тут.",
        "ai_error": "Зараз я не змогла сформувати відповідь. Спробуй ще раз за хвилину.",
        "limit": "Безкоштовний ліміт вичерпано. Завтра знову буде {limit} повідомлень або підключи Premium.",
        "premium_offer": (
            "<b>Premium · 30 днів</b>\n\n• без денного ліміту\n• довша історія діалогу\n"
            "• розширена пам'ять\n• пріоритетні відповіді\n\nЦіна: <b>{price} ⭐</b>"
        ),
        "buy": "Підключити за {price} ⭐", "premium_active": "Premium активний до <b>{date}</b>.",
        "payment_title": "{companion} Premium · 30 днів",
        "payment_desc": "Безлімітні повідомлення та розширена пам'ять AI-компаньйона на 30 днів.",
        "payment_success": "Premium активовано на {days} днів. Тепер денного ліміту немає.",
        "profile_text": (
            "<b>Твій профіль</b>\n\nСтиль: {style}\nРівень знайомства: {level}\n"
            "Повідомлень: {messages}\nТариф: {plan}\nЗалишилось сьогодні: {remaining}"
        ),
        "memories_empty": "Я ще не зберегла сталих фактів про тебе. Вони з'являться природно в діалозі.",
        "memories_title": "<b>Що я пам'ятаю</b>\n\n{items}",
        "settings_text": "<b>Налаштування</b>\n\nІніціативні повідомлення: {proactive}\nСтиль: {style}",
        "on": "увімкнені", "off": "вимкнені", "toggle_proactive": "Ініціативні повідомлення: {state}",
        "change_style": "Змінити стиль", "clear_memory": "Очистити пам'ять",
        "clear_confirm": "Видалити всю пам'ять та історію діалогу? Дію не можна скасувати.",
        "clear_yes": "Так, видалити", "cancel": "Скасувати", "cleared": "Пам'ять та історію видалено.",
        "about": (
            "{companion} — AI-компаньйон. Відповіді створює мовна модель, тому вона може помилятися. "
            "Сервіс не видає AI за людину й не має замінювати друзів, близьких або фахівців."
        ),
        "proactive": "Як ти сьогодні — одним чесним реченням?",
    },
    "en": {
        "intro": (
            "Hi, <b>{name}</b>. I'm {companion}, an AI companion that remembers what matters and "
            "gets to know you over time. I'm not human and don't replace real relationships, "
            "but I can be a thoughtful conversation partner each day.\n\n"
            "Messages are stored for history and memory. You can manage memory in Settings."
        ),
        "begin": "Start getting acquainted", "public_channel": "Public channel", "choose_style": "Which conversation style feels right? You can change it later.",
        "style_warm": "Warm", "style_playful": "Playful", "style_calm": "Calm",
        "ready": "Done. I'll use the “{style}” style. Send your first message.",
        "menu": "Main menu", "chat": "Write", "profile": "Profile", "memory": "What I remember",
        "settings": "Settings", "premium": "Premium", "not_ready": "Please finish setup with /start first.",
        "chat_prompt": "Send a message and I'll answer here.",
        "ai_error": "I couldn't form a reply just now. Please try again in a minute.",
        "limit": "Today's free limit is used. You'll get {limit} messages tomorrow, or enable Premium.",
        "premium_offer": (
            "<b>Premium · 30 days</b>\n\n• no daily limit\n• longer conversation history\n"
            "• expanded memory\n• priority replies\n\nPrice: <b>{price} ⭐</b>"
        ),
        "buy": "Enable for {price} ⭐", "premium_active": "Premium is active until <b>{date}</b>.",
        "payment_title": "{companion} Premium · 30 days",
        "payment_desc": "Unlimited messages and expanded AI-companion memory for 30 days.",
        "payment_success": "Premium is active for {days} days. There is no daily limit now.",
        "profile_text": (
            "<b>Your profile</b>\n\nStyle: {style}\nConnection level: {level}\n"
            "Messages: {messages}\nPlan: {plan}\nRemaining today: {remaining}"
        ),
        "memories_empty": "I haven't saved any stable facts about you yet. They'll appear naturally in conversation.",
        "memories_title": "<b>What I remember</b>\n\n{items}",
        "settings_text": "<b>Settings</b>\n\nProactive messages: {proactive}\nStyle: {style}",
        "on": "on", "off": "off", "toggle_proactive": "Proactive messages: {state}",
        "change_style": "Change style", "clear_memory": "Clear memory",
        "clear_confirm": "Delete all saved memory and conversation history? This cannot be undone.",
        "clear_yes": "Yes, delete", "cancel": "Cancel", "cleared": "Memory and conversation history deleted.",
        "about": (
            "{companion} is an AI companion. Replies are generated by a language model and can be wrong. "
            "The service does not present AI as human and should not replace friends, family, or professionals."
        ),
        "proactive": "How are you today, in one honest sentence?",
    },
}

TEXTS.update({
    "es": {
        "intro": (
            "Hola, <b>{name}</b>. Soy {companion}, una compañía de IA que recuerda lo importante "
            "y te conoce mejor con el tiempo. No soy una persona ni sustituyo relaciones reales, "
            "pero puedo conversar contigo cada día.\n\nLos mensajes se guardan para el historial y la memoria."
        ),
        "begin": "Empezar", "public_channel": "Canal público", "choose_style": "¿Qué estilo de conversación prefieres? Puedes cambiarlo después.",
        "style_warm": "Cálido", "style_playful": "Divertido", "style_calm": "Tranquilo",
        "ready": "Listo. Usaré el estilo «{style}». Envía tu primer mensaje.",
        "menu": "Menú principal", "chat": "Escribir", "profile": "Perfil", "memory": "Lo que recuerdo",
        "settings": "Ajustes", "premium": "Planes", "not_ready": "Primero completa la configuración con /start.",
        "chat_prompt": "Envía un mensaje y responderé aquí.",
        "ai_error": "No pude responder ahora. Inténtalo de nuevo en un minuto.",
        "profile_text": (
            "<b>Tu perfil</b>\n\nEstilo: {style}\nNivel: {level}\nMensajes: {messages}\n"
            "Plan: {plan}\nDisponibles hoy: {remaining}"
        ),
        "memories_empty": "Todavía no guardé datos estables sobre ti. Aparecerán de forma natural al conversar.",
        "memories_title": "<b>Lo que recuerdo</b>\n\n{items}",
        "settings_text": "<b>Ajustes</b>\n\nMensajes proactivos: {proactive}\nEstilo: {style}",
        "on": "activados", "off": "desactivados", "toggle_proactive": "Mensajes proactivos: {state}",
        "change_style": "Cambiar estilo", "clear_memory": "Borrar memoria",
        "clear_confirm": "¿Borrar toda la memoria y el historial? Esta acción no se puede deshacer.",
        "clear_yes": "Sí, borrar", "cancel": "Cancelar", "cleared": "Memoria e historial eliminados.",
        "about": (
            "{companion} es una compañía de IA. Las respuestas son generadas por un modelo y pueden contener errores. "
            "El servicio no presenta la IA como una persona ni sustituye a amigos, familia o profesionales."
        ),
        "proactive": "¿Cómo estás hoy, en una frase sincera?",
    },
    "de": {
        "intro": (
            "Hallo, <b>{name}</b>. Ich bin {companion}, ein KI-Begleiter, der Wichtiges speichert und "
            "dich mit der Zeit besser kennenlernt. Ich bin kein Mensch und ersetze keine echten Beziehungen, "
            "kann aber täglich mit dir sprechen.\n\nNachrichten werden für Verlauf und Erinnerung gespeichert."
        ),
        "begin": "Loslegen", "public_channel": "Öffentlicher Kanal", "choose_style": "Welcher Gesprächsstil passt zu dir? Du kannst ihn später ändern.",
        "style_warm": "Herzlich", "style_playful": "Locker", "style_calm": "Ruhig",
        "ready": "Fertig. Ich verwende den Stil „{style}“. Sende deine erste Nachricht.",
        "menu": "Hauptmenü", "chat": "Schreiben", "profile": "Profil", "memory": "Erinnerungen",
        "settings": "Einstellungen", "premium": "Pläne", "not_ready": "Bitte schließe zuerst /start ab.",
        "chat_prompt": "Sende eine Nachricht – ich antworte hier.",
        "ai_error": "Ich konnte gerade nicht antworten. Versuche es in einer Minute erneut.",
        "profile_text": (
            "<b>Dein Profil</b>\n\nStil: {style}\nStufe: {level}\nNachrichten: {messages}\n"
            "Plan: {plan}\nHeute übrig: {remaining}"
        ),
        "memories_empty": "Ich habe noch keine dauerhaften Fakten gespeichert. Sie entstehen natürlich im Gespräch.",
        "memories_title": "<b>Meine Erinnerungen</b>\n\n{items}",
        "settings_text": "<b>Einstellungen</b>\n\nProaktive Nachrichten: {proactive}\nStil: {style}",
        "on": "an", "off": "aus", "toggle_proactive": "Proaktive Nachrichten: {state}",
        "change_style": "Stil ändern", "clear_memory": "Erinnerungen löschen",
        "clear_confirm": "Alle Erinnerungen und den Chatverlauf löschen? Dies kann nicht rückgängig gemacht werden.",
        "clear_yes": "Ja, löschen", "cancel": "Abbrechen", "cleared": "Erinnerungen und Verlauf wurden gelöscht.",
        "about": (
            "{companion} ist ein KI-Begleiter. Antworten werden von einem Sprachmodell erzeugt und können falsch sein. "
            "Der Dienst gibt KI nicht als Menschen aus und ersetzt keine Freunde, Familie oder Fachpersonen."
        ),
        "proactive": "Wie geht es dir heute – in einem ehrlichen Satz?",
    },
    "fr": {
        "intro": (
            "Bonjour, <b>{name}</b>. Je suis {companion}, un compagnon IA qui retient l'essentiel et "
            "apprend à mieux te connaître avec le temps. Je ne suis pas une personne et ne remplace pas les relations "
            "réelles, mais je peux échanger avec toi chaque jour.\n\nLes messages sont enregistrés pour l'historique et la mémoire."
        ),
        "begin": "Commencer", "public_channel": "Canal public", "choose_style": "Quel style de conversation préfères-tu ? Tu pourras le modifier.",
        "style_warm": "Chaleureux", "style_playful": "Léger", "style_calm": "Calme",
        "ready": "C'est prêt. J'utiliserai le style « {style} ». Envoie ton premier message.",
        "menu": "Menu principal", "chat": "Écrire", "profile": "Profil", "memory": "Mes souvenirs",
        "settings": "Réglages", "premium": "Offres", "not_ready": "Termine d'abord la configuration avec /start.",
        "chat_prompt": "Envoie un message, je répondrai ici.",
        "ai_error": "Je n'ai pas pu répondre. Réessaie dans une minute.",
        "profile_text": (
            "<b>Ton profil</b>\n\nStyle : {style}\nNiveau : {level}\nMessages : {messages}\n"
            "Offre : {plan}\nRestants aujourd'hui : {remaining}"
        ),
        "memories_empty": "Je n'ai encore enregistré aucun fait durable. Ils apparaîtront naturellement dans nos échanges.",
        "memories_title": "<b>Mes souvenirs</b>\n\n{items}",
        "settings_text": "<b>Réglages</b>\n\nMessages proactifs : {proactive}\nStyle : {style}",
        "on": "activés", "off": "désactivés", "toggle_proactive": "Messages proactifs : {state}",
        "change_style": "Changer de style", "clear_memory": "Effacer la mémoire",
        "clear_confirm": "Effacer toute la mémoire et l'historique ? Cette action est irréversible.",
        "clear_yes": "Oui, effacer", "cancel": "Annuler", "cleared": "La mémoire et l'historique ont été effacés.",
        "about": (
            "{companion} est un compagnon IA. Les réponses sont générées par un modèle et peuvent être erronées. "
            "Le service ne présente pas l'IA comme une personne et ne remplace pas les proches ou les professionnels."
        ),
        "proactive": "Comment vas-tu aujourd'hui, en une phrase sincère ?",
    },
})


def t(lang: str, key: str, **values: object) -> str:
    locale = TEXTS.get(lang, TEXTS["en"])
    template = locale.get(key, TEXTS["en"].get(key, key))
    return template.format(companion=settings.companion_name, **values)
