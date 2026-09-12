"""Инструкции по подключению для Android, iOS, Windows и Linux.
"""

from aiogram import (
    Router,
    F,
    types,
)
from aiogram.exceptions import TelegramBadRequest
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import get_setting

__all__: list[str] = []


def register_howto(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.callback_query(F.data.startswith("howto_vless_"))
    @registration_required
    async def show_instruction_handler(callback: types.CallbackQuery):
        await callback.answer()
        key_id = int(callback.data.split("_")[2])

        intro_text = get_setting("howto_intro_text") or "Выберите вашу платформу для инструкции по подключению VLESS:"
        await callback.message.edit_text(
            intro_text,
            reply_markup=keyboards.create_howto_vless_keyboard_key(key_id),
            disable_web_page_preview=True
        )
    
    @user_router.callback_query(F.data.startswith("howto_vless"))
    @registration_required
    async def show_instruction_handler(callback: types.CallbackQuery):
        await callback.answer()

        intro_text = get_setting("howto_intro_text") or "Выберите вашу платформу для инструкции по подключению VLESS:"
        await callback.message.edit_text(
            intro_text,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data == "howto_android")
    @registration_required
    async def howto_android_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_android_text") or (
            "<b>Подключение на Android</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из Google Play Store.\n"
            "2. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "   • Откройте V2RayTun.\n"
            "   • Нажмите на значок + в правом нижнем углу.\n"
            "   • Выберите «Импортировать конфигурацию из буфера обмена» (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Нажмите на кнопку подключения (значок «V» или воспроизведения). Возможно, потребуется разрешение на создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard()

        current_text = callback.message.text or ""
        current_markup = callback.message.reply_markup

        if current_markup and hasattr(current_markup, "model_dump"):
            current_markup_dump = current_markup.model_dump()
        else:
            current_markup_dump = current_markup

        if markup and hasattr(markup, "model_dump"):
            new_markup_dump = markup.model_dump()
        else:
            new_markup_dump = markup

        if current_text == text and current_markup_dump == new_markup_dump:
            return

        try:
            await callback.message.edit_text(
                text,
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise
            logger.debug(
                "Skipping edit_text for howto_android_handler: message is not modified"
            )

    @user_router.callback_query(F.data.startswith("howto_android_"))
    @registration_required
    async def howto_android_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_android_text") or (
            "<b>Подключение на Android</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из Google Play Store.\n"
            "2. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "    Откройте V2RayTun.\n"
            "    Нажмите на значок + в правом нижнем углу.\n"
            "    Выберите <Импортировать конфигурацию из буфера обмена> (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Нажмите на кнопку подключения (значок <V> или воспроизведения). Возможно, потребуется разрешение на создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise

    @user_router.callback_query(F.data == "howto_ios")
    @registration_required
    async def howto_ios_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_ios_text") or (
            "<b>Подключение на iOS (iPhone/iPad)</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из App Store.\n"
            "2. <b>Скопируйте свой ключ (vless://):</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "   • Откройте V2RayTun.\n"
            "   • Нажмите на значок +.\n"
            "   • Выберите «Импортировать конфигурацию из буфера обмена» (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Включите главный переключатель в V2RayTun. Возможно, потребуется разрешить создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data.startswith("howto_ios_"))
    @registration_required
    async def howto_ios_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_ios_text") or (
            "<b>Подключение на iOS (iPhone/iPad)</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из App Store.\n"
            "2. <b>Скопируйте свой ключ (vless://):</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "    Откройте V2RayTun.\n"
            "    Нажмите на значок +.\n"
            "    Выберите <Импортировать конфигурацию из буфера обмена> (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Включите главный переключатель в V2RayTun. Возможно, потребуется разрешить создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise

    @user_router.callback_query(F.data == "howto_windows")
    @registration_required
    async def howto_windows_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_windows_text") or (
            "<b>Подключение на Windows</b>\n\n"
            "1. <b>Установите приложение Nekoray:</b> Загрузите Nekoray с https://github.com/MatsuriDayo/Nekoray/releases. Выберите подходящую версию (например, Nekoray-x64.exe).\n"
            "2. <b>Распакуйте архив:</b> Распакуйте скачанный архив в удобное место.\n"
            "3. <b>Запустите Nekoray.exe:</b> Откройте исполняемый файл.\n"
            "4. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "5. <b>Импортируйте конфигурацию:</b>\n"
            "   • В Nekoray нажмите «Сервер» (Server).\n"
            "   • Выберите «Импортировать из буфера обмена».\n"
            "   • Nekoray автоматически импортирует конфигурацию.\n"
            "6. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите «Серверы» → «Обновить все серверы».\n"
            "7. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "8. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "9. <b>Подключитесь к VPN:</b> Нажмите «Подключить» (Connect).\n"
            "10. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard()

        current_text = callback.message.text or ""
        current_markup = callback.message.reply_markup

        if current_markup and hasattr(current_markup, "model_dump"):
            current_markup_dump = current_markup.model_dump()
        else:
            current_markup_dump = current_markup

        if markup and hasattr(markup, "model_dump"):
            new_markup_dump = markup.model_dump()
        else:
            new_markup_dump = markup

        if current_text == text and current_markup_dump == new_markup_dump:
            return

        try:
            await callback.message.edit_text(
                text,
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise
            logger.debug(
                "Skipping edit_text for howto_windows_handler: message is not modified"
            )

    @user_router.callback_query(F.data.startswith("howto_windows_"))
    @registration_required
    async def howto_windows_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_windows_text") or (
            "<b>Подключение на Windows</b>\n\n"
            "1. <b>Установите приложение Nekoray:</b> Загрузите Nekoray с https://github.com/MatsuriDayo/Nekoray/releases. Выберите подходящую версию (например, Nekoray-x64.exe).\n"
            "2. <b>Распакуйте архив:</b> Распакуйте скачанный архив в удобное место.\n"
            "3. <b>Запустите Nekoray.exe:</b> Откройте исполняемый файл.\n"
            "4. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "5. <b>Импортируйте конфигурацию:</b>\n"
            "    В Nekoray нажмите <Сервер> (Server).\n"
            "    Выберите <Импортировать из буфера обмена>.\n"
            "    Nekoray автоматически импортирует конфигурацию.\n"
            "6. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите <Серверы>  <Обновить все серверы>.\n"
            "7. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "8. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "9. <b>Подключитесь к VPN:</b> Нажмите <Подключить> (Connect).\n"
            "10. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise

    @user_router.callback_query(F.data == "howto_linux")
    @registration_required
    async def howto_linux_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_linux_text") or (
            "<b>Подключение на Linux</b>\n\n"
            "1. <b>Скачайте и распакуйте Nekoray:</b> Перейдите на https://github.com/MatsuriDayo/Nekoray/releases и скачайте архив для Linux. Распакуйте его в удобную папку.\n"
            "2. <b>Запустите Nekoray:</b> Откройте терминал, перейдите в папку с Nekoray и выполните <code>./nekoray</code> (или используйте графический запуск, если доступен).\n"
            "3. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "4. <b>Импортируйте конфигурацию:</b>\n"
            "   • В Nekoray нажмите «Сервер» (Server).\n"
            "   • Выберите «Импортировать из буфера обмена».\n"
            "   • Nekoray автоматически импортирует конфигурацию.\n"
            "5. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите «Серверы» → «Обновить все серверы».\n"
            "6. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "7. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "8. <b>Подключитесь к VPN:</b> Нажмите «Подключить» (Connect).\n"
            "9. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data.startswith("howto_linux_"))
    @registration_required
    async def howto_linux_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_linux_text") or (
            "<b>Подключение на Linux</b>\n\n"
            "1. <b>Скачайте и распакуйте Nekoray:</b> Перейдите на https://github.com/MatsuriDayo/Nekoray/releases и скачайте архив для Linux. Распакуйте его в удобную папку.\n"
            "2. <b>Запустите Nekoray:</b> Откройте терминал, перейдите в папку с Nekoray и выполните <code>./nekoray</code> (или используйте графический запуск, если доступен).\n"
            "3. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "4. <b>Импортируйте конфигурацию:</b>\n"
            "    В Nekoray нажмите <Сервер> (Server).\n"
            "    Выберите <Импортировать из буфера обмена>.\n"
            "    Nekoray автоматически импортирует конфигурацию.\n"
            "5. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите <Серверы>  <Обновить все серверы>.\n"
            "6. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "7. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "8. <b>Подключитесь к VPN:</b> Нажмите <Подключить> (Connect).\n"
            "9. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise
