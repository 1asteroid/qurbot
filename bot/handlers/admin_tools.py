import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from bot.keyboards import cancel_keyboard, main_menu_keyboard
from bot.states import UnitStates
from services import UserService, UnitService

logger = logging.getLogger(__name__)
router = Router()


def _is_admin_user(user) -> bool:
    return bool(user and user.is_admin)


def _admin_panel_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Userlarni boshqarish", callback_data="manage_users"))
    builder.row(InlineKeyboardButton(text="📏 O'lchov birliklari", callback_data="manage_units"))
    builder.row(InlineKeyboardButton(text="📋 Buyurtmalar", callback_data="manager_orders_list"))
    builder.row(InlineKeyboardButton(text="⬅️ Profil", callback_data="back_to_profile"))
    return builder


def _units_list_keyboard(units) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Birlik qo'shish", callback_data="unit_add_start"))
    for unit in units:
        builder.row(InlineKeyboardButton(text=f"📏 {unit.name}", callback_data=f"unit_detail:{unit.id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_panel"))
    return builder


def _unit_detail_keyboard(unit_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"unit_edit_start:{unit_id}"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"unit_delete_start:{unit_id}"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Birliklar", callback_data="manage_units"))
    return builder


def _replacement_keyboard(units, unit_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for unit in units:
        if unit.id == unit_id:
            continue
        builder.row(InlineKeyboardButton(text=f"📏 {unit.name}", callback_data=f"unit_replace:{unit.id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Birlik tafsiloti", callback_data=f"unit_detail:{unit_id}"))
    return builder


@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not _is_admin_user(user):
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    await callback.message.edit_text(
        "⚙️ <b>Admin panel</b>\n\nKerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=_admin_panel_keyboard().as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "manage_units")
async def manage_units(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not _is_admin_user(user):
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    unit_service = UnitService(session)
    units = await unit_service.get_all()

    text = "📏 <b>O'lchov birliklari</b>\n\n"
    text += f"Jami birliklar: <b>{len(units)}</b>"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_units_list_keyboard(units).as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "unit_add_start")
async def unit_add_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not _is_admin_user(user):
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    await state.set_state(UnitStates.entering_name)
    await callback.message.answer(
        "➕ <b>Yangi birlik nomini kiriting</b>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(UnitStates.entering_name)
async def unit_create(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    name = (message.text or "").strip()
    if len(name) < 1:
        await message.answer("❗ Birlik nomini kiriting.")
        return

    unit_service = UnitService(session)
    try:
        unit = await unit_service.create(name)
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
        return
    await state.clear()
    await message.answer(f"✅ Birlik qo'shildi: <b>{unit.name}</b>", parse_mode="HTML")
    await manage_units_after_action(message, session)


@router.callback_query(F.data.startswith("unit_detail:"))
async def unit_detail(callback: CallbackQuery, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not _is_admin_user(user):
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    unit_id = int(callback.data.split(":")[1])
    unit_service = UnitService(session)
    unit = await unit_service.get_by_id(unit_id)
    if not unit:
        await callback.answer("❌ Birlik topilmadi.", show_alert=True)
        return

    used_count = await unit_service.count_products(unit.name)
    text = (
        f"📏 <b>{unit.name}</b>\n\n"
        f"👷 Biriktirilgan mahsulotlar: <b>{used_count}</b> ta\n"
        f"📅 Qo'shilgan: {unit.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_unit_detail_keyboard(unit.id).as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("unit_edit_start:"))
async def unit_edit_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not _is_admin_user(user):
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    unit_id = int(callback.data.split(":")[1])
    await state.update_data(edit_unit_id=unit_id)
    await state.set_state(UnitStates.editing_name)
    await callback.message.answer("✏️ Yangi birlik nomini kiriting:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(UnitStates.editing_name)
async def unit_edit(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    name = (message.text or "").strip()
    if len(name) < 1:
        await message.answer("❗ Birlik nomini kiriting.")
        return

    data = await state.get_data()
    unit_id = data.get("edit_unit_id")
    if not unit_id:
        await state.clear()
        await message.answer("❌ Birlik topilmadi.")
        return

    unit_service = UnitService(session)
    try:
        unit = await unit_service.update(unit_id, name)
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
        return

    await state.clear()
    if not unit:
        await message.answer("❌ Birlik topilmadi.")
        return

    await message.answer(f"✅ Birlik yangilandi: <b>{unit.name}</b>", parse_mode="HTML")
    await manage_units_after_action(message, session)


@router.callback_query(F.data.startswith("unit_delete_start:"))
async def unit_delete_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not _is_admin_user(user):
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    unit_id = int(callback.data.split(":")[1])
    unit_service = UnitService(session)
    unit = await unit_service.get_by_id(unit_id)
    if not unit:
        await callback.answer("❌ Birlik topilmadi.", show_alert=True)
        return

    used_count = await unit_service.count_products(unit.name)
    if used_count == 0:
        await unit_service.delete_with_reassign(unit.id)
        await callback.answer("✅ Birlik o'chirildi!", show_alert=True)
        await manage_units(callback, session)
        return

    units = await unit_service.get_all()
    replacements = [u for u in units if u.id != unit.id]
    if not replacements:
        await callback.answer("❌ O'rnini bosuvchi birlik yo'q.", show_alert=True)
        return

    await state.update_data(delete_unit_id=unit.id)
    await state.set_state(UnitStates.selecting_replacement)
    await callback.message.edit_text(
        f"🗑 <b>{unit.name}</b> birlik {used_count} ta mahsulotga biriktirilgan.\n\n"
        f"Avval o'rnini bosuvchi birlikni tanlang:",
        parse_mode="HTML",
        reply_markup=_replacement_keyboard(replacements, unit.id).as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("unit_replace:"))
async def unit_replace_and_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    if not _is_admin_user(user):
        await callback.answer("❌ Sizda huquq yo'q.", show_alert=True)
        return

    data = await state.get_data()
    delete_unit_id = data.get("delete_unit_id")
    if not delete_unit_id:
        await state.clear()
        await callback.answer("❌ Amal topilmadi.", show_alert=True)
        return

    replacement_unit_id = int(callback.data.split(":")[1])
    unit_service = UnitService(session)
    try:
        deleted = await unit_service.delete_with_reassign(delete_unit_id, replacement_unit_id)
    except ValueError as exc:
        await callback.answer(f"❌ {exc}", show_alert=True)
        return

    await state.clear()
    if not deleted:
        await callback.answer("❌ Birlik topilmadi.", show_alert=True)
        return

    await callback.answer("✅ Birlik qayta biriktirilib o'chirildi!", show_alert=True)
    await manage_units(callback, session)


async def manage_units_after_action(message: Message, session: AsyncSession):
    unit_service = UnitService(session)
    units = await unit_service.get_all()
    text = "📏 <b>O'lchov birliklari</b>\n\n"
    text += f"Jami birliklar: <b>{len(units)}</b>"
    await message.answer(text, parse_mode="HTML", reply_markup=_units_list_keyboard(units).as_markup())
