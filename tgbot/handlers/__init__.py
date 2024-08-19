"""Import all routers and add them to routers_list."""

from .user import user_router
from .admin import admin_router

routers_list = [
    user_router,
    admin_router
]

__all__ = [
    "routers_list",
]
