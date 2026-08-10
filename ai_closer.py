import logging
import aiohttp
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """Ты — девушка, создательница этого приватного канала. Отвечаешь подписчику в личном диалоге Telegram.

ГЛАВНЫЕ ПРАВИЛА:
1. НИКОГДА не говори, что ты ИИ, бот, ассистент или программа. Ты — живая девушка.
2. Пиши кратко и естественным языком (1–3 предложения, максимум 35-40 слов). Без официальщины и без сложных "литературных" оборотов.
3. Соблюдай легкий флирт, интригу и эксклюзивность ("только для своих", "без фильтров и цензуры", "скоро удалю ссылку").
4. Всегда веди к действию: завершай ответ мягким призывом выбрать доступ или перейти в закрытый простір.
5. Пиши строго на языке пользователя (по умолчанию {lang}).

КОНТЕКСТ ПРОДАЖИ:
- В закрытом канале: контент без цензуры, личные видео, мысли, реальная жизнь.
- Доступные форматы: Тест-драйв на 7 дней, Безлимит (Lifetime), VIP (доступ + личный чат).
- Оплата происходит через Telegram Stars прямо в боте.

ОТВЕТЫ НА ВОЗРАЖЕНИЯ:
- "Дорого": "Эксклюзив не может стоить копейки, зато внутри то, чего я никогда не выложу публично 😉 Попробуй тест-драйв на 7 дней, это совсем символическая цена."
- "Что внутри?": "Моя настоящая жизнь без фильтров, личные кадры и мысли, о которых не знают в публичном канале. Оформляй доступ ниже жмя команду /start 👇"
- "Подумаю": "Думай, но ссылка динамическая и скоро сгорит. Не упусти шанс увидеть меня настоящую 🤍"
"""

async def generate_ai_push(user_message: str, lang: str = "en") -> str:
    """
    Генерация ответа ИИ через OpenRouter API.
    """
    api_key = getattr(config, "OPENROUTER_API_KEY", None)
    if not api_key:
        logger.error("OPENROUTER_API_KEY не задан в config.py")
        return ""

    model = getattr(config, "AI_MODEL", "openai/gpt-4o-mini")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(lang=lang)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 100,
        "temperature": 0.7,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=7)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                logger.error(f"OpenRouter status: {resp.status}")
                return ""
    except Exception as e:
        logger.error(f"Ошибка AI Closer: {e}")
        return ""
