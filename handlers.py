import re
import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from aiogram import types, F, Router
from aiogram.types import InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


from keyboard import draft_keyboard, main_menu_keyboard, payment_menu_keyboard
from services import get_draft, create_or_update_draft, delete_draft
from services_payment import create_payment, check_payment_status

load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID"))

router = Router()


# === FSM для редактирования ===
class EditDraft(StatesGroup):
    photo = State()
    description = State()
    contact = State()


# === Показ черновика или опубликованного ===
async def show_draft(user_id: int, target: types.Message, only_draft: bool = True):
    draft = await get_draft(user_id)
    if not draft:
        await target.answer("У тебя пока нет черновика.")
        return

    if only_draft and not draft.is_draft:
        await target.answer("У тебя пока нет черновиков.")
        return
    if not only_draft and draft.is_draft:
        await target.answer("Пока нет опубликованных вакансий.")
        return

    text = f"✍️ *Описание:*\n{draft.description or '(не заполнено)'}\n\n"
    text += f"👤 *Контакт:* @{draft.contact or '(не заполнено)'}\n"

    # Время до окончания публикации
    if draft.published_at and not draft.is_draft:
        expiry = draft.published_at + timedelta(days=30)
        remaining = expiry - datetime.now(timezone.utc)
        days, seconds = remaining.days, remaining.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if remaining.total_seconds() > 0:
            text += f"⏳ Осталось до окончания: {days} дн. {hours} ч. {minutes} мин.\n"
        else:
            text += "⏳ Срок публикации истёк!\n"

    bot = target.bot
    if draft.photo:
        await bot.send_photo(chat_id=target.chat.id, photo=draft.photo, caption=text,
                             parse_mode="Markdown", reply_markup=draft_keyboard())
    else:
        await bot.send_message(chat_id=target.chat.id, text=text, parse_mode="Markdown",
                               reply_markup=draft_keyboard())


# === Обновление опубликованного поста ===
async def update_post(user_id: int):
    draft = await get_draft(user_id)
    if not draft or draft.is_draft or not draft.message_id:
        return True

    full_text = f"{draft.description or '(нет описания)'}"
    if draft.contact:
        full_text += f"\n\n📩 [Связаться со мной](https://t.me/{draft.contact})"

    from bot import bot
    try:
        if draft.photo:
            media = InputMediaPhoto(media=draft.photo, caption=full_text, parse_mode="Markdown")
            await bot.edit_message_media(chat_id=CHAT_ID, message_id=draft.message_id, media=media)
        else:
            await bot.edit_message_text(chat_id=CHAT_ID, message_id=draft.message_id,
                                        text=full_text, parse_mode="Markdown")
        return True
    except Exception as e:
        logging.error(f"Ошибка при обновлении поста: {e}")
        return False


# === Команды ===
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 Привет!\n\n"
        "Это бот для публикации **вакансий** в чате [@IT_VacancyTGG](https://t.me/IT_VacancyTGG).\n\n"
        "✨ Возможности:\n"
        "• Создавать и редактировать вакансии\n"
        "• Публиковать на **30 дней**\n"
        "• Первая публикация — **бесплатно!**\n\n"
        "🚀 Готовы разместить свою первую вакансию? Создайте её в меню!"
    )
    await message.answer(
        welcome_text,
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


# === Главное меню (обработка сообщений) ===
@router.message(F.text == "📝 Черновики")
async def msg_show_drafts(message: types.Message):
    await show_draft(message.from_user.id, message, only_draft=True)


@router.message(F.text == "📢 Опубликованные")
async def msg_show_published(message: types.Message):
    draft = await get_draft(message.from_user.id)
    if draft and not draft.is_draft and draft.message_id:
        await show_draft(message.from_user.id, message, only_draft=False)
    else:
        await message.answer("Пока нет опубликованных вакансий.")


@router.message(F.text == "✍️ Создать резюме")
async def msg_create_resume(message: types.Message):
    user_id = message.from_user.id
    draft = await get_draft(user_id)
    if not draft:
        await create_or_update_draft(user_id, is_draft=True)
        await message.answer("Черновик создан ✅", reply_markup=draft_keyboard())
    else:
        await message.answer("У тебя уже есть черновик.", reply_markup=main_menu_keyboard())


@router.message(F.text == "ℹ️ Помощь")
async def msg_help(message: types.Message):
    help_text = (
        "Если вам нужна помощь или остались вопросы — напишите нам!\n"
        "📩 Поддержка: [@IT_VacancyTGG/35](https://t.me/IT_VacancyTGG/35)\n"
        "💬 Пожалуйста, опишите свою проблему подробно — мы обязательно поможем!"
    )
    await message.answer(help_text, parse_mode="Markdown", disable_web_page_preview=True)

# === Сохранение черновика ===
@router.callback_query(F.data == "save_draft")
async def cb_save_draft(callback: types.CallbackQuery):
    draft = await get_draft(callback.from_user.id)
    bot = callback.message.bot

    if not draft:
        await create_or_update_draft(callback.from_user.id, is_draft=True)
        await callback.message.answer("Черновик сохранён ✅")
        return

    if not draft.is_draft and draft.message_id:
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=draft.message_id)
        except Exception as e:
            logging.error(f"Не удалось удалить сообщение из чата: {e}")

        await create_or_update_draft(callback.from_user.id, is_draft=True, message_id=None)
        await callback.message.answer("✅ Объявление перенесено в черновики и удалено из чата.")
    else:
        await create_or_update_draft(callback.from_user.id, is_draft=True)
        await callback.message.answer("Черновик сохранён ✅")


# === Редактирование ===
@router.callback_query(F.data == "edit_photo")
async def cb_edit_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Пришли фото или напиши «Без фото».")
    await state.set_state(EditDraft.photo)


