from src.services.order_manager import OrderManager
from src.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    order_manager = OrderManager(db_path=settings.DB_PATH, max_orders=settings.MAX_LOADS)
    order_manager.clear_all_orders()
