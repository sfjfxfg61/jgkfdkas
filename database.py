# database.py
import aiosqlite
import os
import logging

DB_PATH = "bot_database.db"

async def init_db():
    """Инициализация базы данных, создание таблиц и индексов для мгновенного поиска"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                lang TEXT DEFAULT 'en',
                ref TEXT DEFAULT 'direct',
                is_paid INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Индекс для быстрой фильтрации неоплативших пользователей при рассылках и чистке
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_unpaid ON users (is_paid)")
        # Индекс для аналитики по рефералам
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_ref ON users (ref)")
        
        await db.commit()
    logging.info("Database initialized successfully with indexes.")

async def db_upsert_user(user_id: int, username: str, first_name: str, lang: str, ref: str):
    """Безопасное добавление или обновление данных пользователя (ON CONFLICT)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, lang, ref)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                lang = excluded.lang
        """, (user_id, username, first_name, lang, ref))
        await db.commit()

async def db_get_user(user_id: int) -> dict:
    """Мгновенное получение карточки пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def db_set_paid_status(user_id: int, is_paid: bool):
    """Обновление статуса оплаты"""
    status = 1 if is_paid else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_paid = ? WHERE user_id = ?", (status, user_id))
        await db.commit()

async def db_get_unpaid_users() -> list:
    """Быстрая выгрузка всех неоплативших пользователей (для дожимов, рассылок и чистки)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id, lang FROM users WHERE is_paid = 0") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def db_delete_user(user_id: int):
    """Удаление 'мертвых душ' (пользователей, заблокировавших бота)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()

async def db_get_stats() -> dict:
    """Сбор моментальной статистики по воронке и рефералам за один проход"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Общие показатели
        async with db.execute("SELECT COUNT(*) as total, SUM(CASE WHEN is_paid = 1 THEN 1 ELSE 0 END) as paid FROM users") as cursor:
            res = await cursor.fetchone()
            total = res["total"] or 0
            paid = res["paid"] or 0

        # Статистика по реферальным источникам
        refs = {}
        async with db.execute("SELECT ref, COUNT(*) as cnt FROM users GROUP BY ref ORDER BY cnt DESC") as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                refs[r["ref"]] = r["cnt"]

        return {
            "total": total,
            "paid": paid,
            "refs": refs
        }
