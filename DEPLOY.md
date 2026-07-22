# Установка на сервер

Инструкция для боевого запуска в кафе: постоянный домен, HTTPS, автоматические
бэкапы. После неё напечатанные QR-наклейки живут вечно — в отличие от временных
адресов туннеля, которые меняются при каждом перезапуске.

## 1. Сервер и домен

VPS в Казахстане — так база с данными гостей физически остаётся в стране
(требование закона о персональных данных). Хватит машины с 2 ГБ памяти.

Домен направьте на сервер A-записью:

```
menu.example.kz.   A   203.0.113.10
```

Проверить, что запись разошлась: `nslookup menu.example.kz`. Пока домен не
указывает на сервер, Caddy не сможет получить сертификат.

## 2. Установка

```bash
# на сервере, под обычным пользователем с правами sudo
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

git clone <адрес-репозитория> qrmenu && cd qrmenu
cp .env.prod.example .env.prod
```

Заполните `.env.prod`: домен, почту, пароль базы, токен бота, секрет вебхука.
Пароль и секрет удобно сгенерировать так:

```bash
openssl rand -base64 24
```

## 3. Первый запуск

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Миграции применяются сами. Дальше — демо-меню (можно пропустить, если сразу
зальёте своё через админку) и учётная запись владельца:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  --profile tools run --rm seed

docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec api python -m app.create_admin
```

Сертификат Caddy получает при первом обращении к домену — откройте
`https://menu.example.kz`, первая загрузка может занять несколько секунд.

## 4. Telegram

`WEBHOOK_URL` на проде не нужен в `.env.prod`: он собирается из домена
(`https://<домен>/api`) прямо в compose-файле, и приложение регистрирует
вебхук при старте. Дальше как обычно: добавьте бота в группу заведения, он
напишет туда свой `chat_id`, впишите его в `GROUP_CHAT_ID` и перезапустите API:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d api
```

## 5. Наклейки на столы

Зайдите в `/admin`, раздел «QR для печати». На проде токены столов случайные
(`DEMO_TOKEN` пуст), адрес постоянный — печатайте один раз и ламинируйте.

## 6. Бэкап базы

Данные лежат в томе `pgdata`, но том — не бэкап: он умрёт вместе с сервером.
Ежедневная выгрузка в 3 часа ночи с хранением за две недели:

```bash
mkdir -p ~/backups
crontab -e
```

```cron
0 3 * * * cd ~/qrmenu && docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db pg_dump -U qrmenu qrmenu | gzip > ~/backups/qrmenu-$(date +\%F).sql.gz && find ~/backups -name 'qrmenu-*.sql.gz' -mtime +14 -delete
```

Восстановление:

```bash
gunzip -c ~/backups/qrmenu-2026-07-22.sql.gz | \
  docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db psql -U qrmenu qrmenu
```

Фотографии блюд лежат в томе `media` — их стоит копировать отдельно:

```bash
docker run --rm -v qrmenu_media:/data -v ~/backups:/backup alpine \
  tar czf /backup/media-$(date +%F).tar.gz -C /data .
```

## 7. Обновление версии

```bash
cd ~/qrmenu && git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Миграции накатятся сами при старте. Перед обновлением полезно снять бэкап
командой из пункта 6.

## Проверка после установки

- `https://<домен>/m/<токен стола>` открывается с телефона по мобильному
  интернету, замок в адресной строке зелёный;
- `/admin/login` пускает по паролю, статистика и меню открываются;
- в `/admin/settings` заданы часы приёма заказов — иначе заказ примут и ночью;
- заказ со стола прилетает в группу, кнопки «Принял» и «Готово» работают;
- `docker compose -f docker-compose.prod.yml --env-file .env.prod ps` —
  все контейнеры `healthy`.
