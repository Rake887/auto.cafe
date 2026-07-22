# QR-Menu MVP — бэкенд (FastAPI)

Демо SaaS QR-меню для кафе: гость сканирует QR на столе → меню → корзина →
заказ → Telegram-группа заведения → повар «Принял» / «Готово» → официант
«Обслуживаю».

Стек: Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16,
aiogram 3 (webhook). Пакетный менеджер — **uv**.

## Быстрый старт (всё в Docker)

Compose лежит в корне репозитория и поднимает весь стек — БД, API и
фронтенд, см. [../README.md](../README.md):

```bash
cd ..
cp .env.example .env        # при необходимости заполнить BOT_TOKEN и др.
docker compose up -d --build
docker compose --profile tools run --rm seed   # демо-меню и токены столов
```

API поднимется на `http://localhost:8010`, миграции применяются автоматически
при старте контейнера. Swagger UI: **http://localhost:8010/docs** — это же
контракт для фронтендера. Сидинг печатает токены столов, они нужны для
`GET /m/{token}`; повторный запуск ничего не дублирует.

## Локальная разработка (БД в Docker, API на хосте)

```bash
docker compose -f ../docker-compose.yml up -d db   # Postgres на localhost:55433
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --port 8010 --reload
```

Порт 8010 при этом должен быть свободен: если контейнер `api` запущен,
сначала `docker compose -f ../docker-compose.yml stop api`.

## Переменные окружения (.env)

| Переменная | Что это |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://qrmenu:qrmenu@localhost:55433/qrmenu` локально; в compose переопределяется на `db:5432` |
| `BOT_TOKEN` | токен бота от @BotFather. Пустой = бот выключен, API работает без уведомлений |
| `WEBHOOK_URL` | публичный HTTPS-адрес API без хвостового `/`; за прокси это адрес туннеля + `/api` |
| `WEBHOOK_SECRET` | случайная строка; ей подписываются запросы Telegram к вебхуку |
| `GROUP_CHAT_ID` | chat_id общего чата заведения (группа с ботом; id отрицательный) |
| `DEMO_ORGANIZATION_ID` | id демо-организации (создаётся сидингом) |
| `DEMO_TOKEN` | если задан, сидинг выдаст этот токен «Столу 1» — чтобы демо-ссылка не менялась при пересоздании базы. Для реального заведения оставить пустым: токены должны быть случайными |
| `CORS_ORIGINS` | origin фронтенда, `*` для разработки |

При запуске через корневой compose эти переменные приходят из `../.env`,
файл `backend/.env` нужен только для локального запуска без Docker.

## Настройка Telegram-бота

Все переменные — в корневом `.env` (см. [../README.md](../README.md)).

1. Создать бота у @BotFather → токен в `BOT_TOKEN`.
2. Поднять публичный HTTPS-туннель и взять из логов выданный адрес:

   ```bash
   docker compose --profile tunnel-cf up -d cloudflared
   docker compose logs cloudflared | grep -o 'https://[a-z-]*\.trycloudflare\.com'
   ```

   В `WEBHOOK_URL` кладут этот адрес **плюс `/api`** — туннель смотрит на
   прокси, а тот отдаёт бэкенду всё, что начинается с `/api`. Бесплатный
   домен меняется при каждом перезапуске туннеля.
3. `docker compose up -d api` — вебхук ставится сам при старте (`setWebhook`
   на `{WEBHOOK_URL}/telegram/webhook`, с секретом из `WEBHOOK_SECRET` и
   подпиской только на `message`, `callback_query`, `my_chat_member`).
4. Создать группу заведения и добавить в неё бота — он сам напишет туда свой
   `chat_id`. Это значение в `GROUP_CHAT_ID`, затем снова
   `docker compose up -d api`. Если сообщение потерялось, отправьте в чат
   `/chatid`.

Проверить состояние вебхука:

```bash
docker compose exec api python -c "import os,json,urllib.request;t=os.environ['BOT_TOKEN'];print(json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{t}/getWebhookInfo'))['result'])"
```

Запросы без правильного секретного заголовка эндпоинт отвергает с 403.
Если хендлер падает, вебхук всё равно отвечает 200 — иначе Telegram будет
повторять один и тот же апдейт по кругу.

## Сценарий целиком руками (curl)

Ниже `TOKEN` — токен стола из вывода сидинга.

**1. Гость открывает меню** (это и есть «скан QR»):

```bash
curl http://localhost:8010/m/TOKEN
```

**2. Гость оформляет заказ** (`client_request_id` генерирует фронт один раз
на корзину — повторный запрос с тем же id не создаст дубль):

```bash
curl -X POST http://localhost:8010/orders \
  -H "Content-Type: application/json" \
  -d '{
    "point_token": "TOKEN",
    "client_request_id": "11111111-1111-1111-1111-111111111111",
    "items": [{"dish_id": 1, "qty": 2}, {"dish_id": 9, "qty": 1}],
    "comment": "без лука"
  }'
# -> {"order_id": 1, "status": "new", "total": 5800}
```

Комментарий необязателен и попадает в сообщение кухне отдельной строкой.
Позвать официанта к столу — `POST /calls` с телом `{"point_token": "TOKEN"}`;
повторный вызов с того же стола в течение минуты получает 429.

Цены клиент не присылает — сервер берёт их из БД и фиксирует снапшотами.

**3. Гость поллит статус** (фронт делает это раз в 3–5 сек):

```bash
curl http://localhost:8010/orders/1
```

**4. В Telegram-группу пришло сообщение с заказом.** Повар жмёт
`[✅ Принял]` → статус `accepted`, сообщение редактируется, появляется
`[🍽 Готово]`. Повар жмёт `[Готово]` → статус `ready`, официантам приходит
новое сообщение «Заказ готов» с кнопкой `[🙋 Обслуживаю]`. Официант жмёт её →
статус `served`, цикл завершён. Вся история — в таблице `order_status_log`.

**5. Регистрация сотрудника в боте** (чтобы в чате отображались имя и роль):
обычно это делается в кабинете, `/admin/staff`. Тем же занят и API — он под
админ-доступом, потому что ссылка-приглашение даёт человеку кнопки кухни:

```bash
curl -X POST "http://localhost:8010/admin/staff?token=$ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Айбек Кулов", "role": "cook"}'
# -> {"staff_id": 1, "invite_token": "...", "deep_link": "https://t.me/<bot>?start=..."}
```

Сотрудник открывает `deep_link` → жмёт Start → зарегистрирован. Токен
одноразовый. Уволенному (`DELETE /admin/staff/{id}`) ссылка перестаёт
работать, а его имя остаётся в прошлой статистике.

## Что отдать фронтендеру

- Swagger: `http://localhost:8010/docs`
- Базовый URL API: `http://localhost:8010`
- Токен тестового стола — из вывода `python -m app.seed`

## Структура проекта

```
app/
  main.py        # FastAPI app, CORS, lifespan (setWebhook)
  core/          # config (pydantic-settings), db (async engine/session)
  models/        # SQLAlchemy 2.0: organization..order_status_log
  schemas/       # Pydantic-схемы = OpenAPI-контракт
  api/           # роутеры: menu, orders, staff, telegram(webhook)
  services/      # бизнес-логика: меню, заказы+идемпотентность, уведомления
  bot/           # aiogram: инстанс бота и хендлеры кнопок
  seed.py        # демо-данные (python -m app.seed)
alembic/         # миграции (генерируются autogenerate)
```
