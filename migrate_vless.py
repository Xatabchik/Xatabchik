#!/usr/bin/env python3
"""
Скрипт для запуска миграции БД - добавление поля vless_output_enabled
"""
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(__file__))

try:
    from src.shop_bot.data_manager.database import run_migration
    
    print("🔄 Запуск миграции БД...")
    run_migration()
    print("✅ Миграция завершена успешно!")
    print("✨ Поле 'vless_output_enabled' добавлено в таблицу xui_hosts")
    
except Exception as e:
    print(f"❌ Ошибка при выполнении миграции: {e}")
    sys.exit(1)
