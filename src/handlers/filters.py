from aiogram import types
from aiogram.filters import BaseFilter


class PrivateChatOnlyFilter(BaseFilter):
    """Filter that only allows messages from private chats."""
    
    async def __call__(self, message: types.Message) -> bool:
        return message.chat.type == "private"