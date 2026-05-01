from aiogram.fsm.state import State, StatesGroup


class RegisterStates(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()


class ProfileEditStates(StatesGroup):
    editing_full_name = State()
    editing_phone = State()


class OrderStates(StatesGroup):
    selecting_user = State()
    selecting_category = State()
    searching_user = State()
    selecting_product = State()
    entering_quantity = State()
    entering_price = State()
    entering_size = State()
    reviewing_order = State()
    confirming_order = State()


class ProductStates(StatesGroup):
    entering_name = State()
    selecting_category = State()
    entering_unit = State()
    editing_name = State()
    editing_unit = State()
    confirm_delete = State()


class MonitoringStates(StatesGroup):
    selecting_custom_month = State()
    viewing_report = State()
