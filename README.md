# Telegram-нотификатор заявок

Готовый сервис для Railway. Принимает `POST /notify` с секретом и отправляет заявку в один Telegram-чат. Подключение Facebook Lead Ads выполняется отдельно: в текущей версии нет прямого соединения с Meta.

## Запуск

1. В Telegram откройте [@BotFather](https://t.me/BotFather), отправьте `/newbot`, задайте имя и username. Скопируйте токен.
2. Создайте репозиторий GitHub с этими файлами. В Railway создайте проект из этого репозитория. Railway найдёт `Dockerfile`.
3. В Variables сервиса Railway добавьте `TELEGRAM_BOT_TOKEN` (токен BotFather) и `NOTIFY_SECRET` (длинная случайная строка). Разверните сервис.
4. Откройте бота в Telegram и отправьте `/start`. Он пришлёт ID чата. Для группы добавьте туда бота и отправьте `/start` в группе. При необходимости отключите privacy mode у BotFather, если команда в группе не видна; также можно отправить `/start@ИмяБота`.
5. Добавьте полученный ID в Variables как `TELEGRAM_CHAT_ID` и примените изменения Railway. Команда `/test` проверяет отправку в текущий чат. В Railway создайте публичный домен для сервиса, если нужно вызывать `/notify` извне.

`TELEGRAM_CHAT_ID` можно оставить пустым на первом запуске, чтобы получить ID через `/start`. Без него `/notify` возвращает `503`.

## Проверка точки приёма

```bash
curl -X POST 'https://YOUR-DOMAIN/notify' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_NOTIFY_SECRET' \
  -d '{"name":"Тестовая заявка","phone":"+380000000000","project":"Демо","source":"Facebook"}'
```

Поддерживаются поля `name`, `phone`, `email`, `project`, `campaign`, `form`, `source`, `message` и объект `fields` для дополнительных ответов. Заявка отправляется только в чат из `TELEGRAM_CHAT_ID`. Секрет передавайте только серверу, который интегрирует Facebook; не размещайте его в браузерном коде. Сервис рассчитан на **одну реплику** из-за Telegram long polling.

## Локальный запуск

```bash
TELEGRAM_BOT_TOKEN='...' TELEGRAM_CHAT_ID='...' NOTIFY_SECRET='...' python3 main.py
```

Проверка доступности: `GET /health` возвращает `{"ok": true}`. Порт берётся из `PORT`, по умолчанию 8080.
