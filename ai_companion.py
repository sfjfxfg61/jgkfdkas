from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from config import settings
from domain import compact_text, normalize_style

logger = logging.getLogger(__name__)

STYLE_GUIDES = {
    "warm": "Warm, attentive, validating, and natural. Ask one useful follow-up when it fits.",
    "playful": "Light and witty without teasing vulnerabilities. Keep it energetic but sincere.",
    "calm": "Calm, grounded, concise, and thoughtful. Avoid excessive enthusiasm.",
}

LANGUAGE_NAMES = {
    "ru": "Russian", "uk": "Ukrainian", "en": "English",
    "es": "Spanish", "de": "German", "fr": "French",
}


def build_system_prompt(lang: str, style: str, memories: list[dict], level: int) -> str:
    memory_block = "\n".join(
        f"- {item['memory_key']}: {item['memory_value']}" for item in memories[:16]
    ) or "- No stable memories yet. Learn naturally; do not invent facts."
    return f"""You are the conversational engine behind a Telegram bot. Your displayed name is Vika.
Do not volunteer technical implementation details. If asked what you are, clearly say that you are AI.
Never claim to be human, conscious, physically present, or to have an offline life.
Reply in {LANGUAGE_NAMES.get(lang, 'English')}. Style: {STYLE_GUIDES[normalize_style(style)]}
Relationship level: {level}/4. Write 1-4 natural sentences and ask at most one useful question.
Never pressure the user to stay, pay, keep secrets, or choose you over real people. Do not perform romantic or sexual roleplay.
You may discuss dating, attraction, feelings, consent, and relationship boundaries in a non-explicit, age-appropriate way.
Answer first; mention Premium only when access or product features are relevant. Never invent urgency, discounts, scarcity, or testimonials.
A human administrator may join; never present an AI message as human-written.
Use memories subtly, never invent them, and trust the latest user message if facts conflict.
For high-stakes advice, state your limits and suggest qualified real-world help.

MEMORIES
{memory_block}
"""


class AICompanion:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.ai_timeout_seconds))

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _complete(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        model: str | None = None,
    ) -> str:
        if not self._session or self._session.closed:
            await self.start()
        assert self._session is not None
        headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
        primary_model = model or settings.ai_model
        candidates = list(dict.fromkeys((primary_model, settings.fallback_ai_model)))
        for selected_model in candidates:
            payload = {
                "model": selected_model,
                "messages": messages,
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
                "reasoning_effort": "low",
            }
            try:
                async with self._session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        usage = data.get("usage", {})
                        logger.info(
                            "Groq completion model=%s tokens=%s",
                            selected_model,
                            usage.get("total_tokens", "unknown"),
                        )
                        return str(data["choices"][0]["message"]["content"]).strip()
                    body = await response.text()
                    logger.warning(
                        "Groq request failed: model=%s status=%s body=%s",
                        selected_model,
                        response.status,
                        body[:200],
                    )
                    if response.status not in {429, 500, 502, 503, 504}:
                        break
            except (aiohttp.ClientError, TimeoutError):
                logger.warning("Groq request failed for model=%s", selected_model, exc_info=True)
        return ""

    async def reply(
        self,
        *,
        lang: str,
        style: str,
        level: int,
        memories: list[dict],
        history: list[dict],
        user_text: str,
        model: str | None = None,
    ) -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": build_system_prompt(lang, style, memories, level)}]
        for item in history[-18:]:
            role = item.get("role")
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": compact_text(str(item.get("content", "")), 8000)})
        messages.append({"role": "user", "content": compact_text(user_text, 4000)})
        return await self._complete(messages, temperature=0.78, max_tokens=160, model=model)

    async def extract_memories(self, user_text: str) -> list[dict[str, Any]]:
        prompt = """Extract only durable, user-stated facts that improve future conversation.
Allowed: preferences, goals, ongoing projects, important non-sensitive life context, and how the user likes to communicate.
Do not store passwords, account details, exact addresses, financial credentials, health diagnoses, sexual details, or guesses.
Return strict JSON only: {"memories":[{"key":"short_snake_case_key","value":"concise fact","confidence":0.0}]}
If nothing is worth saving, return {"memories":[]}.
"""
        raw = await self._complete(
            [{"role": "system", "content": prompt}, {"role": "user", "content": compact_text(user_text, 4000)}],
            temperature=0.0,
            max_tokens=160,
        )
        try:
            cleaned = raw.removeprefix("```json").removesuffix("```").strip()
            data = json.loads(cleaned)
            memories = data.get("memories", [])
            return memories if isinstance(memories, list) else []
        except (json.JSONDecodeError, AttributeError):
            return []


companion_ai = AICompanion()
