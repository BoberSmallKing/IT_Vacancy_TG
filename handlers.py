import re
import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from aiogram import types, F, Router
from aiogram.types import InputMediaPhoto, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import select, func
from db import async_session, User, Rating, Draft
from keyboard import draft_keyboard, main_menu_keyboard, payment_menu_keyboard, rating_keyboard, confirm_delete_draft, confirm_in_draft, topic_keyboard
from services import get_draft, create_or_update_draft, delete_draft, register_user, refresh_id_key
from services_payment import create_payment, check_payment_status

load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID"))

router = Router()

theme_list = {
    "web": 12,
    "tg bots": 5,
    "ai": 159
}

# === FSM для редактирования ===
class EditDraft(StatesGroup):
    photo = State()
    description = State()
    contact = State()
    theme = State()

#========================================================
# Обновление и показ опубликованного поста или черновика 
#========================================================
async def show_draft(user_id: int, target: types.Message, only_draft: bool = True):
    draft = await get_draft(user_id)
    if not draft:
        await target.answer("У тебя пока нет черновика.")
        return

    if only_draft and not draft.is_draft:
        await target.answer("У тебя пока нет черновиков.")
        return
    if not only_draft and draft.is_draft:
        await target.answer("Пока нет опубликованных услуг.")
        return

    text = "📰 *Твой черновик*\n" + "─" * 30 + "\n"
    if not draft.is_draft:
        if draft.message_id:
            text += f"🔗 *Главная ссылка*: https://t.me/SkillFlows/1/{draft.message_id}\n"
            if draft.theme_message_id:
                text += f"🔗 *Тематическая ссылка*: https://t.me/SkillFlows/{theme_list[draft.theme_name]}/{draft.theme_message_id}\n\n"
    text += f"✍️ *Описание:*\n{draft.description or '(не заполнено)'}\n\n"
    text += f"👤 *Контакт:* @{draft.contact or '(не заполнено)'}\n"
    text += f"📔 *Тема:* {draft.theme_name or '(темы нет)'}\n\n"
    


    published_at = draft.published_at
    if isinstance(published_at, str):
        try:
            published_at = datetime.fromisoformat(published_at)
        except Exception:
            published_at = None

    if published_at and not draft.is_draft:
        expiry = published_at + timedelta(days=30)
        remaining = expiry - datetime.now(timezone.utc)
        days, seconds = remaining.days, remaining.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if remaining.total_seconds() > 0:
            text += f"⏳ Осталось до окончания: {days} дн. {hours} ч. {minutes} мин.\n"
        else:
            text += "⏳ Срок публикации истёк!\n"
            
    text += "─" * 30

    bot = target.bot
    if draft.photo:
        await bot.send_photo(chat_id=target.chat.id, photo=draft.photo, caption=text,
                             parse_mode="Markdown", reply_markup=draft_keyboard())
    else:
        await bot.send_message(chat_id=target.chat.id, text=text, parse_mode="Markdown",
                               reply_markup=draft_keyboard())
        
        
