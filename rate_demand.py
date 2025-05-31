import json
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

# --- Load GeoJSON data from file ---
geojson_file = "krakow_pois.geojson"
try:
    with open(geojson_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"Error: The file '{geojson_file}' was not found. Please ensure it's in the same directory as the script.")
    print("A sample GeoJSON content was provided in the previous turn. Please save it as 'krakow_pois.geojson'.")
    exit() # Exit if the file is not found

# Determine if the GeoJSON is a FeatureCollection or a single Feature
if data.get("type") == "FeatureCollection":
    features = data.get("features", [])
elif data.get("type") == "Feature":
    features = [data]
else:
    raise ValueError("Unsupported GeoJSON format")

# --- Define base weights for different categories ---
base_category_weights = {
    "schools": 1.5,
    "universities": 2.0,
    "museums": 1.8,
    "theaters": 1.8,
    "shops": 1.0,
    "bars": 1.4,
    "train_stations": 4.5,
    "bus_stations": 1.5,
    "hospitals": 3.0,
    "restaurants": 1.3,
    "pharmacies": 1.0,
    "libraries": 1.2,
    "churches": 1.0,
    "parks": 1.8,
    "cinemas": 1.5,
    "post_offices": 4.0,
    "police_stations": 1.6
}

default_weight = 0.5 # Weight for categories not explicitly listed

# --- Categories to be affected by specific demand functions ---
# Tylko bary są objęte funkcją nocną
night_affected_categories = {"bars"}
# Pozostałe kategorie z base_category_weights będą objęte funkcją dzienną.

# --- Demand functions for animation ---
def day_demand_function_chart(x_input):
    #  y=-0.5 (x^(2)-1.5) (x^(2)+0.8)
    # <-1.2;1.2>
    x_prime = -1.2 + (2.4 * x_input / 23)
    y_value = -0.5 * (x_prime**2 - 1.5) * (x_prime**2 + 0.8)
    return y_value

def night_demand_function_chart(x_input):
    # y=(((x)/(2)))^(2) + 0.2
    # <-1.2;1.2>
    x_prime = -1.2 + (2.4 * x_input / 23) + 0.4
    y_value = ((x_prime/2)**2)
    return y_value

# --- Prepare initial data for heatmap ---
latitudes = []
longitudes = []
feature_categories = [] # Store categories to re-apply weights during animation

for feature in features:
    if "properties" not in feature:
        feature["properties"] = {}

    category = None
    # Determine the category based on 'amenity', 'shop', or 'category' property
    if "amenity" in feature["properties"] and feature["properties"]["amenity"] in base_category_weights:
        category = feature["properties"]["amenity"]
    elif "shop" in feature["properties"] and feature["properties"]["shop"] in base_category_weights:
        category = feature["properties"]["shop"]
    elif "category" in feature["properties"] and feature["properties"]["category"] in base_category_weights:
        category = feature["properties"]["category"]

    geometry = feature.get("geometry")
    if geometry and geometry.get("type") == "Point":
        coordinates = geometry.get("coordinates")
        if coordinates and len(coordinates) >= 2:
            lon, lat = coordinates[:2]
            longitudes.append(lon)
            latitudes.append(lat)
            feature_categories.append(category) # Store the determined category
        else:
            pass
    else:
        pass

# --- Set up the plot for animation ---
fig, ax = plt.subplots(figsize=(12, 10))

# Initialize the hexbin plot with dummy data or initial weights
hb = ax.hexbin(longitudes, latitudes, C=None, reduce_C_function=np.sum,
               gridsize=50, cmap="Reds", mincnt=1)
cb = fig.colorbar(hb, ax=ax, label="Total Weighted Demand in Bin")

ax.set_title("Animated Weighted Heatmap of Krakow POIs")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.grid(True, linestyle='--', alpha=0.6)

# Set initial limits to ensure consistent view, even if no points are shown initially
if longitudes and latitudes:
    ax.set_xlim(min(longitudes) - 0.01, max(longitudes) + 0.01)
    ax.set_ylim(min(latitudes) - 0.01, max(latitudes) + 0.01)
else:
    # Fallback for empty data, adjust as needed for your specific map area
    ax.set_xlim(19.85, 20.1)
    ax.set_ylim(50.0, 50.1)

# --- Animation function ---
def update(frame):
    day_multiplier = day_demand_function_chart(frame)
    night_multiplier = night_demand_function_chart(frame)

    # Ensure multipliers don't become negative or zero for visualization
    if day_multiplier < 0:
        day_multiplier = 0.001
    if night_multiplier < 0:
        night_multiplier = 0.001

    animated_weights = []
    for i, category in enumerate(feature_categories):
        base_w = base_category_weights.get(category, default_weight)

        # Apply night multiplier only to bars
        if category in night_affected_categories:
            animated_weights.append(base_w * night_multiplier)
        # Apply day multiplier to all other categories that have a base weight
        elif category in base_category_weights:
            animated_weights.append(base_w * day_multiplier)
        # For categories not in base_category_weights, use default_weight (unaffected by multipliers)
        else:
            animated_weights.append(base_w)

    # Remove existing hexbin collections before drawing new one
    for collection in ax.collections:
        if isinstance(collection, type(hb)):
            collection.remove()

    new_hb = ax.hexbin(longitudes, latitudes, C=animated_weights, reduce_C_function=np.sum,
                       gridsize=50, cmap="Reds", mincnt=1)

    cb.update_normal(new_hb)
    cb.set_label("Total Weighted Demand in Bin")

    ax.set_title(f"Animated Heatmap (Krok: {frame}, Popyt Dzienny: {day_multiplier:.2f}, Popyt Nocny (Bary): {night_multiplier:.2f})")
    return new_hb,

# --- Create and save the animation ---
anim = FuncAnimation(fig, update, frames=range(24), blit=False, repeat=False, interval=50)

try:
    print("Próba zapisania animacji do pliku 'krakow_heatmap_day_all_night_bars_demand.gif'...")
    anim.save('krakow_heatmap_day_all_night_bars_demand.gif', writer='pillow', fps=5)
    print("Animacja została zapisana jako 'krakow_heatmap_day_all_night_bars_demand.gif'.")
except Exception as e:
    print(f"Błąd podczas zapisywania animacji: {e}")
    print("Upewnij się, że masz zainstalowany 'pillow' (pip install pillow) lub odpowiedni 'writer' (np. 'imagemagick'/'ffmpeg') i jest on w PATH.")

# plt.show() # Odkomentuj, jeśli chcesz spróbować wyświetlić interaktywnie