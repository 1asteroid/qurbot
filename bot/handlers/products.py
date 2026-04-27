import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import ProductStates
from bot.keyboards import (
    products_list_keyboard,
    product_detail_keyboard,
    unit_keyboard,
    confirm_delete_keyboard,
    main_menu_keyboard,
)
from services import ProductService, UserService

logger = logging.getLogger(__name__)
router = Router()

UNITS = ["kg", "dona", "metr", "litr", "qop"]


def manager_required(is_manager: bool) -> bool:
    return is_manager


# ─── Entry point ──────────────────────────────────────────────────────────────

@router.message(F.text == "📦 Mahsulotlar")
async def show_products(message: Message, session: AsyncSession, is_manager: bool):
    # Database'dan manager tekshiruvi
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if not user or not user.is_manager:
        await message.answer("❌ Sizda bu bo'limga kirish huquqi yo'q.")
        return

    service = ProductService(session)
    products = await service.get_all()

    if not products:
        await message.answer(
            "📦 Mahsulotlar ro'yxati bo'sh.\n\nYangi mahsulot qo'shish uchun tugmani bosing.",
            reply_markup=products_list_keyboard([]),
        )
        return

    text = f"📦 <b>Mahsulotlar ro'yxati</b> ({len(products)} ta)\n\nMahsulotni tanlang:"
    await message.answer(text, parse_mode="HTML", reply_markup=products_list_keyboard(products))


@router.callback_query(F.data == "back_to_products")
async def back_to_products(callback: CallbackQuery, session: AsyncSession):
    service = ProductService(session)
    products = await service.get_all()
    await callback.message.edit_text(
        f"📦 <b>Mahsulotlar ro'yxati</b> ({len(products)} ta)\n\nMahsulotni tanlang:",
        parse_mode="HTML",
        reply_markup=products_list_keyboard(products),
    )
    await callback.answer()


# ─── Product detail ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("product_detail:"))
async def product_detail(callback: CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":")[1])
    service = ProductService(session)
    product = await service.get_by_id(product_id)

    if not product:
        await callback.answer("❌ Mahsulot topilmadi.", show_alert=True)
        return

    text = (
        f"📦 <b>{product.name}</b>\n\n"
        f"🏷 O'lchov birligi: <b>{product.unit}</b>\n"
        f"📅 Qo'shilgan: {product.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=product_detail_keyboard(product.id),
    )
    await callback.answer()


# ─── Add product ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "add_product_start")
async def start_add_product(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProductStates.entering_name)
    await callback.message.answer("📦 Yangi mahsulot nomini kiriting:")
    await callback.answer()


@router.message(ProductStates.entering_name)
async def process_product_name(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❗ Iltimos, mahsulot nomini kiriting (kamida 2 belgi).")
        return
    await state.update_data(product_name=message.text.strip())
    await state.set_state(ProductStates.entering_unit)
    await message.answer(
        "📏 O'lchov birligini tanlang:",
        reply_markup=unit_keyboard(),
    )


@router.callback_query(ProductStates.entering_unit, F.data.startswith("unit:"))
async def process_product_unit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    unit = callback.data.split(":")[1]
    data = await state.get_data()
    product_name = data["product_name"]

    service = ProductService(session)
    product = await service.create(name=product_name, unit=unit)
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Mahsulot qo'shildi!</b>\n\n"
        f"📦 Nom: {product.name}\n"
        f"🏷 O'lchov: {product.unit}",
        parse_mode="HTML",
    )
    # refresh list
    products = await service.get_all()
    await callback.message.answer(
        f"📦 <b>Mahsulotlar ro'yxati</b> ({len(products)} ta)",
        parse_mode="HTML",
        reply_markup=products_list_keyboard(products),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_product")
async def cancel_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    service = ProductService(session)
    products = await service.get_all()
    await callback.message.edit_text(
        f"📦 <b>Mahsulotlar ro'yxati</b>",
        parse_mode="HTML",
        reply_markup=products_list_keyboard(products),
    )
    await callback.answer("Bekor qilindi.")


# ─── Edit product ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit_product:"))
async def start_edit_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    await state.update_data(edit_product_id=product_id)
    await state.set_state(ProductStates.editing_name)
    await callback.message.answer("✏️ Yangi mahsulot nomini kiriting:")
    await callback.answer()


@router.message(ProductStates.editing_name)
async def process_edit_name(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❗ Iltimos, mahsulot nomini kiriting.")
        return
    await state.update_data(new_product_name=message.text.strip())
    await state.set_state(ProductStates.editing_unit)
    await message.answer("📏 Yangi o'lchov birligini tanlang:", reply_markup=unit_keyboard())


@router.callback_query(ProductStates.editing_unit, F.data.startswith("unit:"))
async def process_edit_unit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    unit = callback.data.split(":")[1]
    data = await state.get_data()
    product_id = data["edit_product_id"]
    new_name = data["new_product_name"]

    service = ProductService(session)
    product = await service.update(product_id, new_name, unit)
    await state.clear()

    if not product:
        await callback.answer("❌ Mahsulot topilmadi.", show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ <b>Mahsulot tahrirlandi!</b>\n\n"
        f"📦 Nom: {product.name}\n"
        f"🏷 O'lchov: {product.unit}",
        parse_mode="HTML",
        reply_markup=product_detail_keyboard(product.id),
    )
    await callback.answer()


# ─── Delete product ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete_product:"))
async def confirm_delete_product(callback: CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":")[1])
    service = ProductService(session)
    product = await service.get_by_id(product_id)

    if not product:
        await callback.answer("❌ Mahsulot topilmadi.", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 <b>{product.name}</b> mahsulotini o'chirishni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_delete_keyboard(product_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete:"))
async def execute_delete_product(callback: CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":")[1])
    service = ProductService(session)
    deleted = await service.delete(product_id)

    if deleted:
        await callback.answer("✅ Mahsulot o'chirildi.", show_alert=True)
    else:
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)

    products = await service.get_all()
    await callback.message.edit_text(
        f"📦 <b>Mahsulotlar ro'yxati</b> ({len(products)} ta)",
        parse_mode="HTML",
        reply_markup=products_list_keyboard(products),
    )
