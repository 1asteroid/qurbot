import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from bot.states import RegisterStates
from bot.keyboards import phone_keyboard, main_menu_keyboard, remove_keyboard, user_menu_keyboard
from services import UserService

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, is_manager: bool):
    service = UserService(session)
    user = await service.get_by_telegram_id(message.from_user.id)

    if user:
        text = f"👋 Xush kelibsiz, <b>{user.full_name}</b>!\n"
        text += f"Siz allaqachon ro'yxatdan o'tgansiz.\n\n"
        
        # Database'dan is_manager qiymatini o'qiyamiz
        if user.is_manager:
            text += "Siz menejer sifatida ro'yxatdan o'tgansiz. Asosiy menyu:"
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard()
            )
        else:
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=user_menu_keyboard()
            )
        return

    await state.set_state(RegisterStates.waiting_full_name)
    await message.answer(
        "👋 <b>Qurilish materiallari do'koniga xush kelibsiz!</b>\n\n"
        "Ro'yxatdan o'tish uchun to'liq ismingizni kiriting:",
        parse_mode="HTML",
    )


@router.message(RegisterStates.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("❗ Iltimos, to'liq ismingizni kiriting (kamida 3 belgi).")
        return

    await state.update_data(full_name=message.text.strip())
    await state.set_state(RegisterStates.waiting_phone)
    await message.answer(
        "📱 Telefon raqamingizni yuboring:",
        reply_markup=phone_keyboard(),
    )


@router.message(RegisterStates.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext, session: AsyncSession, is_manager: bool):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await _save_user(message, state, session, phone, is_manager)


@router.message(RegisterStates.waiting_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext, session: AsyncSession, is_manager: bool):
    phone = message.text.strip()
    if len(phone) < 9:
        await message.answer(
            "❗ Telefon raqam noto'g'ri. Iltimos, qayta kiriting.",
            reply_markup=phone_keyboard()
        )
        return
    await _save_user(message, state, session, phone, is_manager)


async def _save_user(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    phone: str,
    is_manager: bool,
):
    data = await state.get_data()
    full_name = data["full_name"]
    service = UserService(session)

    user, _ = await service.get_or_create(
        telegram_id=message.from_user.id,
        full_name=full_name,
        phone=phone,
    )
    await state.clear()

    # Database'dan is_manager qiymatini o'qiyamiz
    logger.debug(f"User {message.from_user.id}: is_manager={user.is_manager} (from database)")

    text = (
        f"✅ <b>Ro'yxatdan muvaffaqiyatli o'tdingiz!</b>\n\n"
        f"👤 Ism: {user.full_name}\n"
        f"📱 Tel: {user.phone}\n\n"
    )
    
    if user.is_manager:
        text += "Siz menejer sifatida ro'yxatdan o'tdingiz. Asosiy menyu:"
        await message.answer(
            text, 
            parse_mode="HTML", 
            reply_markup=main_menu_keyboard()
        )
        logger.info(f"Manager registered: {user.telegram_id} - {user.full_name}")
    else:
        text += "Siz ro'yxatdan o'tdingiz.\n👤 Profil -> Mening buyurtmalarim'dan buyurtmalaringizni ko'rishingiz mumkin."
        await message.answer(
            text, 
            parse_mode="HTML",
            reply_markup=user_menu_keyboard()
        )
        logger.info(f"Regular user registered: {user.telegram_id} - {user.full_name}")
