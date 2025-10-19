import os
import uuid
from yookassa import Configuration, Payment
from dotenv import load_dotenv

load_dotenv()

Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_API_KEY")

async def create_payment(amount: float, description: str, user_id: int):
    payment = Payment.create({
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{os.getenv('BOT_USERNAME')}"
        },
        "capture": True,
        "description": description,
        "metadata": {"user_id": user_id},
        "receipt": {
            "customer": { 
                "full_name": "Ivanov Ivan Ivanovich",
                "email": "sashabobr2020@mail.ru",
                "phone": "79316063416"
            },
            "items": [
                {
                    "description": "IT",
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_mode": "full_payment",
                    "payment_subject": "commodity"
                }
            ],
            "tax_system_code": 1
        }
    }, str(uuid.uuid4()))

    return payment.confirmation.confirmation_url, payment.id

def check_payment_status(payment_id: str):
    payment = Payment.find_one(payment_id)
    print(f"Проверка платежа {payment_id}: статус = {payment.status}")
    return payment.status == "succeeded"