@router.message(EditDraft.photo, F.photo)
async def set_photo(message: types.Message, state: FSMContext):
    await create_or_update_draft(message.from_user.id, photo=message.photo[-1].file_id)
    await message.answer("Фото обновлено ✅", reply_markup=main_menu_keyboard())
    draft = await get_draft(message.from_user.id)
    await show_draft(message.from_user.id, message, only_draft=draft.is_draft)
    await state.clear()


@router.message(EditDraft.photo, F.text)
async def set_no_photo(message: types.Message, state: FSMContext):
    if message.text.lower().strip() in ["без фото", "skip", "no photo"]:
        await create_or_update_draft(message.from_user.id, photo=None)
        await message.answer("Фото удалено ✅", reply_markup=main_menu_keyboard())
        draft = await get_draft(message.from_user.id)
        await show_draft(message.from_user.id, message, only_draft=draft.is_draft)
        await state.clear()
    else:
        await message.answer("Отправь фото или напиши «Без фото».")


@router.callback_query(F.data == "edit_desc")
async def cb_edit_desc(callback: types.CallbackQuery, state: FSMContext):
    draft = await get_draft(callback.from_user.id)
    await callback.message.answer(f"Текущее описание:\n{draft.description or '(не заполнено)'}\n\nОтправь новое:")
    await state.set_state(EditDraft.description)


@router.message(EditDraft.description, F.text)
async def set_description(message: types.Message, state: FSMContext):
    await create_or_update_draft(message.from_user.id, description=message.text)
    await message.answer("Описание обновлено ✅", reply_markup=main_menu_keyboard())
    draft = await get_draft(message.from_user.id)
    await show_draft(message.from_user.id, message, only_draft=draft.is_draft)
    await state.clear()


@router.callback_query(F.data == "edit_contact")
async def cb_edit_contact(callback: types.CallbackQuery, state: FSMContext):
    draft = await get_draft(callback.from_user.id)
    await callback.message.answer(f"Текущий контакт: @{draft.contact or '(не заполнено)'}\n\nОтправь новый username:")
    await state.set_state(EditDraft.contact)


@router.message(EditDraft.contact, F.text)
async def set_contact(message: types.Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    if not re.match(r"^[a-zA-Z0-9_]{5,32}$", username):
        await message.answer("❌ Некорректный username. Попробуй снова.")
        return
    await create_or_update_draft(message.from_user.id, contact=username)
    await message.answer("Контакт обновлён ✅", reply_markup=main_menu_keyboard())
    draft = await get_draft(message.from_user.id)
    await show_draft(message.from_user.id, message, only_draft=draft.is_draft)
    await state.clear()


# === Публикация и оплата ===
@router.callback_query(F.data == "publish")
async def cb_publish(callback: types.CallbackQuery):
    draft = await get_draft(callback.from_user.id)
    if not draft:
        await callback.message.answer("Черновик не найден.")
        return

    if not draft.description or not draft.contact:
        await callback.message.answer("❌ Нужно заполнить хотя бы описание и контакт!")
        return

    if not draft.paid:
        url, payment_id = await create_payment(150, "Оплата публикации резюме", callback.from_user.id)
        await create_or_update_draft(callback.from_user.id, payment_id=payment_id)
        await callback.message.answer(
            f" Для публикации нужно оплатить 150 руб.\nПосле оплаты нажми /check", 
            reply_markup=payment_menu_keyboard(url) 
        )
        return

    bot = callback.message.bot
    full_text = f"{draft.description}\n\n📩 [Связаться со мной](https://t.me/{draft.contact})"

    try:
        if not draft.is_draft and draft.message_id:
            success = await update_post(callback.from_user.id)
            if success:
                await callback.message.answer("✅ Резюме обновлено!")
            else:
                await callback.message.answer("❌ Ошибка при обновлении поста.")
        else:
            if draft.photo:
                sent = await bot.send_photo(CHAT_ID, photo=draft.photo, caption=full_text, parse_mode="Markdown")
            else:
                sent = await bot.send_message(CHAT_ID, full_text, parse_mode="Markdown")

            await create_or_update_draft(callback.from_user.id, message_id=sent.message_id, is_draft=False, published_at=datetime.now(timezone.utc))
            await callback.message.answer("✅ Резюме опубликовано! Теперь оно в разделе 'опубликованные'.")
    except Exception as e:
        logging.error(f"Ошибка при публикации: {e}")
        await callback.message.answer("❌ Ошибка при публикации. Проверь настройки.")


@router.message(Command("check"))
async def cmd_check(message: types.Message):
    user_id = message.from_user.id
    draft = await get_draft(user_id)
    if not draft or not draft.payment_id:
        await message.answer("❌ Нет активного платежа.")
        return

    try:
        if check_payment_status(draft.payment_id):
            await create_or_update_draft(user_id, paid=True)
            await message.answer("✅ Оплата подтверждена! Можешь публиковать резюме.")
        else:
            await message.answer("⏳ Оплата ещё не прошла. Попробуй через минуту.")
    except Exception:
        await message.answer("⚠️ Ошибка проверки оплаты. Попробуй позже.")


# === Удаление ===
@router.callback_query(F.data == "delete")
async def cb_delete(callback: types.CallbackQuery):
    draft = await get_draft(callback.from_user.id)
    bot = callback.message.bot
    if draft and draft.message_id:
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=draft.message_id)
        except Exception as e:
            logging.error(f"Не удалось удалить сообщение: {e}")
    await delete_draft(callback.from_user.id)
    await callback.message.answer("Черновик и опубликованное сообщение удалены ❌", reply_markup=None)


# === Регистрация ===
def register_handlers(dp):
    dp.include_router(router)
