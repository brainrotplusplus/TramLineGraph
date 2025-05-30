import os
import matplotlib.pyplot as plt
import pandas as pd

# Install necessary libraries if they are not already installed
# This is crucial for the script to run in environments where these might be missing.
try:
    import osmnx as ox
    import geopandas as gpd
except ImportError:
    print("Installing osmnx, geopandas, and matplotlib...")
    os.system("pip install osmnx geopandas matplotlib")
    import osmnx as ox
    import geopandas as gpd

# Define the place for which to download and plot POIs
place_name = "Kraków, Poland"

# Define a dictionary of OpenStreetMap tags for various points of interest (POIs).
# Each key represents a category (e.g., "schools", "museums"), and its value is
# another dictionary containing the OSM tags to query for that category.
# This allows for flexible and extensive data retrieval from OSM.
tags = {
    "schools": {"amenity": "school"},
    "universities": {"amenity": "university"},
    "museums": {"tourism": "museum"},
    "theaters": {"amenity": "theatre"},
    "shops": {"shop": ["supermarket", "retail", "bakery", "clothes", "electronics"]}, # Expanded shop types
    "bars": {"amenity": "bar"},
    "train_stations": {"railway": "station"},
    "bus_stations": {"amenity": "bus_station"},
    "hospitals": {"amenity": "hospital"},
    "restaurants": {"amenity": "restaurant"},
    "pharmacies": {"amenity": "pharmacy"},
    "libraries": {"amenity": "library"},
    "churches": {"amenity": "place_of_worship", "religion": "christian"},
    "parks": {"leisure": "park"},
    "cinemas": {"amenity": "cinema"},
    "post_offices": {"amenity": "post_office"},
    "police_stations": {"amenity": "police"}
}

print(f"Preparing to download Points of Interest (POIs) for {place_name}...")

# Initialize an empty dictionary to store GeoDataFrames for each POI category.
# GeoDataFrames are used to handle geospatial data (points, lines, polygons) with attributes.
all_pois_gdfs = {}

# Iterate through each category and its corresponding OSM tags to download data.
for category, tag_dict in tags.items():
    print(f"Downloading {category} data...")
    try:
        # Use osmnx.features_from_place to query OpenStreetMap for features
        # within the specified place that match the given tags.
        gdf = ox.features_from_place(place_name, tag_dict)

        if not gdf.empty:
            # Add a 'category' column to the GeoDataFrame to easily identify the type of POI.
            gdf['category'] = category
            all_pois_gdfs[category] = gdf
            print(f"Successfully downloaded {len(gdf)} {category} features.")
        else:
            print(f"No {category} features found for {place_name}.")
    except Exception as e:
        # Catch and print any errors that occur during the download process.
        print(f"Error downloading {category}: {e}")

print("All POI data downloads complete.")

# --- Save POI data to a GeoJSON file ---
print("Attempting to save all downloaded POI data to a GeoJSON file...")

# Check if any POI data was successfully downloaded.
if all_pois_gdfs:
    # Determine the Coordinate Reference System (CRS) from the first non-empty GeoDataFrame.
    # It's important that all GeoDataFrames have a consistent CRS for concatenation and saving.
    first_gdf_crs = None
    for gdf in all_pois_gdfs.values():
        if not gdf.empty:
            first_gdf_crs = gdf.crs
            break

    if first_gdf_crs:
        # Concatenate all individual GeoDataFrames into a single GeoDataFrame.
        # Ensure each GeoDataFrame is converted to the common CRS before concatenation.
        # This creates a unified dataset of all POIs.
        combined_pois_gdf = pd.concat([gdf.to_crs(first_gdf_crs) for gdf in all_pois_gdfs.values() if not gdf.empty])

        # Define the output file name for the GeoJSON.
        output_geojson_file = "krakow_pois.geojson"
        try:
            # Save the combined GeoDataFrame to a GeoJSON file.
            # GeoJSON is a standard format for representing simple geographical features.
            combined_pois_gdf.to_file(output_geojson_file, driver='GeoJSON')
            print(f"All POI data successfully saved to {output_geojson_file}.")
        except Exception as e:
            print(f"Error saving POI data to GeoJSON: {e}")
    else:
        print("No valid CRS found from downloaded POI data. Cannot save to GeoJSON.")
else:
    print("No POI data was downloaded; skipping GeoJSON save.")

# --- Plotting the data on a map ---
print("Generating the map with POIs...")

# Create a Matplotlib figure and an axes object for plotting.
# The figsize determines the size of the generated map image.
fig, ax = plt.subplots(figsize=(15, 15))

# Define a color map for different categories of POIs.
# This helps in visually distinguishing different types of points on the map.
colors = {
    "schools": "blue",
    "universities": "purple",
    "museums": "green",
    "theaters": "red",
    "shops": "orange",
    "bars": "brown",
    "train_stations": "black",
    "bus_stations": "gray",
    "hospitals": "cyan",
    "restaurants": "magenta",
    "pharmacies": "lime",
    "libraries": "teal",
    "churches": "darkgoldenrod",
    "parks": "darkgreen",
    "cinemas": "darkviolet",
    "post_offices": "darkblue",
    "police_stations": "darkred"
}

# Plot each category of POIs on the map.
for category, gdf in all_pois_gdfs.items():
    if not gdf.empty:
        # Create a copy to avoid modifying the original GeoDataFrame.
        points_to_plot = gdf.copy()
        # For plotting, ensure all geometries are points. If a feature is a Polygon or LineString,
        # use its centroid as the point to plot. This provides a consistent visual representation.
        points_to_plot['geometry'] = points_to_plot['geometry'].apply(
            lambda geom: geom.centroid if geom.geom_type in ['Polygon', 'LineString'] else geom
        )
        # Plot the points with a specific marker, color, size, and transparency.
        # The 'label' is used for the legend, and 'zorder' controls layer order.
        points_to_plot.plot(ax=ax, marker='o', color=colors.get(category, 'black'),
                            markersize=15, alpha=0.7, label=category, zorder=2)
        print(f"Plotted {category} features.")
    else:
        print(f"No data to plot for {category}.")

# Add a title to the map.
ax.set_title(f"Points of Interest in {place_name}", fontsize=18)
# Add labels for longitude and latitude (though they are turned off for a cleaner look).
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
# Add a legend to explain the different colored points.
# 'loc' and 'bbox_to_anchor' position the legend outside the main plot area.
ax.legend(title="Categories", loc="upper left", bbox_to_anchor=(1, 1))
# Turn off the axis ticks and labels for a cleaner map appearance.
ax.set_axis_off()
# Adjust plot layout to prevent elements from overlapping.
plt.tight_layout()
# Display the generated map.
plt.show()

print("Map generation complete.")