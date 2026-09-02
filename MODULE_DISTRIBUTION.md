# 📦 Как создать ZIP модуля для распространения

Требования к манифесту и API ядра: [MODULES_DOCUMENTATION.md](MODULES_DOCUMENTATION.md). Индекс документации: [DOCUMENTATION.md](DOCUMENTATION.md).

## Шаг 1: Подготовьте директорию модуля

```bash
modules/
  my_awesome_module/
    __init__.py
    bot_handlers.py
    db_schema.py
    settings_schema.py
    README.md
    LICENSE
```

## Шаг 2: Создайте ZIP архив

**Linux/Mac:**
```bash
cd modules
zip -r my_awesome_module.zip my_awesome_module/
```

**Windows (PowerShell):**
```powershell
Compress-Archive -Path ".\modules\my_awesome_module" -DestinationPath "my_awesome_module.zip"
```

**Windows (7-Zip):**
- Кликните правой кнопкой на папку `my_awesome_module`
- 7-Zip → Add to archive
- Установите формат ZIP
- Убедитесь, что компрессия включена

## Шаг 3: Проверьте структуру ZIP

Архив должен содержать:
```
my_awesome_module/
├── __init__.py
├── bot_handlers.py
├── db_schema.py
├── settings_schema.py
└── ...
```

❌ **Неправильно:**
```
__init__.py  ← файлы напрямую, без директории!
bot_handlers.py
```

## Шаг 4: Загрузите в админ-панель

1. Войдите в админ-панель панель
2. 🧩 Модули → 📦 Загрузить новый модуль
3. Выберите `my_awesome_module.zip`
4. Нажмите **Загрузить и установить**

✅ Готово! Модуль будет автоматически:
- Распакован в `modules/`
- Валидирован
- Включен
- Доступен в боте

## Структура минимального модуля

**__init__.py:**
```python
from shop_bot.core.module_types import ModuleMeta

MODULE_META = ModuleMeta(
    id="my_awesome_module",
    name="My Awesome Module",
    version="1.0.0",
    description="Don't forget to describe me!",
    author="Your Name",
    bot_entry="bot_handlers",  # если есть обработчики
)
```

**bot_handlers.py:**
```python
from aiogram import Router, types

router = Router()

@router.message()
async def my_handler(message: types.Message):
    await message.answer("🎉 Модуль работает!")
```

## Версионирование модулей

Используйте [семантическое версионирование](https://semver.org/lang/ru/):
- `1.0.0` - первый релиз
- `1.1.0` - добавлена новая функция
- `1.0.1` - исправлена ошибка

## Совместимость

Убедитесь, что модуль совместим с:
- Python 3.11+
- aiogram 3.0+
- Flask 2.3+

Если у модуля есть внешние зависимости, опишите их в `README.md`.

## Распространение

Рекомендуется:
1. Опубликовать модуль на GitHub
2. Добавить в README:
   - Описание функционала
   - Требования и зависимости
   - Скриншоты
   - Инструкции по установке (просто: загрузить ZIP)
   - Лицензию

Пример README:
```markdown
# My Awesome Module

Краткое описание.

## Установка

1. Завантажьте [last_release.zip](https://github.com/your-repo/releases)
2. В админ-панели: 🧩 Модули → 📦 Загрузить новый модуль
3. Выберите ZIP и нажмите Загрузить

## Требования

- Python 3.11+
- Xatabchik v2.0+

## Лицензия

MIT
```

## Дебаггинг

Если модуль не загружается:

1. **Проверьте структуру ZIP:**
   ```bash
   unzip -l my_awesome_module.zip | head -20
   ```

2. **Проверьте наличие __init__.py:**
   ```
   my_awesome_module/__init__.py  ← должна быть
   ```

3. **Проверьте панель логов:**
   В контейнере Docker:
   ```bash
   docker logs xatabchik | grep "Module\|import\|error" -i
   ```

4. **Проверьте статус в админ-панели:**
   Если статус "Ошибка", кликните на модуль чтобы увидеть сообщение об ошибке