async def update_post(user_id: int):
    from bot import bot

    draft = await get_draft(user_id)
    if not draft or draft.is_draft or not draft.message_id:
        return True

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()

        avg_query = await session.execute(
            select(func.avg(Rating.score), func.count(Rating.id))
            .where(Rating.to_user_id == user.id)
        )
        avg_score, review_count = avg_query.first()

        avg_score = round(avg_score or 0, 1)
        review_count = review_count or 0

    rating_line = (
        f"⭐️ Рейтинг: {avg_score} / ({review_count})\n\n"
        if review_count > 0 else "Пока нет отзывов\n\n"
    )

    full_text = (
        f"{draft.description or '(нет описания)'}\n\n"
        f"{rating_line}"
    )
    if draft.contact:
        full_text += f"📩 [Связаться со мной](https://t.me/{draft.contact})"


    if draft.theme_name and draft.theme_change_count == 2:
        if draft.theme_message_id:
             await bot.delete_message(chat_id=CHAT_ID, message_id=draft.theme_message_id)


        if draft.theme_name in theme_list:
            thread_id = theme_list[draft.theme_name]
            if draft.photo:
                sent_thread = await bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=draft.photo,
                    caption=full_text,
                    parse_mode="Markdown",
                    message_thread_id=thread_id
                )
            else:
                sent_thread = await bot.send_message(
                    chat_id=CHAT_ID,
                    text=full_text,
                    parse_mode="Markdown",
                    message_thread_id=thread_id
                )

            await create_or_update_draft(
                telegram_id=user_id,
                theme_message_id=sent_thread.message_id,
                theme_change_count=3
            )
            
            full_text += f"\u200B"
            
    if draft.photo:
        media = InputMediaPhoto(media=draft.photo, caption=full_text, parse_mode="Markdown")
        await bot.edit_message_media(chat_id=CHAT_ID, message_id=draft.message_id, media=media)
        if draft.theme_message_id:
            await bot.edit_message_media(chat_id=CHAT_ID, message_id=draft.theme_message_id, media=media)
    else:
        await bot.edit_message_text(chat_id=CHAT_ID, message_id=draft.message_id, text=full_text, parse_mode="Markdown")
        if draft.theme_message_id:
            await bot.edit_message_text(chat_id=CHAT_ID, message_id=draft.theme_message_id, text=full_text, parse_mode="Markdown")


    return True

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("rate_"):
        id_key = args[1].replace("rate_", "")
        await start_rate_flow(message, id_key, state)
        return

    user = await register_user(message.from_user.id, message.from_user.username)
    await refresh_id_key(user)

    text = (
        f"👋 <b>Добро пожаловать, {message.from_user.full_name}!</b>\n\n"
        "Этот бот поможет тебе <b>создать и опубликовать резюме</b> в Telegram-чате, "
        "а также получать <b>отзывы и рейтинг</b> от заказчиков.\n\n"
        "📋 Основные возможности:\n"
        "• ✍️ Создай резюме прямо в Telegram\n"
        "• 💾 Сохраняй черновики перед публикацией\n"
        "• 📢 Публикуй в общем чате после оплаты\n"
        "• ⭐️ Получай оценки и отзывы через личную ссылку\n"
        "• 👤 Просматривай свой профиль и рейтинг\n\n"
        f"📎 Ссылка для отзывов находится во акладке профиль"
    )
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML", disable_web_page_preview=True)


#==================================
#Главное меню (обработка сообщений) 
#==================================

@router.message(F.text == "📝 Черновики")
async def msg_show_drafts(message: types.Message):
    await show_draft(message.from_user.id, message, only_draft=True)


@router.message(F.text == "📢 Опубликованные")
async def msg_show_published(message: types.Message):
    draft = await get_draft(message.from_user.id)
    if draft and not draft.is_draft and draft.message_id:
        await show_draft(message.from_user.id, message, only_draft=False)
    else:
        await message.answer("Пока нет опубликованных услуг.")


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
        "📩 Поддержка: [@SkillFlows/35](https://t.me/SkillFlows/35)\n"
        "💬 Пожалуйста, опишите свою проблему подробно — мы обязательно поможем!"
    )
    await message.answer(help_text, parse_mode="Markdown", disable_web_page_preview=True)
    
    
