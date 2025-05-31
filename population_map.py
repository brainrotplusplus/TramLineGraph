import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
import math

# --- Step 1: Load the Excel file ---
df = pd.read_excel("ludnosc_dane.xlsx")

# --- Step 2: Calculate the total number of residents ---
df["Liczba mieszkańców"] = (df["Liczba osób zameldowanych na stałe"] + 
                             df["Liczba osób zameldowanych czasowo"])

# --- Step 3: Create a GeoDataFrame with points ---
# We assume the two coordinate columns represent X and Y coordinates in PL-2000 (EPSG:2178).
# Note: be sure that you pass the correct columns to points_from_xy.
gdf_points = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Współrzędna Y (układ PL-2000)"],
                                df["Współrzędna X (układ PL-2000)"]),
    crs="EPSG:2178"  # PL-2000 Zone 3, suitable for the local area
)

# --- Function: create a hexagon polygon ---
def create_hexagon(center, radius):
    """
    Create a regular hexagon polygon centered at 'center'
    with each vertex 'radius' distance away from the center.
    
    Parameters:
        center (tuple): The (x, y) coordinate of the center.
        radius (float): Distance from the center to each vertex (in meters).
        
    Returns:
        shapely.geometry.Polygon: Hexagon polygon.
    """
    cx, cy = center
    angles = [math.radians(60 * i) for i in range(6)]
    points = [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]
    return Polygon(points)

# --- Step 4: Replace points with hexagon polygons in the original projection ---
# Create a new geometry column with hexagons.
radius = 250
gdf_hex = gdf_points.copy()
gdf_hex["geometry"] = gdf_hex.geometry.apply(
    lambda point: create_hexagon((point.x, point.y), radius)
)

# --- Step 5: Convert the hexagon GeoDataFrame to WGS84 (EPSG:4326) ---
gdf_hex_wgs84 = gdf_hex.to_crs("EPSG:4326")

# --- Step 6: Plot the hexagon GeoDataFrame with a base map for verification ---
fig, ax = plt.subplots(figsize=(12, 12))

# Plot the hexagons
gdf_hex_wgs84.plot(ax=ax, facecolor='none', edgecolor='blue', linewidth=1.5, alpha=0.8, label='Residential Hexagons')

# Add title and labels
ax.set_title('Population Distribution Hexagons in WGS84', fontsize=16)
ax.set_xlabel('Longitude (WGS84)', fontsize=12)
ax.set_ylabel('Latitude (WGS84)', fontsize=12)

# Add a legend
ax.legend()

# --- Step 7: Export hexagons to GeoJSON ---
# Save the hexagons with population data to GeoJSON file
output_file = "population_hexagons.geojson"
gdf_hex_wgs84.to_file(output_file, driver='GeoJSON')
print(f"Hexagons exported to: {output_file}")

# Adjust layout and show the plot
plt.tight_layout()
plt.show()
