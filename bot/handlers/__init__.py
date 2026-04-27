from aiogram import Router
from bot.handlers import start, products, orders, history, monitoring, profile, user_management, misc


def setup_routers() -> Router:
    """Combine all routers in priority order."""
    main_router = Router()
    main_router.include_router(start.router)
    main_router.include_router(profile.router)
    main_router.include_router(user_management.router)
    main_router.include_router(orders.router)
    main_router.include_router(products.router)
    main_router.include_router(history.router)
    main_router.include_router(monitoring.router)
    main_router.include_router(misc.router)  # fallback last
    return main_router