@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Профиль не найден.")
            return

        result = await session.execute(
            select(
                func.coalesce(func.avg(Rating.score), 0),
                func.count(Rating.id)
            ).where(Rating.to_user_id == user.id)
        )
        avg_rating, review_count = result.first()
        free_vacancy_line = "✅ У вас есть бесплатная публикация" if user.is_first_visit else "❌ У вас нет бесплатной публикации" 
        
        text = (
            f"👤 <b>Твой профиль</b>\n\n"
            f"🆔 ID: <code>{user.telegram_id}</code>\n"
            f"💬 Имя: {message.from_user.full_name}\n"
            f"🔗 Ник: @{message.from_user.username or '—'}\n\n"
            f"⭐ Средний рейтинг: <b>{round(avg_rating, 2)}</b>\n"
            f"📝 Отзывов получено: <b>{review_count}</b>\n\n"
            f"{free_vacancy_line}\n"
            f"🔑 Ссылка для отзывов:\n"
            f"<code>https://t.me/ITvacancyCreate_bot?start=rate_{user.id_key}</code>"
        )

        await message.answer(text, parse_mode="HTML")
        

#===================================
# Меню вакансии(обработка сообщений) 
#===================================
@router.callback_query(F.data == "save_draft")
async def cb_save_draft(callback: types.CallbackQuery):
    await callback.message.answer("Вы уверены, что хотите перенести опубликованную услугу в черновик? Вам придется опять оплатить публикацию", reply_markup=confirm_in_draft())

        
@router.callback_query(F.data == "in_draft_confirm")
async def cb_save_draft_confirm(callback: types.CallbackQuery):
    draft = await get_draft(callback.from_user.id)
    bot = callback.message.bot

    if not draft:
        await create_or_update_draft(callback.from_user.id, is_draft=True)
        await callback.message.answer("Черновик сохранён ✅")
        return

    if not draft.is_draft and draft.message_id and draft.theme_name:
        await bot.delete_message(chat_id=CHAT_ID, message_id=draft.message_id)
        await bot.delete_message(chat_id=CHAT_ID, message_id=draft.theme_message_id)
        await create_or_update_draft(callback.from_user.id, is_draft=True, message_id=None, paid=False)
        await callback.message.answer("✅ Объявление перенесено в черновики и удалено из чата.")
    else:
        await create_or_update_draft(callback.from_user.id, is_draft=True, paid=False)
        await callback.message.answer("Черновик сохранён ✅")
        
        
@router.callback_query(F.data == "in_draft_cancel")
async def cb_save_draft_confirm(callback: types.CallbackQuery):
    await callback.message.answer("Отмена переноса ✅")
    await callback.answer()
        


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
    
#=== Удаление вакансии ===    
@router.callback_query(F.data == "delete")
async def cb_delete_confirm(callback: types.CallbackQuery):
    await callback.message.answer("Вы точно хотите удалить черновик и опубликованное сообщение?\n Они удалятся и Вы не сможете из вернуть!", reply_markup=confirm_delete_draft())
    await callback.answer()  

@router.callback_query(F.data == "delete_confirm")
async def cb_delete_execute(callback: types.CallbackQuery):
    draft = await get_draft(callback.from_user.id)
    bot = callback.message.bot
    await bot.delete_message(chat_id=CHAT_ID, message_id=draft.message_id)
    if draft.theme_message_id:
        await bot.delete_message(chat_id=CHAT_ID, message_id=draft.theme_message_id)
    await delete_draft(callback.from_user.id)
    await callback.message.answer("Черновик и опубликованное сообщение удалены ❌")
    await callback.answer()


@router.callback_query(F.data == "delete_cancel")
async def cb_delete_cancel(callback: types.CallbackQuery):
    await callback.message.answer("Удаление отменено ✅")
    await callback.answer()
    
@router.callback_query(F.data == "choose_topic")
async def cb_set_topic(callback: types.CallbackQuery):
    await callback.message.answer("Выберите тему, в которой дополнительно\nбудет публиковаться Ваша улуга. Тему менять можно только 2 раза", reply_markup=topic_keyboard())

