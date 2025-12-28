import asyncio
import logging
import random
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy

from src.handlers import router as main_router 
from src.middlewares.services import ServicesMiddleware
from src.services.order_manager import OrderManager
from src.services.city_manager import CityManager
from src.services.scrapers.board_2 import LoadScraper
from src.services.error_notifier import ErrorNotifier
from src.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BotApplication:
    def __init__(self):
        self.settings = get_settings()
        self.bot = Bot(
            token=self.settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher(
            storage=MemoryStorage(),
            fsm_strategy=FSMStrategy.CHAT,
        )
        self.order_manager = OrderManager()
        self.city_manager = CityManager(self.settings.CITIES_FILE)
        self.scraper = LoadScraper(self.settings.CITIES_FILE)
        self.error_notifier = ErrorNotifier()
        self.entry_queue = asyncio.Queue()
        self.posting_enabled = True
        
        self._setup_middleware()
        self._setup_router()

    def _setup_middleware(self):
        middleware = ServicesMiddleware(self, self.city_manager, self.order_manager)
        self.dispatcher.message.middleware(middleware)
        self.dispatcher.callback_query.middleware(middleware)

    def _setup_router(self):
        self.dispatcher.include_router(main_router)

    async def register_commands(self):
        commands = [
            BotCommand(command="startpost", description="🚀 Resume posting loads"),
            BotCommand(command="stoppost", description="⏸ Pause posting loads"),
            BotCommand(command="status", description="📊 Check posting status"),
            BotCommand(command="clearorders", description="🧹 Clear all order IDs"),
            BotCommand(command="addcity", description="➕ Add city to filter"),
            BotCommand(command="removecity", description="➖ Remove city from filter"),
            BotCommand(command="listcities", description="📍 Show tracked cities"),
            BotCommand(command="help", description="❓ Show help message"),
        ]
        await self.bot.set_my_commands(commands)

    def _format_message(self, entry):
        state_code = entry.get('state_code', '')
        stops = "\n".join(f"  <b>Stop {i+1}</b>: {stop}" for i, stop in enumerate(entry['stops']))
        
        return (
            f"<b>New Load Bid:</b> <code>{entry['order_id']}</code>\n\n"
            f"<b>Distance:</b> {entry['distance']}\n\n"
            f"<b>Pickup:</b> {entry['pickup_time']}\n"
            f"<b>Delivery:</b> {entry['delivery_time']}\n\n"
            f"🚛<b>Stops:</b>\n{stops}\n\n"
            f"#{state_code}\n\n"
            f"<a href='https://t.me/ben_usps'>USPS LOADS</a>"
        )

    async def _send_with_retry(self, entry, max_retries=5):
        try:
            message = self._format_message(entry)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📍 Map", url=entry['route'])
            ]])
        except Exception as e:
            logger.error(f"Error formatting message for {entry.get('order_id')}: {e}", exc_info=True)
            if self.settings.ERROR_NOTIFICATION_ENABLED:
                await self.error_notifier.notify(f"Message format error: {e}\n\nEntry: {entry}", self.bot)
            return False

        for attempt in range(max_retries):
            try:
                await self.bot.send_message(
                    chat_id=self.settings.TELEGAM_CHANNEL_ID,
                    text=message,
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                    
        return False

    async def process_entries(self):
        while True:
            try:
                entry = await self.entry_queue.get()
                
                if not self.posting_enabled:
                    logger.info(f"Posting disabled, skipping {entry['order_id']}")
                else:
                    success = await self._send_with_retry(entry)
                    if success:
                        logger.info(f"Posted {entry['order_id']}")
                    else:
                        logger.warning(f"Failed to post {entry['order_id']}")
                    
                    await asyncio.sleep(3)
                    
                self.entry_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info("Process entries task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error processing entry: {e}", exc_info=True)
                if self.settings.ERROR_NOTIFICATION_ENABLED:
                    await self.error_notifier.notify(f"Entry processing error: {e}", self.bot)
                self.entry_queue.task_done()

    async def scrape_entries(self):
        while True:
            try:
                new_entries = self.scraper.get_new_entries()
                unseen_entries = self.order_manager.process_new_entries(new_entries)
                
                for entry in unseen_entries:
                    await self.entry_queue.put(entry)
                    
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Scraper error: {e}", exc_info=True)
                if self.settings.ERROR_NOTIFICATION_ENABLED:
                    await self.error_notifier.notify(f"Scraper error: {e}", self.bot)
                await asyncio.sleep(60)

    async def start(self):
        await self.register_commands()
        
        process_task = asyncio.create_task(self.process_entries())
        scraper_task = asyncio.create_task(self.scrape_entries())
        
        try:
            await self.dispatcher.start_polling(self.bot)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down...")
        except Exception as e:
            logger.critical(f"Fatal error: {e}", exc_info=True)
            if self.settings.ERROR_NOTIFICATION_ENABLED:
                await self.error_notifier.notify(f"Fatal error: {e}", self.bot)
            raise
        finally:
            process_task.cancel()
            scraper_task.cancel()
            await asyncio.gather(process_task, scraper_task, return_exceptions=True)
            await self.bot.session.close()


async def main():
    app = BotApplication()
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())