import logging
import requests
from urllib.parse import quote_plus
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class LoadScraper:
    """Scraper for Board 2 API"""
    
    API_URL = "https://demo.swanautomations.store/webhook/7c584a73-0a69-45f4-8bca-c3066e5bec3a"
    REQUEST_TIMEOUT = 30
    
    def __init__(self, cities_list: List[str]):
        self.cities_list = cities_list
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def _format_time(self, time_str: str) -> str:
        """Format various time formats to MM/DD/YYYY HH:MM AM/PM"""
        if not time_str:
            return "Not specified"
            
        try:
            if 'T' in time_str:
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                return dt.strftime("%m/%d/%Y %I:%M %p")
            
            elif '-' in time_str and ':' in time_str:
                parts = time_str.split(' ')
                if len(parts) == 2:
                    date_part, time_part = parts
                    date_components = date_part.split('-')
                    if len(date_components) == 3:
                        month, day, year = date_components
                        try:
                            time_obj = datetime.strptime(time_part, "%H:%M").time()
                            dt = datetime(int(year), int(month), int(day), time_obj.hour, time_obj.minute)
                            return dt.strftime("%m/%d/%Y %I:%M %p")
                        except ValueError:
                            return f"{month}/{day}/{year} {time_part}"
            
            return time_str
                
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse time '{time_str}': {e}")
            return time_str

    def _format_stop_location(self, stop: Dict) -> str:
        """Format stop location as CITY, STATE ZIP"""
        city = stop.get('city', '').upper()
        state = stop.get('state', '').upper()
        zipcode = stop.get('zipcode', '')
        
        if not city or not state:
            return None
        
        for city_name in self.cities_list:
            if city_name in city or city_name in f"{city} {state}".upper():
                city = city_name
                break
        
        return f"{city}, {state} {zipcode}"

    def _format_stops(self, stops: List[Dict]) -> List[str]:
        """Format stops information for display"""
        if not stops:
            return ["No stops information"]
        
        formatted = [self._format_stop_location(stop) for stop in stops]
        valid_stops = [s for s in formatted if s is not None]
        
        return valid_stops if valid_stops else ["No valid stops"]

    def _extract_pickup_time(self, job: Dict) -> str:
        """Extract pickup time from job data"""
        time_fields = ['pickup_start_datetime', 'pickup_end_datetime', 'pick_up_datetime']
        
        for field in time_fields:
            if job.get(field):
                return self._format_time(job[field])
        
        stops = job.get('stops', [])
        for stop in stops:
            if stop.get('stop_type') == 'Pickup':
                if stop.get('appointment_start_time'):
                    return self._format_time(stop['appointment_start_time'])
                if stop.get('appointment_end_time'):
                    return self._format_time(stop['appointment_end_time'])
        
        return "Not specified"

    def _extract_delivery_time(self, job: Dict) -> str:
        """Extract delivery time from job data"""
        time_fields = ['delivery_start_datetime', 'delivery_end_datetime', 'delivery_datetime']
        
        for field in time_fields:
            if job.get(field):
                return self._format_time(job[field])
        
        stops = job.get('stops', [])
        for stop in reversed(stops):
            if stop.get('stop_type') == 'Delivery':
                if stop.get('appointment_start_time'):
                    return self._format_time(stop['appointment_start_time'])
                if stop.get('appointment_end_time'):
                    return self._format_time(stop['appointment_end_time'])
        
        return "Not specified"

    def _extract_state_code(self, stops: List[Dict]) -> str:
        """Extract state code from first stop"""
        if not stops:
            return ''
        return stops[0].get('state', '').upper()

    def _create_route_link(self, stops: List[Dict]) -> str:
        """Generate Google Maps route link from stops"""
        if len(stops) < 2:
            return ""
        
        locations = []
        for stop in stops:
            city = stop.get('city', '')
            state = stop.get('state', '')
            zipcode = stop.get('zipcode', '')
            if city and state:
                locations.append(f"{city}, {state} {zipcode}")
        
        if len(locations) < 2:
            return ""
        
        encoded = [quote_plus(loc) for loc in locations]
        return "https://www.google.com/maps/dir/" + "/".join(encoded)

    def _has_meaningful_data(self, job: Dict) -> bool:
        """Check if job has meaningful data"""
        has_miles = job.get('total_miles')
        has_pickup = any(job.get(f) for f in ['pickup_start_datetime', 'pickup_end_datetime', 'pick_up_datetime'])
        has_delivery = any(job.get(f) for f in ['delivery_start_datetime', 'delivery_end_datetime', 'delivery_datetime'])
        stops = job.get('stops', [])
        
        if not stops:
            return False
        
        valid_stops = [s for s in stops if s.get('city') and s.get('state')]
        if not valid_stops:
            return False
        
        has_appointments = any(stop.get('appointment_start_time') for stop in stops)
        
        return any([has_miles, has_pickup, has_delivery, has_appointments])

    def get_new_entries(self) -> List[Dict[str, Any]]:
        """Fetch new job listings from API"""
        try:
            response = self.session.post(self.API_URL, json={}, timeout=self.REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.error(f"API request failed: {response.status_code}")
                return []
            
            data = response.json()
            
            if not isinstance(data, list):
                logger.error(f"Unexpected API response format: {type(data)}")
                return []
            
            entries = []
            for job in data:
                load_id = job.get('load_id')
                if not load_id or not self._has_meaningful_data(job):
                    continue
                
                stops = job.get('stops', [])
                
                entry = {
                    'order_id': str(load_id),
                    'distance': f"{job.get('total_miles', 0):,.1f} miles",
                    'pickup_time': self._extract_pickup_time(job),
                    'delivery_time': self._extract_delivery_time(job),
                    'stops': self._format_stops(stops),
                    'state_code': self._extract_state_code(stops),
                    'route': self._create_route_link(stops)
                }
                entries.append(entry)
            
            logger.info(f"Fetched {len(entries)} entries from Board 2")
            return entries
                
        except Exception as e:
            logger.error(f"Error fetching jobs: {e}", exc_info=True)
            return []