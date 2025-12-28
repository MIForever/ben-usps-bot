import sqlite3
import logging
from src.config import get_settings
from typing import List, Dict, Any

class OrderManager:
    def __init__(self):
        """
        Initialize OrderManager with SQLite for persistent storage
        
        :param db_path: Path to SQLite database file
        :param max_orders: Maximum number of order IDs to keep in history
        """
        self.settings = get_settings()
        self.db_path = self.settings.DB_PATH
        self.max_orders = self.settings.MAX_LOADS
        self.init_db()

    def init_db(self):
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Table for seen orders with auto-cleanup
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_orders (
                    order_id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_seen(self, order_id: str) -> bool:
        """Check if an order ID has been seen before"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_orders WHERE order_id = ?", (order_id,))
            return cursor.fetchone() is not None

    def mark_seen(self, order_id: str):
        """Mark an order as seen and cleanup old entries if needed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Add new order
                cursor.execute(
                    "INSERT OR REPLACE INTO seen_orders (order_id) VALUES (?)",
                    (order_id,)
                )
                
                # Cleanup old orders if we exceed max_orders
                cursor.execute("""
                    DELETE FROM seen_orders 
                    WHERE order_id IN (
                        SELECT order_id FROM seen_orders 
                        ORDER BY timestamp DESC 
                        LIMIT -1 OFFSET ?
                    )
                """, (self.max_orders,))
                
                conn.commit()
        except Exception as e:
            logging.error(f"Error marking order {order_id} as seen: {e}")
    
    
    def process_new_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process new entries, filter out seen ones, and return unseen entries in FIFO order
        
        :param entries: List of new entries from API
        :return: List of unseen entries in correct order
        """
        unseen_entries = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Process in reverse order (oldest first)
            for entry in reversed(entries):
                order_id = entry.get('order_id')
                if not order_id:
                    continue
                
                try:
                    # Atomic check-and-mark using INSERT
                    cursor.execute(
                        "INSERT INTO seen_orders (order_id) VALUES (?)",
                        (order_id,)
                    )
                    # If we get here, it was a new entry
                    unseen_entries.append(entry)
                    
                except sqlite3.IntegrityError:
                    # Order already exists, skip it
                    continue
            
            # Cleanup once at the end
            if unseen_entries:
                cursor.execute("""
                    DELETE FROM seen_orders 
                    WHERE order_id IN (
                        SELECT order_id FROM seen_orders 
                        ORDER BY timestamp DESC 
                        LIMIT -1 OFFSET ?
                    )
                """, (self.max_orders,))
            
            conn.commit()
        
        return unseen_entries


    def clear_all_orders(self):
        """Delete all seen orders from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM seen_orders")
                conn.commit()
                logging.info("Successfully cleared all seen orders")
        except Exception as e:
            logging.error(f"Error clearing seen orders: {e}")
