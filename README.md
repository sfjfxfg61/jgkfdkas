# Victoria v11

Начни с **START_HERE.md**. SQL для установки и обновления: **V11_SETUP.sql**.

Python 3.11+, aiogram 3.31.0, Supabase, manual-first Telegram Stars bot.

```bash
pip install -r requirements.txt
python main.py
```

Секреты задаются через environment. Пример — `.env.example` (сам по себе не загружается кодом). В production нужен постоянный диск для STATE_DIR и один постоянно работающий polling-процесс. Параметры Render — в render.yaml.

Проверки:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
cd sql-tests
npm install
npm test
```

Старые отчёты V10_* оставлены как исторические материалы; актуальный порядок запуска находится в START_HERE.md. Никакой автоматической публикации, изменения текущей БД или настройки тарифов Render этот архив не выполняет.
