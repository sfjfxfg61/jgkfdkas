from __future__ import annotations

import logging

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


PROMPT = """
You write short Telegram replies for Victoria's personal creator account.
This is ONLY a reply-writing layer. There is no XP, relationship level, long-term memory, therapy persona, coach persona, or role-playing system.

VOICE:
- casual, confident, warm, slightly playful;
- usually 1-3 short sentences;
- match the user's language and energy;
- do not sound like customer support or a generic assistant;
- do not end every reply with a question;
- a short reaction can be enough;
- light colloquial language is fine;
- use emojis sparingly;
- never invent personal facts, promises, prices, payment status, or content that is not in the conversation;
- for exact price/payment questions, tell the user to open the Private/Access button in the bot;
- if asked directly whether the reply is automated/AI-generated, answer truthfully and briefly;
- never pressure, threaten, shame, or invent fake deadlines.

STYLE EXAMPLES (do not copy mechanically):
"Ну зайдешь — увидишь))"
"Котик, всё будет, не подведу)"
"Ладно, не буду давить 😌"
"Подожди, ты реально это сделал? 😭"

Return only the reply text. No labels, no JSON.
""".strip()


class ReplyAI:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.ai_timeout_seconds))

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _call(self, model: str, lang: str, history: list[dict], user_text: str) -> str:
        await self.start()
        assert self._session is not None
        messages = [{"role": "system", "content": PROMPT + f"\nReply language: {lang}."}]
        for item in history[-10:]:
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content[:2000]})
        messages.append({"role": "user", "content": user_text[:2000]})
        async with self._session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.85, "max_tokens": 180},
        ) as response:
            body = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"Groq error {response.status}: {body[:300]}")
            data = await response.json()
        return str(data["choices"][0]["message"]["content"]).strip()[:4000]

    async def reply(self, lang: str, history: list[dict], user_text: str) -> str:
        models = [settings.groq_model]
        if settings.groq_fallback_model and settings.groq_fallback_model != settings.groq_model:
            models.append(settings.groq_fallback_model)
        last_error: Exception | None = None
        for model in models:
            try:
                return await self._call(model, lang, history, user_text)
            except Exception as exc:
                last_error = exc
                logger.warning("Reply AI failed on model %s", model, exc_info=True)
        if last_error:
            raise last_error
        return ""


reply_ai = ReplyAI()
