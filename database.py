# database.py
import aiohttp
import logging
import config

# Базовые заголовки для работы с Supabase REST API
HEADERS = {
    "apikey": config.SUPABASE_KEY,
    "Authorization": f"Bearer {config.SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# Ссылка на REST-интерфейс таблиц в Supabase
TABLE_URL = f"{config.SUPABASE_URL}/rest/v1/users"

async def init_db():
    """
    Для Supabase инициализация таблиц через код не требуется, 
    так как таблица 'users' и индексы уже созданы тобой через SQL-запрос.
    """
    logging.info("Supabase PostgreSQL connection configured and active.")

async def db_upsert_user(user_id: int, username: str, first_name: str, lang: str, ref: str):
    """Добавление или обновление пользователя в Supabase (ON CONFLICT)"""
    url = f"{TABLE_URL}?on_conflict=user_id"
    payload = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "lang": lang[:2],  # Обрезаем до 2 символов согласно VARCHAR(2)
        "ref": ref[:50]    # Обрезаем до 50 символов согласно VARCHAR(50)
    }
    
    # Добавляем заголовок для выполнения UPSERT (обновления при конфликте)
    headers = HEADERS.copy()
    headers["Prefer"] = "resolution=merge-duplicates"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as r:
                if r.status not in [200, 201, 204]:
                    text = await r.text()
                    logging.error(f"Supabase upsert error: {r.status} - {text}")
        except Exception as e:
            logging.error(f"Failed to connect to Supabase: {e}")

async def db_get_user(user_id: int) -> dict:
    """Получение пользователя из Supabase по его ID"""
    url = f"{TABLE_URL}?user_id=eq.{user_id}&select=*"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS) as r:
                if r.status == 200:
                    data = await r.json()
                    return data[0] if data else None
        except Exception as e:
            logging.error(f"Supabase get_user error: {e}")
    return None

async def db_set_paid_status(user_id: int, is_paid: bool):
    """Обновление статуса оплаты пользователя в Supabase (тип BOOLEAN)"""
    url = f"{TABLE_URL}?user_id=eq.{user_id}"
    # Отправляем чистый Python-boolean (True/False), который aiohttp конвертирует в JSON true/false
    payload = {"is_paid": is_paid}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, json=payload, headers=HEADERS) as r:
                if r.status not in [200, 204]:
                    text = await r.text()
                    logging.error(f"Supabase set_paid error: {r.status} - {text}")
        except Exception as e:
            logging.error(f"Supabase patch request failed: {e}")

async def db_get_unpaid_users() -> list:
    """
    Получение списка всех неоплативших пользователей для рассылки дожимов.
    Использует созданный тобой индекс idx_users_unpaid (is_paid = false).
    """
    url = f"{TABLE_URL}?is_paid=eq.false&select=user_id,lang"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS) as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            logging.error(f"Supabase get_unpaid_users error: {e}")
    return []

async def db_delete_user(user_id: int):
    """Удаление пользователя (если он заблокировал бота)"""
    url = f"{TABLE_URL}?user_id=eq.{user_id}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(url, headers=HEADERS) as r:
                if r.status not in [200, 204]:
                    text = await r.text()
                    logging.error(f"Supabase delete user error: {r.status} - {text}")
        except Exception as e:
            logging.error(f"Supabase delete connection error: {e}")

async def db_get_stats() -> dict:
    """Сбор статистики по пользователям напрямую из Supabase"""
    url = f"{TABLE_URL}?select=is_paid,ref"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=HEADERS) as r:
                if r.status == 200:
                    users = await r.json()
                    
                    total = len(users)
                    # Считаем тех, у кого is_paid равен True
                    paid = sum(1 for u in users if u.get("is_paid") is True)
                    
                    # Считаем реферальные переходы из TikTok
                    refs = {}
                    for u in users:
                        ref_name = u.get("ref") or "direct"
                        refs[ref_name] = refs.get(ref_name, 0) + 1
                        
                    return {
                        "total": total,
                        "paid": paid,
                        "refs": refs
                    }
        except Exception as e:
            logging.error(f"Supabase get_stats error: {e}")
            
    return {"total": 0, "paid": 0, "refs": {}}
