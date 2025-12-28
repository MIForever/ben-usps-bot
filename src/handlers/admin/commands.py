import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from src.handlers.filters import PrivateChatOnlyFilter
from src.services.order_manager import OrderManager
from src.services.city_manager import CityManager
from src.config import get_settings

logger = logging.getLogger(__name__)
router = Router()

settings = get_settings()

def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(PrivateChatOnlyFilter(), Command("stoppost"))
async def cmd_stoppost(message: Message, app):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    app.posting_enabled = False
    logger.info(f"Posting stopped by admin {message.from_user.id}")
    await message.reply("⏸ Posting paused!")


@router.message(PrivateChatOnlyFilter(), Command("startpost"))
async def cmd_startpost(message: Message, app):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    app.posting_enabled = True
    logger.info(f"Posting started by admin {message.from_user.id}")
    await message.reply("✅ Posting enabled!")


@router.message(PrivateChatOnlyFilter(), Command("status"))
async def cmd_status(message: Message, app):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    status = "🟢 Enabled" if app.posting_enabled else "🔴 Disabled"
    await message.reply(f"📊 Posting Status: {status}")


@router.message(PrivateChatOnlyFilter(), Command("clearorders"))
async def cmd_clearorders(message: Message, order_manager: OrderManager):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    order_manager.clear_all_orders()
    await message.answer("✅ All orders have been cleared from the database.")


@router.message(PrivateChatOnlyFilter(), Command("addcity"))
async def cmd_addcity(message: Message, city_manager: CityManager):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("⚠️ Please provide a city name.\nExample: /addcity Miami")
        return

    city = parts[1].strip()
    
    if city_manager.add_city(city):
        await message.answer(f"✅ City {city.upper()} has been added to the cities list.")
    else:
        await message.answer(f"⚠️ City {city.upper()} is already in the list.")


@router.message(PrivateChatOnlyFilter(), Command("listcities"))
async def cmd_listcities(message: Message, city_manager: CityManager):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    cities = city_manager.get_all_cities()
    
    if not cities:
        await message.answer("📄 <b>Cities list is empty.</b>")
        return
    
    formatted = "\n".join(f"• {city}" for city in cities)
    await message.answer(f"📄 <b>Cities list ({len(cities)}):</b>\n\n{formatted}")


@router.message(PrivateChatOnlyFilter(), Command("removecity"))
async def cmd_removecity(message: Message, city_manager: CityManager):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("⚠️ Please provide a city name.\nExample: /removecity Miami")
        return
    
    city = parts[1].strip()
    
    if city_manager.remove_city(city):
        await message.answer(f"✅ City <b>{city.upper()}</b> has been removed from the cities list.")
    else:
        await message.reply(f"❌ City {city.upper()} not found in the cities list.")


@router.message(PrivateChatOnlyFilter(), Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You don't have permission to use this command.")
        return

    help_text = (
        "<b>🛠 Admin Commands</b>\n\n"
        "<b>/startpost</b> – Resume posting loads to the channel\n"
        "<b>/stoppost</b> – Pause posting loads\n"
        "<b>/status</b> – Check posting status\n"
        "<b>/clearorders</b> – Clear all stored order IDs\n"
        "<b>/addcity CITY</b> – Add a city to the filter list\n"
        "<b>/removecity CITY</b> – Remove a city from the filter list\n"
        "<b>/listcities</b> – Show all tracked cities\n"
    )

    await message.answer(help_text)