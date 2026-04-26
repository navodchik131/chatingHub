"""
Коннектор Fanvue: вебхук входящих сообщений и отправка ответов через REST API.

- Вебхук (SaaS): ``POST /api/webhooks/fanvue/{secret}`` (подпись ``X-Fanvue-Signature``).
- Отправка: ``POST https://api.fanvue.com/chats/{fanUserUuid}/message`` (Bearer из БД).
"""
