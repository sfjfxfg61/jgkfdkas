# ai_closer.py
import logging
import aiohttp
from config import OPENROUTER_API_KEY, AI_MODEL  # или из os.getenv

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

async def generate_ai_push(user_message: str, lang: str = "ru", history: list = None) -> str:
    """
    Генерация ответа ИИ с экономией токенов и ролевым дожимом.
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY не установлен.")
        return ""

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(lang=lang)

    # Формируем цепочку сообщений (только последние 4 для экономии токенов)
    messages = [{"role": "system", "content": system_prompt}]
    
    if history:
        # Берём максимум последние 4 сообщения истории
        for msg in history[-4:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org",
    }

    payload = {
        "model": AI_MODEL or "openai/gpt-4o-mini",  # gpt-4o-mini / deepseek-r1 / claude-3-haiku — дешёвые и быстрые
        "messages": messages,
        "max_tokens": 120,      # Экономия токенов
        "temperature": 0.7,     # Живой разговорный стиль
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    answer = data["choices"][0]["message"]["content"].strip()
                    return answer
                else:
                    logger.error(f"OpenRouter API error {resp.status}: await resp.text()")
                    return ""
    except Exception as e:
        logger.error(f"Ошибка при вызове AI Closer: {e}")
        return ""