@router.callback_query(F.data.in_(["topic_web", "topic_bots", "topic_ai"]))
async def cb_set_topic(callback: types.CallbackQuery):
    topics = {
        "topic_web": "web",
        "topic_bots": "tg bots",
        "topic_ai": "ai"
    }

    draft = await get_draft(callback.from_user.id)
    if not draft:
        await callback.message.answer("❌ Черновик не найден.")
        return

    new_theme = topics[callback.data]

    if not draft.theme_name:
        await create_or_update_draft(
            callback.from_user.id,
            theme_name=new_theme,
            theme_change_count=1
        )
        await callback.message.answer(f"Вы выбрали тему {new_theme}✅")

    elif draft.theme_change_count == 1:
        await create_or_update_draft(
            callback.from_user.id,
            theme_name=new_theme,
            theme_change_count=2
        )
        await callback.message.answer(f"Вы изменили тему на {new_theme}✅")

    else:
        await callback.message.answer("❌ Нельзя менять тему больше двух раз.")
        return  

    draft = await get_draft(callback.from_user.id) 
    await show_draft(callback.from_user.id, callback.message, only_draft=draft.is_draft)

        
@router.callback_query(F.data == "topic_cancel")
async def cb_set_topic(callback: types.CallbackQuery):
    await callback.message.answer("Темы не выбрана ❌")    

    

#====================
# Публикация и оплата 
#====================

@router.callback_query(F.data == "publish")
async def cb_publish(callback: types.CallbackQuery):
    draft = await get_draft(callback.from_user.id)
    if not draft:
        await callback.message.answer("Черновик не найден.")
        return

    if not draft.description or not draft.contact or not draft.theme_name:
        await callback.message.answer("❌ Нужно заполнить хотя бы описание, контакт и тему!")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not draft.paid and not user.is_first_visit:
            url, payment_id = await create_payment(1, "Оплата публикации резюме", callback.from_user.id)
            await create_or_update_draft(callback.from_user.id, payment_id=payment_id)
            await callback.message.answer(
                "Для публикации нужно оплатить 1 руб.\nПосле оплаты нажми /check",
                reply_markup=payment_menu_keyboard(url)
            )
            return

        if user.is_first_visit:
            user.is_first_visit = False
            await session.commit()
            
        avg_query = await session.execute(
            select(func.avg(Rating.score), func.count(Rating.id))
            .where(Rating.to_user_id == user.id)
        )
        avg_score, review_count = avg_query.first()
        avg_score = round(avg_score or 0, 1)
        review_count = review_count or 0

    rating_line = (
        f"⭐️ Рейтинг: {avg_score} / ({review_count})\n\n"
        if review_count > 0 else "Пока нет отзывов\n\n"
    )

    full_text = (
        f"{draft.description}\n\n"
        f"{rating_line}"
        f"📩 [Связаться со мной](https://t.me/{draft.contact})"
    )

    bot = callback.message.bot

    if not draft.is_draft and draft.message_id:
        success = await update_post(callback.from_user.id)
        if success:
            await callback.message.answer("✅ Резюме обновлено!")
        else:
            await callback.message.answer("❌ Ошибка при обновлении поста.")
    else:
        if draft.photo:
            sent_main = await bot.send_photo(
                CHAT_ID,
                photo=draft.photo,
                caption=full_text,
                parse_mode="Markdown"
            )
            if draft.theme_name:
                sent_thread = await bot.send_photo(
                    CHAT_ID,
                    photo=draft.photo,
                    caption=full_text,
                    parse_mode="Markdown",
                    message_thread_id=theme_list[draft.theme_name]
                )
        else:
            sent_main = await bot.send_message(
                CHAT_ID,
                full_text,
                parse_mode="Markdown"
            )
            if draft.theme_name:
                sent_thread = await bot.send_message(
                    CHAT_ID,
                    full_text,
                    parse_mode="Markdown",
                    message_thread_id=theme_list[draft.theme_name]
                )
        await create_or_update_draft(
            callback.from_user.id,
            message_id=sent_main.message_id,
            theme_message_id=sent_thread.message_id,
            is_draft=False,
            published_at=datetime.now(timezone.utc),
            theme_change_count=1
        )

        await callback.message.answer("✅ Резюме опубликовано! Теперь оно в разделе 'Опубликованные'.")




