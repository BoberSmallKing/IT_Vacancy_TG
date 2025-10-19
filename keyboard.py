from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
def draft_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📸 Фото", callback_data="edit_photo")
    kb.button(text="✍️ Описание", callback_data="edit_desc")
    kb.button(text="👤 Контакт", callback_data="edit_contact")
    kb.button(text="📰 Темы", callback_data="choose_topic")
    kb.button(text="💾 В черновик", callback_data="save_draft")
    kb.button(text="❌ Удалить", callback_data="delete")
    kb.button(text="✅ Опубликовать", callback_data="publish")
    kb.adjust(2,2,2,1)
    return kb.as_markup()

def main_menu_keyboard():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Черновики"),
                KeyboardButton(text="📢 Опубликованные")
            ],
            [
                KeyboardButton(text="✍️ Создать резюме"),
                KeyboardButton(text="👤 Профиль")
            ],
            [
                KeyboardButton(text="ℹ️ Помощь")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return kb


def payment_menu_keyboard(url_link):
    kb = InlineKeyboardBuilder()
    kb.button(text="💳Оплатить 150руб", url=url_link)
    return kb.as_markup()


def rating_keyboard(target_user_id: int):
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text=f"⭐️ {i}", callback_data=f"rate_{target_user_id}_{i}")
    kb.adjust(5)
    return kb.as_markup()

def confirm_delete_draft():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить", callback_data="delete_confirm")
    kb.button(text="❌ Отмена", callback_data="delete_cancel")
    return kb.as_markup()

def confirm_in_draft():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, в черновик", callback_data="in_draft_confirm")
    kb.button(text="❌ Отмена", callback_data="in_draft_cancel")
    return kb.as_markup()


def topic_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="💻 Web", callback_data="topic_web")
    kb.button(text="🤖 ТГ боты", callback_data="topic_bots")
    kb.button(text="🧠 AI", callback_data="topic_ai")
    kb.button(text="❌ Без темы", callback_data="topic_cancel")
    kb.adjust(3,1)
    return kb.as_markup()
