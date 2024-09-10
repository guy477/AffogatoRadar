import requests
from geopy.geocoders import Nominatim
import hashlib
from .local_storage import LocalStorage
from ._util import *

# SANATIZED KEY
api_key = os.getenv("GOOGLE_API_KEY")

# Helper function to create a unique hash key from API inputs
def generate_hash_key(address, restaurant_name, radius):
    hash_input = f"{address}_{restaurant_name}_{radius}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

# Step 1: Get coordinates of the address
def get_coordinates(address):
    geolocator = Nominatim(user_agent="restaurant_menu_locator")
    location = geolocator.geocode(address)
    return (location.latitude, location.longitude)

# Step 2: Search for restaurants near the location or return cached results
def search_restaurants_nearby(address, restaurant_name, radius=5000):
    db = LocalStorage(db_name="addr_rest_rad_to_places.db")

    hash_key = generate_hash_key(address, restaurant_name, radius)
    
    # Check if data exists in cache
    cached_data = db.get_data_by_hash(hash_key)
    if cached_data:
        print("Returning cached data.")
        return json.loads(cached_data)

    # If no cache, make API request
    coords = get_coordinates(address)
    print(coords)
    search_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        'location': f"{coords[0]},{coords[1]}",
        'radius': radius,  # in meters
        'type': 'restaurant',
        'keyword': restaurant_name,
        'key': api_key
    }
    response = requests.get(search_url, params=params)
    response_data = response.json()

    if response_data and response_data['results']:
        # Save the data in the database
        db.save_data(hash_key, json.dumps(response_data))

    db.close()

    return response_data

# Step 3: Extract restaurant menu from results
def get_menu(place_id):
    db = LocalStorage(db_name="addr_rest_rad_to_places.db")

    details_url = f"https://maps.googleapis.com/maps/api/place/details/json"
    
    # Check if data exists in cache
    cached_data = db.get_data_by_hash(place_id)
    if cached_data:
        print("Returning cached data.")
        return json.loads(cached_data)
    
    params = {
        'place_id': place_id,
        'fields': 'url',
        'key': api_key
    }
    response = requests.get(details_url, params=params)
    details = response.json()
    print(details)
    
    if not details or 'result' not in details or 'url' not in details['result']:
        return None

    # Save the data in the database
    db.save_data(place_id, json.dumps(details['result']['url']))

    db.close()

    return details['result']['url']
