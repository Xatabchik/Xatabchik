#!/usr/bin/env python3
"""
Инвалидация всех persistent webapp auth_token в таблице users.

Зачем: старый эндпоинт POST /api/auth/telegram-direct выдавал токен по голому
user_id без проверки Telegram initData (CWE-306). Любые ранее выданные
auth_token могли быть скомпрометированы. Этот скрипт перезаписывает каждый
непустой auth_token новым случайным UUID4 — старые сессии перестают работать.

Запуск (из корня репозитория, с настроенным DB_FILE / как у бота):

    python migrate_invalidate_auth_tokens.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from shop_bot.data_manager.database import invalidate_all_user_auth_tokens, DB_FILE

    print(f"DB: {DB_FILE}")
    print("Инвалидация всех auth_token пользователей...")
    updated = invalidate_all_user_auth_tokens()
    print(f"Готово. Обновлено записей: {updated}")
    print("Пользователям потребуется повторный вход в webapp.")
except Exception as e:
    print(f"Ошибка: {e}", file=sys.stderr)
    sys.exit(1)
