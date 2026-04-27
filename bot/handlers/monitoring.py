import logging
from datetime import datetime
import pytz
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import MonitoringStates
from bot.keyboards import monitoring_keyboard
from services import OrderService, UserService
from utils import format_number
from config import settings

logger = logging.getLogger(__name__)
router = Router()
TZ = pytz.timezone(settings.TIMEZONE)


@router.message(F.text == "📊 Monitoring")
async def show_monitoring_menu(message: Message, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    if not user or not user.is_manager:
        await message.answer("❌ Sizda bu bo'limga kirish huquqi yo'q.")
        return
    await message.answer(
        "📊 <b>Monitoring</b>\n\nStatistika turini tanlang:",
        parse_mode="HTML",
        reply_markup=monitoring_keyboard(),
    )


@router.callback_query(F.data == "stats:daily")
async def daily_stats(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    service = OrderService(session)
    stats = await service.get_daily_stats()
    today = datetime.now(TZ).strftime("%d.%m.%Y")
    text = (
        f"📅 <b>Bugungi savdo ({today})</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=monitoring_keyboard())
    await callback.answer()


@router.callback_query(F.data == "stats:monthly")
async def monthly_stats(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    service = OrderService(session)
    now = datetime.now(TZ)
    stats = await service.get_monthly_stats(now.year, now.month)
    month_name = now.strftime("%B %Y")
    text = (
        f"📆 <b>{month_name} oyi statistikasi</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=monitoring_keyboard())
    await callback.answer()


@router.callback_query(F.data == "stats:yearly")
async def yearly_stats(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    service = OrderService(session)
    year = datetime.now(TZ).year
    stats = await service.get_yearly_stats(year)
    text = (
        f"📊 <b>{year} yil statistikasi</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=monitoring_keyboard())
    await callback.answer()


@router.callback_query(F.data == "stats:custom")
async def ask_custom_month(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    await state.set_state(MonitoringStates.selecting_custom_month)
    await callback.message.answer(
        "🗓 Oy va yilni kiriting (masalan: <b>03.2025</b>):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(MonitoringStates.selecting_custom_month)
async def process_custom_month(message: Message, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    if not user or not user.is_manager:
        await state.clear()
        await message.answer("❌ Sizda huquq yo'q.")
        return
    try:
        dt = datetime.strptime(message.text.strip(), "%m.%Y")
    except ValueError:
        await message.answer("❗ Noto'g'ri format. Iltimos, MM.YYYY formatida kiriting (masalan: 03.2025).")
        return

    await state.clear()
    service = OrderService(session)
    stats = await service.get_monthly_stats(dt.year, dt.month)
    month_name = dt.strftime("%B %Y")
    text = (
        f"📆 <b>{month_name} oyi statistikasi</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=monitoring_keyboard())


@router.callback_query(F.data == "stats:top_products")
async def top_products(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    service = OrderService(session)
    top = await service.get_top_products(limit=10)

    if not top:
        await callback.answer("Hozircha ma'lumot yo'q.", show_alert=True)
        return

    lines = ["🏆 <b>TOP mahsulotlar (daromad bo'yicha)</b>\n"]
    for i, item in enumerate(top, 1):
        lines.append(
            f"{i}. <b>{item['name']}</b> ({item['unit']})\n"
            f"   📦 Sotilgan: {item['total_qty']:.0f} {item['unit']}\n"
            f"   💰 Daromad: {format_number(item['total_revenue'])} UZS\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=monitoring_keyboard(),
    )
    await callback.answer()
