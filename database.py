import logging
import aiohttp
from config import SUPABASE_URL, SUPABASE_KEY

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

async def db_upsert_user(user_id: int, username: str, first_name: str, lang: str, ref: str):
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = get_headers()
    headers["Prefer"] = "resolution=merge-duplicates"
    
    payload = {
        "user_id": user_id,
        "username": username[:32] if username else None,
        "first_name": first_name[:64] if first_name else "User",
        "lang": lang[:2],
        "ref": ref[:50] if ref else "direct"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    logging.error(f"Supabase upsert error: {await resp.text()}")
        except Exception as e:
            logging.error(f"Failed to upsert user {user_id}: {e}")

async def db_set_paid_status(user_id: int, status: bool = True):
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, json={"is_paid": status}, headers=get_headers()) as resp:
                if resp.status not in [200, 204]:
                    logging.error(f"Supabase patch status error: {await resp.text()}")
        except Exception as e:
            logging.error(f"Failed to update paid status for {user_id}: {e}")

async def db_get_stats():
    url = f"{SUPABASE_URL}/rest/v1/users?select=is_paid,ref"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=get_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    total = len(data)
                    paid = sum(1 for x in data if x.get("is_paid"))
                    
                    refs = {}
                    for x in data:
                        r = x.get("ref", "direct")
                        refs[r] = refs.get(r, 0) + 1
                    return {"total": total, "paid": paid, "refs": refs}
        except Exception as e:
            logging.error(f"Stats retrieval failed: {e}")
    return None

async def db_get_unpaid_users():
    url = f"{SUPABASE_URL}/rest/v1/users?is_paid=eq.false&select=user_id,lang"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=get_headers()) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logging.error(f"Unpaid users fetch failed: {e}")
    return []

async def db_get_user(user_id: int):
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}&select=*"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=get_headers()) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    return res[0] if res else None
        except Exception as e:
            logging.error(f"Fetch user failed: {e}")
    return None

async def db_delete_user(user_id: int):
    """Полное удаление неактивного юзера (Очистка БД)"""
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(url, headers=get_headers()) as resp:
                if resp.status not in [200, 204]:
                    logging.error(f"Supabase delete user error: {await resp.text()}")
        except Exception as e:
            logging.error(f"Failed to delete user {user_id}: {e}")
