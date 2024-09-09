import requests
from geopy.geocoders import Nominatim
import hashlib
from ._util import *

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
def search_restaurants_nearby(api_key, address, restaurant_name, radius=5000, db = None):
    hash_key = generate_hash_key(address, restaurant_name, radius)
    
    # Check if data exists in cache
    cached_data = db.get_data_by_hash(hash_key)
    if cached_data:
        print("Returning cached data.")
        return json.loads(cached_data)

    # If no cache, make API request
    coords = get_coordinates(address)
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

    # Save the data in the database
    db.save_data(hash_key, json.dumps(response_data))

    return response_data

# Step 3: Extract restaurant menu from results
def get_menu(api_key, place_id):
    details_url = f"https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        'place_id': place_id,
        'fields': 'url',
        'key': api_key
    }
    response = requests.get(details_url, params=params)
    details = response.json()
    
    if 'url' in details['result']:
        return details['result']['url']
    else:
        return None
