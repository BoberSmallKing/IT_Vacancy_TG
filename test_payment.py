import os
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from yookassa import Payment
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
API_KEY = os.getenv("YOOKASSA_API_KEY")

from yookassa import Configuration
Configuration.account_id = SHOP_ID
Configuration.secret_key = API_KEY

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


@router.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить 100 руб", callback_data="pay_100")
    await message.answer("Привет! Нажми кнопку, чтобы оплатить:", reply_markup=kb.as_markup())


@router.callback_query(F.data == "pay_100")
async def process_payment(callback: types.CallbackQuery):
    payment = Payment.create({
        "amount": {
            "value": "100.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/ITvacancyCreate_bot"  
        },
        "capture": True,
        "description": f"Оплата от {callback.from_user.full_name}"
    })

    pay_url = payment.confirmation.confirmation_url
    await callback.message.answer(f"Перейди по ссылке для оплаты:\n{pay_url}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
