import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

logger = logging.getLogger(__name__)
router = Router()

DEVELOPER_CONTACT = "@your_developer_username"  # ← Change this


@router.message(F.text == "👨‍💻 Dasturchi bilan bog'lanish")
async def contact_developer(message: Message):
    await message.answer(
        f"👨‍💻 <b>Dasturchi bilan bog'lanish</b>\n\n"
        f"Muammo yoki taklif bo'lsa, quyidagi manzilga murojaat qiling:\n\n"
        f"Telegram: <b>{DEVELOPER_CONTACT}</b>",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message, is_manager: bool):
    if is_manager:
        text = (
            "ℹ️ <b>Yordam — Menejer</b>\n\n"
            "🧾 <b>Buyurtma yaratish</b> — yangi buyurtma qo'shish\n"
            "📦 <b>Mahsulotlar</b> — mahsulotlarni boshqarish\n"
            "📜 <b>Buyurtmalar tarixi</b> — barcha buyurtmalar\n"
            "📊 <b>Monitoring</b> — savdo statistikasi\n"
            "👨‍💻 <b>Dasturchi</b> — texnik yordam\n"
        )
    else:
        text = (
            "ℹ️ <b>Yordam</b>\n\n"
            "Siz /start buyrug'i orqali ro'yxatdan o'tasiz.\n"
            "Buyurtma berish uchun menejer bilan bog'laning."
        )
    await message.answer(text, parse_mode="HTML")


@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "❓ Tushunarsiz buyruq. /help yozing yoki menyudan tanlang."
    )
