from _utils._util import *
from .local_storage import LocalStorage

import hashlib
import requests
from geopy.geocoders import Nominatim


class RestaurantMenuLocator:
    def __init__(self, db_name="addr_rest_rad_to_places.db", user_agent="restaurant_menu_locator"):
        self.api_key = os.getenv("GOOGLE_API_KEY")  # SANITIZED KEY
        self.db = LocalStorage(db_name=db_name)
        self.geolocator = Nominatim(user_agent=user_agent)
        util_logger.info(f"RestaurantMenuLocator initialized with db_name='{db_name}' and user_agent='{user_agent}'.")

    def generate_hash_key(self, address, restaurant_name, radius):
        """Helper function to create a unique hash key from API inputs."""
        util_logger.debug(f"Generating hash key with address='{address}', restaurant_name='{restaurant_name}', radius={radius}.")
        hash_input = f"{address}_{restaurant_name}_{radius}".encode('utf-8')
        hash_key = hashlib.sha256(hash_input).hexdigest()
        util_logger.debug(f"Generated hash key: {hash_key}.")
        return hash_key

    def get_coordinates(self, address):
        """Get coordinates of the address."""
        util_logger.info(f"Fetching coordinates for address='{address}'.")
        try:
            location = self.geolocator.geocode(address)
            if location:
                coords = (location.latitude, location.longitude)
                util_logger.info(f"Coordinates for address='{address}': {coords}.")
                return coords
            else:
                util_logger.warning(f"Geocoding failed for address='{address}'. No location found.")
                return None
        except Exception as e:
            util_logger.error(f"Error while geocoding address='{address}': {e}.")
            return None

    def search_restaurants_nearby(self, address, restaurant_name, radius=5000):
        """Search for restaurants near the location or return cached results."""
        util_logger.info(f"Searching for restaurants near address='{address}' with name='{restaurant_name}' and radius={radius} meters.")
        hash_key = self.generate_hash_key(address, restaurant_name, radius)
        
        # Check if data exists in cache
        cached_data = self.db.get_data_by_hash(hash_key)
        if cached_data:
            util_logger.info(f"Cache hit for hash_key='{hash_key}'. Returning cached data.")
            return json.loads(cached_data)
        else:
            util_logger.info(f"Cache miss for hash_key='{hash_key}'. Proceeding with API request.")

        # If no cache, make API request
        coords = self.get_coordinates(address)
        if not coords:
            util_logger.error(f"Could not retrieve coordinates for address='{address}'. Aborting search.")
            return None

        search_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{coords[0]},{coords[1]}",
            'radius': radius,  # in meters
            'type': 'food',
            'keyword': restaurant_name,
            'key': self.api_key
        }
        util_logger.info(f"Making API request to '{search_url}' with params={ {k: v for k, v in params.items() if k != 'key'} }.")

        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            response_data = response.json()
            util_logger.debug(f"API response received: {response_data.get('status', 'No status provided')}.")
        except requests.RequestException as e:
            util_logger.error(f"API request failed: {e}.")
            return None
        except ValueError as e:
            util_logger.error(f"Error parsing JSON response: {e}.")
            return None

        if response_data and 'results' in response_data:
            # Save the data in the database
            try:
                self.db.save_data(hash_key, json.dumps(response_data))
                util_logger.info(f"API response data cached with hash_key='{hash_key}'.")
            except Exception as e:
                util_logger.error(f"Failed to save data to cache for hash_key='{hash_key}': {e}.")
        
        return response_data

    def get_menu(self, place_id):
        """Extract restaurant menu from results or return cached results."""
        util_logger.info(f"Retrieving menu for place_id='{place_id}'.")
        
        # Check if data exists in cache
        cached_data = self.db.get_data_by_hash(place_id)
        if cached_data:
            util_logger.info(f"Cache hit for place_id='{place_id}'. Returning cached menu data.")
            return json.loads(cached_data)
        else:
            util_logger.info(f"Cache miss for place_id='{place_id}'. Proceeding with API request.")

        # If no cache, make API request for place details
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            'place_id': place_id,
            'fields': 'url',
            'key': self.api_key
        }
        util_logger.info(f"Making API request to '{details_url}' with params={ {k: v for k, v in params.items() if k != 'key'} }.")

        try:
            response = requests.get(details_url, params=params)
            response.raise_for_status()
            details = response.json()
            util_logger.debug(f"API details response received: {details.get('status', 'No status provided')}.")
        except requests.RequestException as e:
            util_logger.error(f"API request for place details failed: {e}.")
            return None
        except ValueError as e:
            util_logger.error(f"Error parsing JSON response for place details: {e}.")
            return None

        if not details or 'result' not in details or 'url' not in details['result']:
            util_logger.warning(f"No menu URL found for place_id='{place_id}'.")
            return None

        # Save the menu URL in the database
        menu_url = details['result']['url']
        try:
            self.db.save_data(place_id, json.dumps(menu_url))
            util_logger.info(f"Menu URL cached for place_id='{place_id}'.")
        except Exception as e:
            util_logger.error(f"Failed to save menu URL to cache for place_id='{place_id}': {e}.")

        util_logger.info(f"Menu URL for place_id='{place_id}': {menu_url}.")
        return menu_url

    def close_db(self):
        """Close the database connection."""
        try:
            self.db.close()
            util_logger.info("Database connection closed successfully.")
        except Exception as e:
            util_logger.error(f"Error closing database connection: {e}.")


# Example usage
# locator = RestaurantMenuLocator()
# result = locator.search_restaurants_nearby('Houston, TX', 'burger', 5000)
# menu = locator.get_menu('ChIJD7fiBh9u5kcRYJSMaMOCCwQ')
# locator.close_db()