#=== Проверка оплаты ===
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


#========    
# Рейтинг 
#========    
async def start_rate_flow(message: types.Message, id_key: str, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id_key == id_key))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Ссылка недействительна или устарела.")
            return

    await message.answer(
        f"Ты собираешься оценить пользователя @{user.username or 'без ника'}.\n"
        "Выбери оценку:",
        reply_markup=rating_keyboard(user.id)
    )

@router.callback_query(F.data.regexp(r"^rate_(\d+)_(\d+)$"))
async def cb_handle_rating(callback: types.CallbackQuery):
    match = re.match(r"^rate_(\d+)_(\d+)$", callback.data)
    if not match:
        return

    target_user_id = int(match.group(1))
    score = int(match.group(2))

    async with async_session() as session:
        from_user = (await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )).scalar_one_or_none()

        if not from_user:
            from_user = User(
                telegram_id=callback.from_user.id,
                username=callback.from_user.username or None,
            )
            session.add(from_user)
            await session.flush()  


        if target_user_id == from_user.id:
            await callback.message.answer(
                "❌ Нельзя оценить самого себя!",
                reply_markup=main_menu_keyboard()
            )
            return


        existing = (await session.execute(
            select(Rating).where(
                Rating.from_user_id == from_user.id,
                Rating.to_user_id == target_user_id
            )
        )).scalar_one_or_none()

        if existing:
            await callback.message.answer(
                "⚠️ Ты уже оставлял отзыв этому пользователю.",
                reply_markup=main_menu_keyboard()
            )
            return

        new_rating = Rating(
            from_user_id=from_user.id,
            to_user_id=target_user_id,
            score=score
        )
        session.add(new_rating)


        result = await session.execute(
            select(User, Draft)
            .join(Draft, Draft.user_id == User.id, isouter=True)
            .where(User.id == target_user_id, Draft.is_draft == False)
        )
        row = result.first()
        rated_user, draft = row if row else (None, None)

        if rated_user:
            rated_user.update_id_key()
            session.add(rated_user)

        await session.commit()  


        avg_score, review_count = (await session.execute(
            select(func.avg(Rating.score), func.count(Rating.id))
            .where(Rating.to_user_id == target_user_id)
        )).first()
        avg_score = round(avg_score or 0, 1)
        review_count = review_count or 0


        if draft and draft.message_id:
            bot = callback.bot
            rating_line = f"⭐️ Рейтинг: {avg_score}/({review_count})\n\n"
            full_text = (
                f"{draft.description}\n\n"
                f"{rating_line}"
                f"📩 [Связаться со мной](https://t.me/{draft.contact})"
            )

            try:
                if draft.photo:
                    await bot.edit_message_caption(
                        chat_id=int(os.getenv("CHAT_ID")),
                        message_id=draft.message_id,
                        caption=full_text,
                        parse_mode="Markdown"
                    )
                    if draft.theme_message_id:
                        await bot.edit_message_caption(
                        chat_id=int(os.getenv("CHAT_ID")),
                        message_id=draft.theme_message_id,
                        caption=full_text,
                        parse_mode="Markdown"
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=int(os.getenv("CHAT_ID")),
                        message_id=draft.message_id,
                        text=full_text,
                        parse_mode="Markdown"
                    )
                    if draft.theme_message_id:
                        await bot.edit_message_text(
                        chat_id=int(os.getenv("CHAT_ID")),
                        message_id=draft.theme_message_id,
                        text=full_text,
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logging.warning(f"Не удалось обновить сообщение: {e}")


    await callback.answer()
    await callback.message.answer(
        f"✅ Твоя оценка {score}/5 успешно сохранена.\n"
        "Спасибо за отзыв! ⭐️",
        reply_markup=main_menu_keyboard()
    )

# === Регистрация роутеров ===
def register_handlers(dp):
    dp.include_router(router)