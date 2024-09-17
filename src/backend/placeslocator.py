from _utils._util import *
from web.cachemanager import CacheManager

import requests
from geopy.geocoders import Nominatim


class PlaceLocator:
    def __init__(self, db_name="addr_place_rad_to_places", user_agent="place_locator"):
        self.api_key = os.getenv("GOOGLE_API_KEY")  # SANITIZED KEY
        self.cache_manager = CacheManager()
        self.geolocator = Nominatim(user_agent=user_agent)
        util_logger.info(f"PlaceLocator initialized with db_name='{db_name}' and user_agent='{user_agent}'.")

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

    def search_establishments_nearby(self, address, keyword, establishment_type, radius=5000):
        """Search for establishments near the location or return cached results."""
        util_logger.info(f"Searching for establishments near address='{address}' with param='{keyword}' and radius={radius} meters.")
        hash_key = str((address, keyword, radius))
        
        # Check if data exists in cache
        cached_data = self.cache_manager.get_cached_data('addr_place_rad_to_places', hash_key)
        if cached_data:
            util_logger.debug(f"Cache hit for hash_key='{hash_key}'. Returning cached data.")
            return json.loads(cached_data)
        else:
            util_logger.debug(f"Cache miss for hash_key='{hash_key}'. Proceeding with API request.")

        # If no cache, make API request
        coords = self.get_coordinates(address)
        if not coords:
            util_logger.error(f"Could not retrieve coordinates for address='{address}'. Aborting search.")
            return None

        search_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{coords[0]},{coords[1]}",
            'radius': radius,  # Use radius with rankby='prominence'
            'type': establishment_type,
            'keyword': keyword,
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
            # Save the data in the cache
            try:
                self.cache_manager.set_cached_data('addr_place_rad_to_places', hash_key, json.dumps(response_data))
                util_logger.info(f"API response data cached with hash_key='{hash_key}'.")
            except Exception as e:
                util_logger.error(f"Failed to save data to cache for hash_key='{hash_key}': {e}.")
        
        return response_data

    def get_google_places_url(self, place_id):
        """Extract establishment URL from results or return cached results."""
        util_logger.info(f"Retrieving URL for place_id='{place_id}'.")
        
        # Check if data exists in cache
        cached_data = self.cache_manager.get_cached_data('menu_data', place_id)
        if cached_data:
            util_logger.debug(f"Cache hit for place_id='{place_id}'. Returning cached URL.")
            return json.loads(cached_data)
        else:
            util_logger.debug(f"Cache miss for place_id='{place_id}'. Proceeding with API request.")

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
            util_logger.warning(f"No URL found for place_id='{place_id}'.")
            return None

        # Save the URL in the cache
        website_url = details['result']['url']
        try:
            self.cache_manager.set_cached_data('menu_data', place_id, json.dumps(website_url))
            util_logger.info(f"URL cached for place_id='{place_id}'.")
        except Exception as e:
            util_logger.error(f"Failed to save URL to cache for place_id='{place_id}': {e}.")

        util_logger.info(f"URL for place_id='{place_id}': {website_url}.")
        return website_url

    def close_db(self):
        """Close the database connection."""
        try:
            self.cache_manager.close()
            util_logger.info("CacheManager closed successfully.")
        except Exception as e:
            util_logger.error(f"Error closing database connection: {e}.")


