from geopy.geocoders import Nominatim

from _utils._util import *  # Ensure this imports UTIL_LOGGER and other necessary utilities
from .cachemanager import CacheManager


class GooglePlacesClient:
    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self, api_key: str, cache_manager: CacheManager):
        self.api_key = api_key
        self.cache_manager = cache_manager
        UTIL_LOGGER.info("GooglePlacesClient initialized with provided API key.")

    def _make_request(self, endpoint: str, params: dict) -> Optional[dict]:
        """Make a GET request to the specified Google Places API endpoint."""
        url = f"{self.BASE_URL}/{endpoint}/json"
        UTIL_LOGGER.info(f"Making API request to '{url}' with params={ {k: v for k, v in params.items() if k != 'key'} }.")
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            response_data = response.json()
            UTIL_LOGGER.debug(f"API response received: {response_data.get('status', 'No status provided')}.")
            return response_data
        except requests.RequestException as e:
            UTIL_LOGGER.error(f"API request to {endpoint} failed: {e}.")
            return None
        except ValueError as e:
            UTIL_LOGGER.error(f"Error parsing JSON response from {endpoint}: {e}.")
            return None

    def get_place_details_url(self, place_id: str) -> Optional[str]:
        """Retrieve the URL for a given place_id."""
        UTIL_LOGGER.info(f"Retrieving URL for place_id='{place_id}'.")
        cached_url = self.cache_manager.get_cached_data('menu_data', place_id)
        if cached_url:
            UTIL_LOGGER.debug(f"Cache hit for place_id='{place_id}'. Returning cached URL.")
            return json.loads(cached_url)

        UTIL_LOGGER.debug(f"Cache miss for place_id='{place_id}'. Proceeding with API request.")
        params = {
            'place_id': place_id,
            'fields': 'url',
            'key': self.api_key
        }
        details = self._make_request('details', params)
        if details and 'result' in details and 'url' in details['result']:
            website_url = details['result']['url']
            self.cache_manager.set_cached_data('menu_data', place_id, json.dumps(website_url))
            UTIL_LOGGER.info(f"URL cached for place_id='{place_id}'.")
            UTIL_LOGGER.info(f"URL for place_id='{place_id}': {website_url}.")
            return website_url

        UTIL_LOGGER.warning(f"No URL found for place_id='{place_id}'.")
        return None


class PlaceLocator:
    def __init__(self, db_name: str = "addr_place_rad_to_places", user_agent: str = "place_locator"):
        self.api_key = os.getenv("GOOGLE_API_KEY")  # SANITIZED KEY
        self.cache_manager = CacheManager()
        self.geolocator = Nominatim(user_agent=user_agent, timeout=2)
        self.google_places_client = GooglePlacesClient(self.api_key, self.cache_manager)
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
            UTIL_LOGGER.warning(f"Geocoding failed for address='{address}'. No location found.")
            return None
        except Exception as e:
            UTIL_LOGGER.error(f"Error while geocoding address='{address}': {e}.")
            return None

    def validate_parameters(self, params: dict) -> bool:
        """Validate API request parameters."""
        if params.get('rankby') == 'distance':
            if 'radius' in params:
                UTIL_LOGGER.error("Radius must not be set when rankby=distance.")
                return False
            if not any(k in params for k in ['keyword', 'name', 'type']):
                UTIL_LOGGER.error("At least one of keyword, name, or type must be specified when rankby=distance.")
                return False
        return True

    def fetch_places(self, coords: tuple, radius: int, establishment_type: str, keyword: Optional[str] = None) -> Optional[dict]:
        """Fetch places from Google Places Nearby Search API."""
        params = {
            'location': f"{coords[0]},{coords[1]}",
            'radius': radius,
            'type': establishment_type,
            'key': self.api_key
        }
        if keyword:
            params['keyword'] = keyword

        if not self.validate_parameters(params):
            return None

        return self.google_places_client._make_request('nearbysearch', params)

    def search_establishments_nearby(self, address: str, keyword: str, establishment_types: List[str], radius: int = 16093) -> Optional[List[dict]]:
        """Search for establishments near the location or return cached results."""
        UTIL_LOGGER.info(f"Searching for establishments near address='{address}' with keyword='{keyword}' and radius={radius} meters.")
        hash_key = str((address, keyword, establishment_types, radius))

        cached_data = self.cache_manager.get_cached_data('addr_place_rad_to_places', hash_key)
        if cached_data:
            UTIL_LOGGER.debug(f"Cache hit for hash_key='{hash_key}'. Returning cached data.")
            return json.loads(cached_data)

        UTIL_LOGGER.debug(f"Cache miss for hash_key='{hash_key}'. Proceeding with API requests.")
        coords = self.get_coordinates(address)
        if not coords:
            UTIL_LOGGER.error(f"Could not retrieve coordinates for address='{address}'. Aborting search.")
            return None

        all_results = self._aggregate_establishment_results(establishment_types, coords, radius, keyword)
        if all_results:
            self._cache_aggregated_results(hash_key, all_results)
            return all_results

        UTIL_LOGGER.warning(f"No results found for address='{address}' with keyword='{keyword}' and radius={radius}.")
        return None

    def _aggregate_establishment_results(self, establishment_types: List[str], coords: tuple, radius: int, keyword: Optional[str]) -> List[dict]:
        """Aggregate results from multiple establishment type searches."""
        all_results = []
        for est_type in establishment_types:
            response = self.fetch_places(coords, radius, est_type, keyword)
            if response and 'results' in response:
                all_results.extend(response['results'])
        return all_results

    def _cache_aggregated_results(self, hash_key: str, all_results: List[dict]) -> None:
        """Cache the aggregated API response data."""
        try:
            self.cache_manager.set_cached_data('addr_place_rad_to_places', hash_key, json.dumps(all_results))
            UTIL_LOGGER.info(f"Aggregated API response data cached with hash_key='{hash_key}'.")
            UTIL_LOGGER.debug(f"Aggregated API response data=\n`{all_results}`")
        except Exception as e:
            UTIL_LOGGER.error(f"Failed to save data to cache for hash_key='{hash_key}': {e}.")

    def get_google_places_url(self, place_id: str) -> Optional[str]:
        """Extract establishment URL from results or return cached results."""
        return self.google_places_client.get_place_details_url(place_id)

    def close_db(self):
        """Close the database connection."""
        try:
            self.cache_manager.close()
            UTIL_LOGGER.info("CacheManager closed successfully.")
        except Exception as e:
            UTIL_LOGGER.error(f"Error closing database connection: {e}.")