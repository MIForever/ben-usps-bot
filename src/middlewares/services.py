"""Middleware to inject services into handlers."""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.services.order_manager import OrderManager
from src.services.city_manager import CityManager


class ServicesMiddleware(BaseMiddleware):
    """Middleware to inject service container into handlers."""
    
    def __init__(self, app, city_manager: CityManager, order_manager: OrderManager):
        self.app = app
        self.city_manager = city_manager
        self.order_manager = order_manager
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        data['app'] = self.app
        data['city_manager'] = self.city_manager
        data["order_manager"] = self.order_manager
        return await handler(event, data)