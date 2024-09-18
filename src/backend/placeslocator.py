from geopy.geocoders import Nominatim

from _utils._util import *  # Ensure this imports UTIL_LOGGER and other necessary utilities
from .cachemanager import CacheManager


class PlaceLocator:
    def __init__(self, db_name="addr_place_rad_to_places", user_agent="place_locator"):
        self.api_key = os.getenv("GOOGLE_API_KEY")  # SANITIZED KEY
        self.cache_manager = CacheManager()
        self.geolocator = Nominatim(user_agent=user_agent)
        UTIL_LOGGER.info(f"PlaceLocator initialized with db_name='{db_name}' and user_agent='{user_agent}'.")

    def get_coordinates(self, address: str) -> Optional[tuple]:
        """Get coordinates of the address."""
        UTIL_LOGGER.info(f"Fetching coordinates for address='{address}'.")
        try:
            location = self.geolocator.geocode(address)
            if location:
                coords = (location.latitude, location.longitude)
                UTIL_LOGGER.info(f"Coordinates for address='{address}': {coords}.")
                return coords
            else:
                UTIL_LOGGER.warning(f"Geocoding failed for address='{address}'. No location found.")
                return None
        except Exception as e:
            UTIL_LOGGER.error(f"Error while geocoding address='{address}': {e}.")
            return None

    def validate_parameters(self, params: dict) -> bool:
        """Validate API request parameters."""
        if params.get('rankby') == 'distance' and 'radius' in params:
            UTIL_LOGGER.error("Radius must not be set when rankby=distance.")
            return False
        if params.get('rankby') == 'distance' and not any(k in params for k in ['keyword', 'name', 'type']):
            UTIL_LOGGER.error("At least one of keyword, name, or type must be specified when rankby=distance.")
            return False
        return True

    def fetch_places(self, coords: tuple, radius: int, establishment_type: str, keyword: Optional[str] = None) -> Optional[dict]:
        """Fetch places from Google Places Nearby Search API."""
        search_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{coords[0]},{coords[1]}",
            'radius': radius,
            'type': establishment_type,
            'key': self.api_key
        }

        if keyword:
            params['keyword'] = keyword

        # Validate parameters before making the request
        if not self.validate_parameters(params):
            return None

        UTIL_LOGGER.info(f"Making API request to '{search_url}' with params={ {k: v for k, v in params.items() if k != 'key'} }.")

        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            response_data = response.json()
            UTIL_LOGGER.debug(f"API response received: {response_data.get('status', 'No status provided')}.")
            return response_data
        except requests.RequestException as e:
            UTIL_LOGGER.error(f"API request failed: {e}.")
            return None
        except ValueError as e:
            UTIL_LOGGER.error(f"Error parsing JSON response: {e}.")
            return None

    def search_establishments_nearby(self, address: str, keyword: str, establishment_types: List[str], radius: int = 16093) -> Optional[List[dict]]:
        """Search for establishments near the location or return cached results."""
        UTIL_LOGGER.info(f"Searching for establishments near address='{address}' with keyword='{keyword}' and radius={radius} meters.")
        hash_key = str((address, keyword, establishment_types, radius))
        
        # Check if data exists in cache
        cached_data = self.cache_manager.get_cached_data('addr_place_rad_to_places', hash_key)
        if cached_data:
            UTIL_LOGGER.debug(f"Cache hit for hash_key='{hash_key}'. Returning cached data.")
            UTIL_LOGGER.debug(f"Cached data=\n`{cached_data}`")
            return json.loads(cached_data)
        else:
            UTIL_LOGGER.debug(f"Cache miss for hash_key='{hash_key}'. Proceeding with API requests.")

        # If no cache, make API requests for each establishment type
        coords = self.get_coordinates(address)
        if not coords:
            UTIL_LOGGER.error(f"Could not retrieve coordinates for address='{address}'. Aborting search.")
            return None

        all_results = []
        for est_type in establishment_types:
            response = self.fetch_places(coords, radius, est_type, keyword)
            if response and 'results' in response:
                all_results.extend(response['results'])

        if all_results:
            # Save the aggregated data in the cache
            try:
                self.cache_manager.set_cached_data('addr_place_rad_to_places', hash_key, json.dumps(all_results))
                UTIL_LOGGER.info(f"Aggregated API response data cached with hash_key='{hash_key}'.")
                UTIL_LOGGER.debug(f"Aggregated API response data=\n`{all_results}`")
            except Exception as e:
                UTIL_LOGGER.error(f"Failed to save data to cache for hash_key='{hash_key}': {e}.")

            return all_results
        else:
            UTIL_LOGGER.warning(f"No results found for address='{address}' with keyword='{keyword}' and radius={radius}.")
            return None

    def get_google_places_url(self, place_id: str) -> Optional[str]:
        """Extract establishment URL from results or return cached results."""
        UTIL_LOGGER.info(f"Retrieving URL for place_id='{place_id}'.")

        # Check if data exists in cache
        cached_data = self.cache_manager.get_cached_data('menu_data', place_id)
        if cached_data:
            UTIL_LOGGER.debug(f"Cache hit for place_id='{place_id}'. Returning cached URL.")
            UTIL_LOGGER.debug(f"Cached URL=\n`{cached_data}`")
            return json.loads(cached_data)
        else:
            UTIL_LOGGER.debug(f"Cache miss for place_id='{place_id}'. Proceeding with API request.")

        # If no cache, make API request for place details
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            'place_id': place_id,
            'fields': 'url',
            'key': self.api_key
        }
        UTIL_LOGGER.info(f"Making API request to '{details_url}' with params={ {k: v for k, v in params.items() if k != 'key'} }.")

        try:
            response = requests.get(details_url, params=params)
            response.raise_for_status()
            details = response.json()
            UTIL_LOGGER.debug(f"API details response received: {details.get('status', 'No status provided')}.")
        except requests.RequestException as e:
            UTIL_LOGGER.error(f"API request for place details failed: {e}.")
            return None
        except ValueError as e:
            UTIL_LOGGER.error(f"Error parsing JSON response for place details: {e}.")
            return None

        if not details or 'result' not in details or 'url' not in details['result']:
            UTIL_LOGGER.warning(f"No URL found for place_id='{place_id}'.")
            return None

        # Save the URL in the cache
        website_url = details['result']['url']
        try:
            self.cache_manager.set_cached_data('menu_data', place_id, json.dumps(website_url))
            UTIL_LOGGER.info(f"URL cached for place_id='{place_id}'.")
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to save URL to cache for place_id='{place_id}': {e}.")

        UTIL_LOGGER.info(f"URL for place_id='{place_id}': {website_url}.")
        return website_url

    def close_db(self):
        """Close the database connection."""
        try:
            self.cache_manager.close()
            UTIL_LOGGER.info("CacheManager closed successfully.")
        except Exception as e:
            UTIL_LOGGER.error(f"Error closing database connection: {e}.")