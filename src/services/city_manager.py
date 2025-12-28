import json
import logging
from pathlib import Path
from src.config import get_settings
from typing import List

logger = logging.getLogger(__name__)


class CityManager:
    def __init__(self, cities_file: str):
        self.settings = get_settings()
        self.cities_file = Path(cities_file)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not self.cities_file.exists():
            self.cities_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_cities([])
            logger.info(f"Created cities file: {self.cities_file}")
    
    def _load_cities(self) -> List[str]:
        try:
            with open(self.cities_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading cities: {e}")
            return []
    
    def _save_cities(self, cities: List[str]):
        with open(self.cities_file, 'w') as f:
            json.dump(cities, f, indent=2)
    
    def add_city(self, city: str) -> bool:
        city = city.strip().upper()
        cities = self._load_cities()
        
        if city in cities:
            return False
        
        cities.append(city)
        self._save_cities(cities)
        logger.info(f"Added city: {city}")
        return True
    
    def remove_city(self, city: str) -> bool:
        city = city.strip().upper()
        cities = self._load_cities()
        
        if city not in cities:
            return False
        
        cities.remove(city)
        self._save_cities(cities)
        logger.info(f"Removed city: {city}")
        return True
    
    def get_all_cities(self) -> List[str]:
        return self._load_cities()
    
    def has_city(self, city: str) -> bool:
        city = city.strip().upper()
        return city in self._load_cities()
    
    def clear_all(self):
        self._save_cities([])
        logger.info("Cleared all cities")