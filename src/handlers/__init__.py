from aiogram import Router
from .admin import router as admin_router

router = Router()
router.include_router(admin_router)