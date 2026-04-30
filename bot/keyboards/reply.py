from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Manager uchun menyu"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧾 Buyurtma yaratish")],
            [KeyboardButton(text="📦 Mahsulotlar"), KeyboardButton(text="📜 Buyurtmalar tarixi")],
            [KeyboardButton(text="📊 Monitoring"), KeyboardButton(text="👤 Profil")],
            [KeyboardButton(text="👨‍💻 Dasturchi bilan bog'lanish")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def user_menu_keyboard() -> ReplyKeyboardMarkup:
    """Oddiy foydalanuvchi uchun menyu"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="� Mening buyurtmalarim"), KeyboardButton(text="👤 Profil")],
            [KeyboardButton(text="👨‍💻 Dasturchi bilan bog'lanish")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
