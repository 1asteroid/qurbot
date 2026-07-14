import logging
from datetime import datetime, timedelta
import pytz
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import MonitoringStates
from bot.keyboards import monitoring_keyboard, monitoring_report_keyboard
from services import OrderService, UserService
from utils import format_number, format_quantity, generate_manager_report_pdf
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
async def daily_stats(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    service = OrderService(session)
    stats = await service.get_daily_stats()
    today = datetime.now(TZ).replace(tzinfo=None).date()
    today_start = datetime(today.year, today.month, today.day)
    today_end = today_start + timedelta(days=1)
    
    # Store period info for PDF download
    await state.update_data(
        period_type="daily",
        period_start=today_start,
        period_end=today_end,
        period_label=today.strftime("%d.%m.%Y")
    )
    
    text = (
        f"📅 <b>Bugungi savdo ({today.strftime('%d.%m.%Y')})</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=monitoring_report_keyboard())
    await callback.answer()


@router.callback_query(F.data == "stats:monthly")
async def monthly_stats(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    service = OrderService(session)
    now = datetime.now(TZ)
    stats = await service.get_monthly_stats(now.year, now.month)
    month_name = now.strftime("%B %Y")
    
    # Store period info for PDF download
    month_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1)
    else:
        month_end = datetime(now.year, now.month + 1, 1)
    
    await state.update_data(
        period_type="monthly",
        period_start=month_start,
        period_end=month_end,
        period_label=month_name,
        year=now.year,
        month=now.month
    )
    
    text = (
        f"📆 <b>{month_name} oyi statistikasi</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=monitoring_report_keyboard())
    await callback.answer()


@router.callback_query(F.data == "stats:yearly")
async def yearly_stats(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    service = OrderService(session)
    year = datetime.now(TZ).year
    stats = await service.get_yearly_stats(year)
    
    # Store period info for PDF download
    year_start = datetime(year, 1, 1)
    year_end = datetime(year + 1, 1, 1)
    
    await state.update_data(
        period_type="yearly",
        period_start=year_start,
        period_end=year_end,
        period_label=str(year),
        year=year
    )
    
    text = (
        f"📊 <b>{year} yil statistikasi</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=monitoring_report_keyboard())
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

    service = OrderService(session)
    stats = await service.get_monthly_stats(dt.year, dt.month)
    month_name = dt.strftime("%B %Y")
    
    # Store period info for PDF download
    month_start = datetime(dt.year, dt.month, 1)
    if dt.month == 12:
        month_end = datetime(dt.year + 1, 1, 1)
    else:
        month_end = datetime(dt.year, dt.month + 1, 1)
    
    await state.update_data(
        period_type="custom",
        period_start=month_start,
        period_end=month_end,
        period_label=month_name,
        year=dt.year,
        month=dt.month
    )
    
    text = (
        f"📆 <b>{month_name} oyi statistikasi</b>\n\n"
        f"📦 Buyurtmalar soni: <b>{stats['count']}</b>\n"
        f"💰 Jami summa: <b>{format_number(stats['total'])} UZS</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=monitoring_report_keyboard())


@router.callback_query(F.data == "stats:top_products")
async def top_products(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
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
            f"   📦 Sotilgan: {format_quantity(item['total_qty'])} {item['unit']}\n"
            f"   💰 Daromad: {format_number(item['total_revenue'])} UZS\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=monitoring_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "download_report_pdf")
async def download_report_pdf(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Download monitoring report as PDF"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_manager:
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return
    
    data = await state.get_data()
    period_start = data.get("period_start")
    period_end = data.get("period_end")
    period_label = data.get("period_label", "Hisobot")
    
    if not period_start or not period_end:
        await callback.answer("❌ Iltimos, avval rapportni tanlang.", show_alert=True)
        return
    
    try:
        service = OrderService(session)
        orders, stats = await service.get_orders_for_period(period_start, period_end)
        
        if not orders:
            await callback.answer("❌ Tanlangan davr uchun buyurtma yo'q.", show_alert=True)
            return
        
        # Generate PDF
        pdf_buffer = generate_manager_report_pdf(user, orders)
        
        # Send PDF
        pdf_file = BufferedInputFile(
            pdf_buffer.getvalue(),
            filename=f"Hisobot_{period_label}.pdf"
        )
        
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=pdf_file,
            caption=f"📊 Hisobot: {period_label}\n\n📦 Buyurtmalar: {stats['count']}\n💰 Jami: {format_number(stats['total'])} UZS"
        )
        await callback.answer("✅ PDF yuklandi.", show_alert=False)
        
    except Exception as e:
        logger.error(f"PDF download error: {e}")
        await callback.answer("❌ PDF yaratishda xatolik.", show_alert=True)


@router.callback_query(F.data == "stats:menu")
async def back_to_stats_menu(callback: CallbackQuery, state: FSMContext):
    """Go back to stats menu"""
    await state.clear()
    await callback.message.edit_text(
        "📊 <b>Monitoring</b>\n\nStatistika turini tanlang:",
        parse_mode="HTML",
        reply_markup=monitoring_keyboard(),
    )
    await callback.answer()
