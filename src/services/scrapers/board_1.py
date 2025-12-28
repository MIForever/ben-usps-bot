import re
import logging
import requests
from urllib.parse import quote_plus
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class LoadScraper:
    """Scraper for Board 1 API"""
    
    API_URL = "http://172.86.97.3:7000/api/Dispatcher/LoadBids"
    LOGIN_URL = "http://172.86.97.3:7000/api/Account/Login"
    USERNAME = "dispatch@a2zexpress.net"
    PASSWORD = "332353"
    REQUEST_TIMEOUT = 30
    
    def __init__(self, cities_list: List[str]):
        self.cities_list = cities_list
        self.session = requests.Session()
        self.token = None
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
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
            
            if '-' in time_str and ':' in time_str:
                parts = time_str.split(' ')
                if len(parts) == 2:
                    date_part, time_part = parts
                    date_components = date_part.split('-')
                    if len(date_components) == 3:
                        month, day, year = date_components
                        time_obj = datetime.strptime(time_part, "%H:%M").time()
                        dt = datetime(int(year), int(month), int(day), time_obj.hour, time_obj.minute)
                        return dt.strftime("%m/%d/%Y %I:%M %p")
            
            if '/' in time_str and ':' in time_str:
                dt = datetime.strptime(time_str, "%m/%d/%Y %H:%M")
                return dt.strftime("%m/%d/%Y %I:%M %p")
            
            return time_str
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse time '{time_str}': {e}")
            return time_str

    def _extract_city_state_zip(self, address: str) -> Optional[str]:
        """Extract 'CITY, STATE ZIP' from full address"""
        pattern = r"([A-Za-z\.\s]+?),\s*([A-Z]{2}).*?(\d{5})$"
        match = re.search(pattern, address)
        if not match:
            return None
        
        city, state, zipcode = match.groups()
        city = city.strip().upper()
        
        for city_name in self.cities_list:
            if city_name in address.upper():
                city = city_name
                break
        
        return f"{city}, {state} {zipcode}"

    def _format_stops(self, stops: List[Dict]) -> List[str]:
        """Format stops information for display"""
        if not stops:
            return ["No stops information"]
        
        formatted_stops = []
        for stop in stops:
            if 'shortFormat' in stop:
                location = stop['shortFormat']
                for city_name in self.cities_list:
                    if city_name in stop.get('address', '').upper():
                        parts = location.split(',')
                        parts[0] = city_name
                        location = ','.join(parts)
                        break
                formatted_stops.append(location)
            elif 'address' in stop:
                location = self._extract_city_state_zip(stop['address'])
                formatted_stops.append(location or 'Unknown')
            else:
                formatted_stops.append('Unknown')
        
        return formatted_stops

    def _extract_pickup_time(self, job: Dict) -> str:
        """Extract pickup time from various possible fields"""
        time_fields = [
            'loadStartDate',
            'pickup_start_datetime',
            'pickup_end_datetime',
            'pick_up_datetime'
        ]
        
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
        """Extract delivery time from various possible fields"""
        time_fields = [
            'loadEndDate',
            'delivery_start_datetime',
            'delivery_end_datetime',
            'delivery_datetime'
        ]
        
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

    def _login(self) -> bool:
        """Login and get authentication token"""
        try:
            response = self.session.post(
                self.LOGIN_URL,
                json={"username": self.USERNAME, "password": self.PASSWORD},
                timeout=self.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('data'):
                    self.token = result['data']
                    self.session.headers['Authorization'] = f'Bearer {self.token}'
                    logger.info("Successfully logged in")
                    return True
                logger.error(f"Login failed: {result.get('error', 'Unknown error')}")
                return False
            
            logger.error(f"Login failed with status {response.status_code}")
            return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def _ensure_authenticated(self) -> bool:
        """Ensure valid token exists"""
        if not self.token:
            return self._login()
        return True

    def _create_route_link(self, locations: List[str]) -> str:
        """Generate Google Maps route link"""
        if len(locations) < 2:
            return ""
        encoded = [quote_plus(loc) for loc in locations]
        return "https://www.google.com/maps/dir/" + "/".join(encoded)

    def _extract_state_code(self, stops: List[Dict]) -> str:
        """Extract state code from first stop"""
        if not stops:
            return ''
        
        first_stop = stops[0]
        if 'shortFormat' in first_stop:
            parts = first_stop['shortFormat'].split(',')
            if len(parts) >= 2:
                return parts[1].strip().split()[0]
        elif 'state' in first_stop:
            return first_stop['state']
        
        return ''

    def _has_meaningful_data(self, job: Dict) -> bool:
        """Check if job has any meaningful data"""
        has_miles = job.get('total_miles') or job.get('totalDistance')
        has_pickup = any(job.get(f) for f in ['pick_up_datetime', 'pickup_start_datetime', 'pickup_end_datetime', 'loadStartDate'])
        has_delivery = any(job.get(f) for f in ['delivery_datetime', 'delivery_start_datetime', 'delivery_end_datetime', 'loadEndDate'])
        has_stops = job.get('stops')
        
        has_appointments = False
        if has_stops:
            has_appointments = any(stop.get('appointment_start_time') for stop in has_stops)
        
        return any([has_miles, has_pickup, has_delivery, has_stops, has_appointments])

    def get_new_entries(self) -> List[Dict[str, Any]]:
        """Fetch new job listings from API"""
        try:
            if not self._ensure_authenticated():
                logger.error("Authentication failed")
                return []
            
            response = self.session.get(self.API_URL, timeout=self.REQUEST_TIMEOUT)
            
            if response.status_code == 401:
                logger.warning("Token expired, re-authenticating")
                self.token = None
                if not self._login():
                    logger.error("Re-authentication failed")
                    return []
                response = self.session.get(self.API_URL, timeout=self.REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.error(f"API request failed: {response.status_code}")
                return []
            
            response_data = response.json()
            
            if isinstance(response_data, dict):
                if not response_data.get('success'):
                    logger.error(f"API error: {response_data.get('error')}")
                    return []
                data = response_data.get('data', [])
            elif isinstance(response_data, list):
                data = response_data
            else:
                logger.error(f"Unexpected API response format: {type(response_data)}")
                return []
            
            if not isinstance(data, list):
                logger.error(f"Data is not a list: {type(data)}")
                return []
            
            entries = []
            for job in data:
                load_id = job.get('load_id') or job.get('loadId')
                if not load_id or not self._has_meaningful_data(job):
                    continue
                
                stops = job.get('stops', [])
                stop_addresses = [stop.get('address', '') for stop in stops if stop.get('address')]
                
                entry = {
                    'order_id': str(load_id),
                    'distance': f"{(job.get('total_miles') or job.get('totalDistance', 0)):,.1f} miles",
                    'pickup_time': self._extract_pickup_time(job),
                    'delivery_time': self._extract_delivery_time(job),
                    'stops': self._format_stops(stops),
                    'state_code': self._extract_state_code(stops),
                    'route': self._create_route_link(stop_addresses)
                }
                entries.append(entry)
            
            logger.info(f"Fetched {len(entries)} entries")
            return entries
                
        except Exception as e:
            logger.error(f"Error fetching jobs: {e}", exc_info=True)
            return []