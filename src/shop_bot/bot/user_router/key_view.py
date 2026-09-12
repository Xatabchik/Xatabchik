"""Пробный период, карточка ключа, автопродление, смена сервера и устройства.
"""

import qrcode
from html import escape as html_escape
from io import BytesIO
from datetime import (
    datetime,
    timedelta,
)
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.types import BufferedInputFile
from aiogram.fsm.context import FSMContext
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    get_user,
    get_next_key_number,
    get_user_keys,
    get_plan_by_id,
    get_all_hosts,
    set_trial_used,
)
from shop_bot.config import (
    get_key_info_text,
    get_purchase_success_text,
)
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager import database
from shop_bot.modules import remnawave_api
from shop_bot.data_manager.database import delete_key_by_id

__all__: list[str] = []


def register_key_view(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    # =============================
    # Trial period
    # =============================

    @user_router.callback_query(F.data == "get_trial")
    @registration_required
    async def trial_period_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        if user_db_data and user_db_data.get('trial_used'):
            await callback.answer("Вы уже использовали бесплатный пробный период.", show_alert=True)
            return

        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для создания пробного ключа.")
            return

        # Если в настройках задан хост по умолчанию — пропускаем выбор
        default_host = (get_setting("trial_default_host") or "").strip()
        if default_host and any(h['host_name'] == default_host for h in hosts):
            await callback.answer()
            await process_trial_key_creation(callback.message, default_host)
            return

        if len(hosts) == 1:
            await callback.answer()
            await process_trial_key_creation(callback.message, hosts[0]['host_name'])
        else:
            await callback.answer()
            await callback.message.edit_text(
                "Вариант подключения:",
                reply_markup=keyboards.create_host_selection_keyboard(hosts, action="trial")
            )

    @user_router.callback_query(F.data.startswith("select_host_trial_"))
    @registration_required
    async def trial_host_selection_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_trial_"):]
        await process_trial_key_creation(callback.message, host_name)

    async def process_trial_key_creation(message: types.Message, host_name: str):
        user_id = message.chat.id
        await message.edit_text(
            f"Отлично! Создаю для вас бесплатный ключ на {get_setting('trial_duration_days')} дня "
            f"(вариант подключения «{host_name}»)..."
        )

        try:

            try:
                candidate_email = rw_repo.generate_key_email_for_user(user_id)
            except Exception:
                candidate_email = f"{user_id}-{int(datetime.now().timestamp())}@bot.local"

            # --- Trial limits (optional) ---
            traffic_limit_bytes = None
            hwid_device_limit = None
            try:
                raw_gb = (get_setting('trial_traffic_limit_gb') or '').strip()
                if raw_gb:
                    gb = float(raw_gb.replace(',', '.'))
                    if gb > 0:
                        traffic_limit_bytes = int(gb * 1024 * 1024 * 1024)
            except Exception:
                traffic_limit_bytes = None

            try:
                raw_dev = (get_setting('trial_device_limit') or '').strip()
                if raw_dev:
                    dev = int(float(raw_dev.replace(',', '.')))
                    if dev > 0:
                        hwid_device_limit = dev
            except Exception:
                hwid_device_limit = None

            try:
                result = await remnawave_api.create_or_update_key_on_host(
                    host_name=host_name,
                    email=candidate_email,
                    days_to_add=int(get_setting("trial_duration_days")),
                    traffic_limit_bytes=traffic_limit_bytes,
                    traffic_limit_strategy='NO_RESET' if traffic_limit_bytes is not None else None,
                    hwid_device_limit=hwid_device_limit,
                    raise_on_error=True,
                )
            except Exception as exc:
                await _handle_key_creation_failure(
                    message.bot,
                    user_id=user_id,
                    action_label=_format_key_action_label("trial"),
                    exc=exc,
                    refund=False,
                )
                try:
                    await message.edit_text("❌ Не удалось создать ключ.")
                except Exception:
                    pass
                return
            if not result:
                await _handle_key_creation_failure(
                    message.bot,
                    user_id=user_id,
                    action_label=_format_key_action_label("trial"),
                    exc=RuntimeError("trial key creation returned empty response"),
                    refund=False,
                )
                try:
                    await message.edit_text("❌ Не удалось создать ключ.")
                except Exception:
                    pass
                return

            set_trial_used(user_id)

            # +1 день рефереру начисляем только после успешного создания триал-ключа.
            try:
                await grant_referrer_day_bonus_for_trial(referred_user_id=user_id, bot=message.bot)
            except Exception:
                pass

            # Persist origin info so "🕒 Тариф" shows "триал".
            try:
                td = int(get_setting("trial_duration_days") or 0)
            except Exception:
                td = 0
            origin_desc = _build_key_origin_meta(
                source="trial",
                plan_id=None,
                plan_name="trial",
                months=0,
                duration_days=td,
                is_trial=True,
            )
            new_key_id = rw_repo.record_key_from_payload(
                user_id=user_id,
                payload=result,
                host_name=host_name,
                tag="trial",
                description=origin_desc,
            )
            
            await message.delete()
            new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
            final_text = get_purchase_success_text("new", get_next_key_number(user_id) -1, new_expiry_date, result['connection_string'])
            await message.answer(text=final_text, reply_markup=keyboards.create_key_info_keyboard(new_key_id, result.get('connection_string')))

        except Exception as e:
            logger.error(f"Error creating trial key for user {user_id} on host {host_name}: {e}", exc_info=True)
            await message.edit_text("❌ Произошла ошибка при создании пробного ключа.")

    @user_router.callback_query(F.data.startswith("show_key_"))
    @registration_required
    async def show_key_handler(callback: types.CallbackQuery):
        key_id_to_show = int(callback.data.split("_")[2])
        # Answer callback immediately to avoid Telegram client "spinner" and perceived hangs.
        try:
            await callback.answer()
        except Exception:
            pass
        await callback.message.edit_text("Загружаю информацию о ключе...")
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id_to_show)

        if not key_data or key_data['user_id'] != user_id:
            await callback.message.edit_text("❌ Ошибка: ключ не найден.")
            return
            
        try:
            details = await remnawave_api.get_key_details_from_host(key_data)
            if not details or not details.get('connection_string'):
                # Если ключ удалён в Remnawave, удалим его и локально, чтобы не висел в списке.
                try:
                    exists = await _remnawave_key_exists(key_data)
                except Exception:
                    exists = None
                if exists is False:
                    try:
                        delete_key_by_id(key_id_to_show)
                    except Exception:
                        pass
                    await callback.message.edit_text(
                        "❌ Этот ключ был удалён на сервере и уже убран из бота.",
                        reply_markup=keyboards.create_back_to_menu_keyboard()
                    )
                    return

                await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                return

            connection_string = details['connection_string']
            expiry_date = datetime.fromisoformat(key_data['expiry_date'])
            created_date = datetime.fromisoformat(key_data['created_date'])
            
            all_user_keys = get_user_keys(user_id)
            key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id_to_show), 0)
            
            user_payload = details.get('user') if isinstance(details, dict) else None
            devices_connected = await _get_connected_devices_count(key_data, user_payload)
            devices_list = await _get_devices_list(key_data, user_payload)
            plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
            
            # Получаем информацию о подарке, если это подарок
            gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id_to_show)
            domain = (get_setting("domain") or "").strip()
            
            # Определяем, доступна ли докупка ГБ (тариф ключа имеет ограничение трафика)
            show_traffic_topup = False
            plan_traffic_limit_bytes = 0
            plan_lte_limit_bytes = 0
            plan_main_reset_price = 0.0
            plan_for_key = None
            try:
                plan_id_for_key = _resolve_plan_id_for_key(key_data)
                if plan_id_for_key:
                    plan_for_key = get_plan_by_id(plan_id_for_key)
                    if plan_for_key:
                        plan_traffic_limit_bytes = int(plan_for_key.get('traffic_limit_bytes') or 0)
                        plan_lte_limit_bytes = int(plan_for_key.get('lte_limit_bytes') or 0)
                        plan_main_reset_price = float(plan_for_key.get('main_reset_price_rub') or 0)
                        if plan_traffic_limit_bytes > 0:
                            show_traffic_topup = True
            except Exception:
                show_traffic_topup = False

            # Объём использованного трафика и дата ближайшего ежемесячного сброса
            # (если тариф лимитирован по ГБ и/или LTE).
            traffic_info_text = None
            next_reset_display = database.format_next_traffic_reset_display(
                key_data.get('next_traffic_reset_at')
            )
            try:
                if plan_traffic_limit_bytes > 0:
                    used_bytes = _extract_traffic_used_bytes(user_payload)
                    boost_bytes = int(key_data.get('traffic_boost_bytes') or 0)
                    total_limit_bytes = plan_traffic_limit_bytes + boost_bytes
                    used_gb_txt = _format_bytes_gb(used_bytes)
                    total_gb_txt = _format_bytes_gb(total_limit_bytes)
                    traffic_info_text = f"♾ Основной: {used_gb_txt} ГБ / {total_gb_txt} ГБ"
                    if next_reset_display:
                        traffic_info_text += f" (сброс {next_reset_display})"
            except Exception:
                traffic_info_text = None

            # Показываем блок LTE-пула (💰 premium-ноды), если у тарифа есть отдельный LTE-лимит
            # И у хоста ключа реально настроен активный сквад класса 'lte' (host_squads).
            show_lte_topup = False
            lte_display_label = "LTE"
            # Сброс основного трафика доступен только тарифам с лимитом основного трафика и заданной ценой
            show_main_reset = show_traffic_topup and plan_main_reset_price > 0
            try:
                host_name_for_lte = key_data.get('host_name')
                if database.should_account_lte_traffic(plan_for_key, host_name_for_lte):
                    lte_squad_cfg = database.get_squad_by_class(host_name_for_lte, 'lte')
                    show_lte_topup = True
                    lte_display_label = database.squad_display_label(lte_squad_cfg)
                    # LTE-пул принадлежит КЛЮЧУ: докупка на одном ключе не расходуется
                    # на других ключах того же пользователя.
                    lte_state = database.get_key_lte_state(key_id_to_show)
                    lte_used = int(lte_state.get('lte_used_bytes') or 0)
                    # Та же формула, что энфорсит планировщик (лимит тарифа + докупленный
                    # буст) — раньше показанный лимит и проверяемый расходились.
                    lte_total = database.resolve_lte_limit_bytes(lte_state, plan_lte_limit_bytes)
                    lte_used_txt = _format_bytes_gb(lte_used)
                    lte_total_txt = _format_bytes_gb(lte_total)
                    # Названия хостов/нод в карточке ключа не показываем: пользователю
                    # достаточно суммарного LTE-лимита, а разбивка по нодам доступна
                    # администратору в веб-панели (key_node_usage_snapshots).
                    lte_line = f"💰 {html_escape(lte_display_label)}: {lte_used_txt} ГБ / {lte_total_txt} ГБ"
                    if next_reset_display:
                        lte_line += f" (сброс {next_reset_display})"
                    traffic_info_text = f"{traffic_info_text}\n{lte_line}" if traffic_info_text else lte_line
            except Exception:
                pass

            final_text = get_key_info_text(
                key_data,
                key_number,
                devices_connected=devices_connected,
                plan_group=plan_group,
                plan_name=plan_name,
                device_limit=device_limit,
                gift_code=gift_code,
                domain=domain,
                traffic_info_text=traffic_info_text,
            )
            
            await callback.message.edit_text(
                text=final_text,
                reply_markup=keyboards.create_key_info_keyboard(
                    key_id_to_show, connection_string, devices_list=devices_list,
                    gift_code=gift_code, gift_id=gift_id,
                    show_traffic_topup=show_traffic_topup,
                    show_lte_topup=show_lte_topup,
                    show_main_reset=show_main_reset,
                    auto_renew=bool(int(key_data.get("auto_renew") or 0)),
                    lte_label=lte_display_label,
                )
            )
        except Exception as e:
            logger.error(f"Error showing key {key_id_to_show}: {e}")
            await callback.message.edit_text("❌ Произошла ошибка при получении данных ключа.")

    @user_router.callback_query(F.data.startswith("auto_renew_key_"))
    @registration_required
    async def auto_renew_key_toggle(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int(callback.data[len("auto_renew_key_"):])
        except ValueError:
            await callback.answer("Некорректный ID ключа.", show_alert=True)
            return

        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data["user_id"] != callback.from_user.id:
            await callback.answer("Ключ не найден.", show_alert=True)
            return

        new_state = not bool(int(key_data.get("auto_renew") or 0))
        rw_repo.set_key_auto_renew(key_id, new_state)
        state_text = "✅ Автопродление включено" if new_state else "❌ Автопродление отключено"
        await callback.answer(state_text, show_alert=True)
        # Обновляем карточку ключа
        await show_key_handler(callback.model_copy(update={"data": f"show_key_{key_id}"}))

    @user_router.callback_query(F.data == "toggle_auto_renew_profile")
    @registration_required
    async def toggle_auto_renew_profile(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_keys = rw_repo.get_user_keys(user_id)
        any_enabled = any(bool(int(k.get("auto_renew") or 0)) for k in user_keys)
        # Инвертируем: если хоть один включён — выключаем все, иначе включаем все
        new_state = not any_enabled
        rw_repo.set_all_keys_auto_renew_for_user(user_id, new_state)
        state_text = "✅ Автопродление включено для всех ключей" if new_state else "❌ Автопродление отключено для всех ключей"
        await callback.answer(state_text, show_alert=True)
        await profile_handler_callback(callback)

    @user_router.callback_query(F.data.startswith("switch_server_"))
    @registration_required
    async def switch_server_start(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int(callback.data[len("switch_server_"):])
        except ValueError:
            await callback.answer("Некорректный идентификатор ключа.", show_alert=True)
            return

        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != callback.from_user.id:
            await callback.answer("Ключ не найден.", show_alert=True)
            return

        hosts = get_all_hosts()
        if not hosts:
            await callback.answer("Нет доступных серверов.", show_alert=True)
            return

        current_host = key_data.get('host_name')
        hosts = [h for h in hosts if h.get('host_name') != current_host]
        if not hosts:
            await callback.answer("Другие серверы отсутствуют.", show_alert=True)
            return

        await callback.message.edit_text(
            "Выберите новый сервер (локацию) для этого ключа:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts, action=f"switch_{key_id}")
        )

    @user_router.callback_query(F.data.startswith("select_host_switch_"))
    @registration_required
    async def select_host_for_switch(callback: types.CallbackQuery):
        await callback.answer()
        payload = callback.data[len("select_host_switch_"):]
        parts = payload.split("_", 1)
        if len(parts) != 2:
            await callback.answer("Некорректные данные выбора сервера.", show_alert=True)
            return
        try:
            key_id = int(parts[0])
        except ValueError:
            await callback.answer("Некорректный идентификатор ключа.", show_alert=True)
            return
        new_host_name = parts[1]

        key_data = rw_repo.get_key_by_id(key_id)

        if not key_data or key_data.get('user_id') != callback.from_user.id:
            await callback.answer("Ключ не найден.", show_alert=True)
            return

        old_host = key_data.get('host_name')
        if not old_host:
            await callback.answer("Для ключа не указан текущий сервер.", show_alert=True)
            return
        if new_host_name == old_host:
            await callback.answer("Это уже текущий сервер.", show_alert=True)
            return


        try:
            expiry_dt = datetime.fromisoformat(key_data['expiry_date'])
            expiry_timestamp_ms_exact = int(expiry_dt.timestamp() * 1000)
        except Exception:

            now_dt = datetime.now()
            expiry_timestamp_ms_exact = int((now_dt + timedelta(days=1)).timestamp() * 1000)

        await callback.message.edit_text(
            f"⏳ Переношу ключ на сервер \"{new_host_name}\"..."
        )

        email = key_data.get('key_email')
        try:
            plan_id_for_move = _resolve_plan_id_for_key(key_data)
            plan_for_move = get_plan_by_id(plan_id_for_move) if plan_id_for_move else None
            move_limit = int((plan_for_move or {}).get('traffic_limit_bytes') or key_data.get('traffic_limit_bytes') or 0)
            if move_limit < 0:
                move_limit = 0
            move_strategy = (
                database.remnawave_traffic_limit_strategy_for_plan(plan_for_move)
                if plan_for_move is not None
                else (key_data.get('traffic_limit_strategy') or 'NO_RESET')
            )

            result = await remnawave_api.create_or_update_key_on_host(
                new_host_name,
                email,
                days_to_add=None,
                expiry_timestamp_ms=expiry_timestamp_ms_exact,
                plan_id=plan_id_for_move,
                traffic_limit_bytes=move_limit,
                traffic_limit_strategy=move_strategy,
            )
            if not result:
                await callback.message.edit_text(
                    f"❌ Не удалось перенести ключ на сервер \"{new_host_name}\". Попробуйте позже."
                )
                return


            try:
                await remnawave_api.delete_client_on_host(old_host, email)
            except Exception:
                pass


            update_key_host_and_info(
                key_id=key_id,
                new_host_name=new_host_name,
                new_remnawave_uuid=result['client_uuid'],
                new_expiry_ms=result['expiry_timestamp_ms']
            )


            try:
                updated_key = rw_repo.get_key_by_id(key_id)
                details = await remnawave_api.get_key_details_from_host(updated_key)
                if details and details.get('connection_string'):
                    connection_string = details['connection_string']
                    expiry_date = datetime.fromisoformat(updated_key['expiry_date'])
                    created_date = datetime.fromisoformat(updated_key['created_date'])
                    all_user_keys = get_user_keys(callback.from_user.id)
                    key_number = next((i + 1 for i, k in enumerate(all_user_keys) if k['key_id'] == key_id), 0)
                    user_payload = details.get('user') if isinstance(details, dict) else None
                    devices_connected = await _get_connected_devices_count(updated_key, user_payload)
                    plan_group, plan_name, device_limit = _get_tariff_info_for_key(updated_key, user_payload)
                    
                    # Получаем информацию о подарке, если это подарок
                    gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                    domain = (get_setting("domain") or "").strip()
                    
                    final_text = get_key_info_text(
                        updated_key,
                        key_number,
                        devices_connected=devices_connected,
                        plan_group=plan_group,
                        plan_name=plan_name,
                        device_limit=device_limit,
                        gift_code=gift_code,
                        domain=domain,
                    )
                    await callback.message.edit_text(
                        text=final_text,
                        reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, gift_code=gift_code, gift_id=gift_id)
                    )
                else:

                    await callback.message.edit_text(
                        f"✅ Готово! Ключ перенесён на сервер \"{new_host_name}\".\n"
                        "Обновите подписку/конфиг в клиенте, если требуется.",
                        reply_markup=keyboards.create_back_to_menu_keyboard()
                    )
            except Exception:
                await callback.message.edit_text(
                    f"✅ Готово! Ключ перенесён на сервер \"{new_host_name}\".\n"
                    "Обновите подписку/конфиг в клиенте, если требуется.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
        except Exception as e:
            logger.error(f"Error switching key {key_id} to host {new_host_name}: {e}", exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка при переносе ключа. Попробуйте позже."
            )

    @user_router.callback_query(F.data.startswith("show_qr_"))
    @registration_required
    async def show_qr_handler(callback: types.CallbackQuery):
        await callback.answer("Генерирую QR-код...")
        key_id = int(callback.data.split("_")[2])
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data['user_id'] != callback.from_user.id: return
        
        try:
            details = await remnawave_api.get_key_details_from_host(key_data)
            if not details or not details['connection_string']:
                await callback.answer("Ошибка: Не удалось сгенерировать QR-код.", show_alert=True)
                return

            connection_string = details['connection_string']
            qr_img = qrcode.make(connection_string)
            bio = BytesIO(); qr_img.save(bio, "PNG"); bio.seek(0)
            qr_code_file = BufferedInputFile(bio.read(), filename="vpn_qr.png")
            await callback.message.answer_photo(photo=qr_code_file)
        except Exception as e:
            logger.error(f"Error showing QR for key {key_id}: {e}")

    @user_router.callback_query(F.data.startswith("delete_device_"))
    @registration_required
    async def delete_device_handler(callback: types.CallbackQuery):
        """Обработчик удаления HWID-устройства с ключа."""
        try:
            await callback.answer("Удаляю устройство...")
        except Exception:
            pass
        
        # Парсим callback data вида: delete_device_{key_id}_{hwid}
        parts = callback.data[len("delete_device_"):].split("_", 1)
        if len(parts) != 2:
            await callback.answer("❌ Некорректные данные устройства", show_alert=True)
            return
        
        try:
            key_id = int(parts[0])
        except ValueError:
            await callback.answer("❌ Некорректный идентификатор ключа", show_alert=True)
            return
        
        hwid = parts[1]
        
        # Проверяем что ключ принадлежит пользователю
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data['user_id'] != callback.from_user.id:
            await callback.answer("❌ Ключ не найден или вам недоступен", show_alert=True)
            return
        
        try:
            # Получаем данные пользователя из Remnawave (нужен integer id для нового API)
            user_uuid = key_data.get('remnawave_user_uuid') or key_data.get('xui_client_uuid')
            user_id: int | None = None
            details = await remnawave_api.get_key_details_from_host(key_data)
            if details and isinstance(details.get('user'), dict):
                up = details['user']
                if not user_uuid:
                    user_uuid = up.get('uuid') or up.get('userUuid')
                raw_id = up.get('id')
                if raw_id is not None:
                    try:
                        user_id = int(raw_id)
                    except (ValueError, TypeError):
                        pass

            if not user_uuid and user_id is None:
                await callback.answer("❌ Не удалось получить информацию об аккаунте", show_alert=True)
                return
            
            # Пытаемся удалить устройство через API
            host_name = key_data.get('host_name')
            email = key_data.get('key_email') or key_data.get('email')
            success = await remnawave_api.delete_hwid_device(
                user_uuid, hwid, host_name=host_name, user_id=user_id, email=email
            )
            
            if success:
                await callback.answer("✅ Устройство успешно удалено!", show_alert=True)
                
                # Обновляем экран с информацией о ключе
                try:
                    details = await remnawave_api.get_key_details_from_host(key_data)
                    if details and isinstance(details.get('user'), dict):
                        user_payload = details['user']
                        devices_list = await _get_devices_list(key_data, user_payload)
                        devices_connected = await _get_connected_devices_count(key_data, user_payload)
                        
                        plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                        
                        all_user_keys = get_user_keys(callback.from_user.id)
                        key_number = next((i + 1 for i, k in enumerate(all_user_keys) if k['key_id'] == key_id), 0)
                        
                        # Получаем информацию о подарке, если это подарок
                        gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                        domain = (get_setting("domain") or "").strip()
                        
                        final_text = get_key_info_text(
                            key_data,
                            key_number,
                            devices_connected=devices_connected,
                            plan_group=plan_group,
                            plan_name=plan_name,
                            device_limit=device_limit,
                            gift_code=gift_code,
                            domain=domain,
                        )
                        
                        # Обновляем сообщение
                        await callback.message.edit_text(
                            text=final_text,
                            reply_markup=keyboards.create_key_info_keyboard(key_id, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                        )
                except Exception as e:
                    logger.warning(f"Could not refresh key info after device deletion: {e}")
                    # Всё равно уведомляем пользователя о успехе
            else:
                await callback.answer("❌ Не удалось удалить устройство. Попробуйте позже.", show_alert=True)
        
        except Exception as e:
            logger.error(f"Error deleting device {hwid} from key {key_id}: {e}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при удалении устройства", show_alert=True)
