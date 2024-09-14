from _utils._util import *
from .local_storage import LocalStorage

import hashlib
import requests
from geopy.geocoders import Nominatim



class RestaurantMenuLocator:
    def __init__(self, db_name="addr_rest_rad_to_places.db", user_agent="restaurant_menu_locator"):
        self.api_key = os.getenv("GOOGLE_API_KEY")  # SANATIZED KEY
        self.db = LocalStorage(db_name=db_name)
        self.geolocator = Nominatim(user_agent=user_agent)

    def generate_hash_key(self, address, restaurant_name, radius):
        """Helper function to create a unique hash key from API inputs."""
        hash_input = f"{address}_{restaurant_name}_{radius}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()

    def get_coordinates(self, address):
        """Get coordinates of the address."""
        location = self.geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        return None

    def search_restaurants_nearby(self, address, restaurant_name, radius=5000):
        """Search for restaurants near the location or return cached results."""
        hash_key = self.generate_hash_key(address, restaurant_name, radius)
        
        # Check if data exists in cache
        cached_data = self.db.get_data_by_hash(hash_key)
        if cached_data:
            print("Returning cached data.")
            return json.loads(cached_data)
        
        # If no cache, make API request
        coords = self.get_coordinates(address)
        if not coords:
            print("Could not get coordinates.")
            return None

        print(f"Coordinates for {address}: {coords}")
        search_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            'location': f"{coords[0]},{coords[1]}",
            'radius': radius,  # in meters
            'type': 'food',
            'keyword': restaurant_name,
            'key': self.api_key
        }
        response = requests.get(search_url, params=params)
        response_data = response.json()

        if response_data and 'results' in response_data:
            # Save the data in the database
            self.db.save_data(hash_key, json.dumps(response_data))
        
        return response_data

    def get_menu(self, place_id):
        """Extract restaurant menu from results or return cached results."""
        # Check if data exists in cache
        cached_data = self.db.get_data_by_hash(place_id)
        if cached_data:
            print("Returning cached menu data.")
            return json.loads(cached_data)
        
        # If no cache, make API request for place details
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            'place_id': place_id,
            'fields': 'url',
            'key': self.api_key
        }
        response = requests.get(details_url, params=params)
        details = response.json()
        
        if not details or 'result' not in details or 'url' not in details['result']:
            print(f"No menu found for place ID {place_id}.")
            return None
        
        # Save the menu URL in the database
        menu_url = details['result']['url']
        self.db.save_data(place_id, json.dumps(menu_url))

        print(f"Menu URL: {menu_url}")
        return menu_url

    def close_db(self):
        """Close the database connection."""
        self.db.close()

# Example usage
# locator = RestaurantMenuLocator()
# result = locator.search_restaurants_nearby('Houston, TX', 'burger', 5000)
# menu = locator.get_menu('ChIJD7fiBh9u5kcRYJSMaMOCCwQ')
# locator.close_db()
