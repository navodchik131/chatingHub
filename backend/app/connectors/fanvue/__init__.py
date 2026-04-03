"""
Коннектор Fanvue: вебхук входящих сообщений и отправка ответов через REST API.

- Вебхук: ``POST /api/connectors/fanvue/webhook`` (подпись ``X-Fanvue-Signature``).
- Отправка: ``POST https://api.fanvue.com/chats/{fanUserUuid}/message`` (Bearer).
"""
