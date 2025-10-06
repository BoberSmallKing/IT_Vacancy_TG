from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
def draft_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📸 Фото", callback_data="edit_photo")
    kb.button(text="✍️ Описание", callback_data="edit_desc")
    kb.button(text="👤 Контакт", callback_data="edit_contact")
    kb.button(text="💾 В черновик", callback_data="save_draft")
    kb.button(text="✅ Опубликовать", callback_data="publish")
    kb.button(text="❌ Удалить", callback_data="delete")
    kb.adjust(2, 2, 1)
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
