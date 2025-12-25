"""
Обработчики бота
"""
from .start import router as start_router
from .search import router as search_router
from .categories import router as categories_router
from .shops import router as shops_router
from .favorites import router as favorites_router
from .subscription import router as subscription_router
from .admin import router as admin_router

# Список всех роутеров
routers = [
    start_router,
    search_router,
    categories_router,
    shops_router,
    favorites_router,
    subscription_router,
    admin_router,
]
