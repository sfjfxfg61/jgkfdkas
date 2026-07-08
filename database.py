import logging
import aiohttp
from config import SUPABASE_URL, SUPABASE_KEY

async def db_upsert_user(user_id: int, username: str, first_name: str, lang: str, ref: str):
    """Быстрое сохранение/обновление юзера без блокировки потока"""
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "lang": lang,
        "ref": ref
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    logging.error(f"Supabase upsert error: {await resp.text()}")
        except Exception as e:
            logging.error(f"Failed to connect to Supabase (upsert): {e}")

async def db_set_paid_status(user_id: int):
    """Фиксация успешной оплаты"""
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, json={"is_paid": True}, headers=headers) as resp:
                if resp.status not in [200, 204]:
                    logging.error(f"Supabase payment update error: {await resp.text()}")
        except Exception as e:
            logging.error(f"Failed to connect to Supabase (payment): {e}")
