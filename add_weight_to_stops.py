import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import osmnx as ox
import geopandas as gpd
import networkx as nx
import json # To parse the JSON string in graphml data
from shapely.geometry import Point

# Define the place for which to download and plot POIs
place_name = "Kraków, Poland"

# --- Load the tram graph ---
print("Loading the tram graph from krakow_tram_graph.graphml...")
G_tram = None

try:
    G_tram = ox.load_graphml("krakow_tram_graph.graphml")
    print("Tram graph loaded successfully using osmnx.")
except Exception as e:
    print(f"Error loading tram graph with osmnx: {e}. Attempting manual conversion.")
    # Fallback to manual loading with type conversion if osmnx.load_graphml fails
    try:
        G_raw = nx.read_graphml("krakow_tram_graph.graphml")
        G_tram = nx.MultiDiGraph() # Create a new MultiDiGraph for osmnx compatibility

        for u, data in G_raw.nodes(data=True):
            new_u = str(u) # Ensure node ID is a string
            # Ensure 'osmid' and coordinates are correctly typed
            if 'osmid' in data:
                data['osmid'] = str(data['osmid'])
            if 'x' in data and not isinstance(data['x'], float):
                data['x'] = float(data['x'])
            if 'y' in data and not isinstance(data['y'], float):
                data['y'] = float(data['y'])

            # Parse the 'd10' attribute if it exists and is a string
            # Example: <data key="d10">[{"id": 6492, "name": "Os. Piastów 01", "type": "pętla"}]</data>
            if 'd10' in data and isinstance(data['d10'], str):
                try:
                    # Attempt to load as JSON, it might be a list of dicts
                    parsed_d10 = json.loads(data['d10'])
                    # Assuming we care about the first item if it's a list
                    if isinstance(parsed_d10, list) and len(parsed_d10) > 0:
                        for item in parsed_d10:
                            if isinstance(item, dict):
                                # Copy relevant keys to the node data directly
                                if 'name' in item:
                                    data['name'] = item['name']
                                if 'type' in item:
                                    data['type'] = item['type']
                    elif isinstance(parsed_d10, dict): # If it's a single dict
                        if 'name' in parsed_d10:
                            data['name'] = parsed_d10['name']
                        if 'type' in parsed_d10:
                            data['type'] = parsed_d10['type']
                    # Remove the original 'd10' to keep the graph cleaner
                    del data['d10']
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse JSON for node {u}'s d10 attribute.")
            G_tram.add_node(new_u, **data)

        for u, v, key, data in G_raw.edges(keys=True, data=True):
            new_u = str(u)
            new_v = str(v)
            # Ensure 'osmid' and other string attributes are correctly typed for edges
            if 'osmid' in data:
                data['osmid'] = str(data['osmid'])
            G_tram.add_edge(new_u, new_v, key, **data)

        print("Tram graph successfully loaded with manual type conversions and d10 parsing.")

    except Exception as inner_e:
        print(f"Critical error loading tram graph even with manual conversion: {inner_e}")
        print("Please inspect krakow_tram_graph.graphml for corruption or unexpected data types.")
        exit()

if not G_tram.nodes:
    print("Error: The loaded tram graph contains no nodes. Cannot proceed.")
    exit()

# --- Load the POIs from the GeoJSON file ---
print("Loading POI data from krakow_pois.geojson...")
try:
    pois_gdf = gpd.read_file("krakow_pois.geojson")
    print(f"Loaded {len(pois_gdf)} POIs.")
except FileNotFoundError:
    print("Error: krakow_pois.geojson not found. Please ensure it's in the same directory.")
    exit()
except Exception as e:
    print(f"Error loading POI data: {e}")
    exit()

# Ensure the POIs GeoDataFrame has a valid CRS for distance calculations
if pois_gdf.crs is None:
    print("Warning: POIs GeoDataFrame has no CRS. Assuming WGS84 (EPSG:4326).")
    pois_gdf = pois_gdf.set_crs("EPSG:4326", allow_override=True)
elif pois_gdf.crs.to_epsg() != 4326:
    print(f"Reprojecting POIs from {pois_gdf.crs.to_string()} to EPSG:4326 for consistency.")
    pois_gdf = pois_gdf.to_crs(epsg=4326)

# --- Assign importance (weights) to tram stops based on proximity to POIs ---
print("Assigning importance (weights) to tram stops based on proximity to POIs...")

# Define a proximity radius in meters for POIs
proximity_radius_meters = 200

# Reproject POIs to a suitable projected CRS for accurate buffering in meters
# Kraków is around 50.06° N, 19.94° E. UTM Zone 34N is appropriate. EPSG:32634 (WGS 84 / UTM zone 34N)
pois_gdf_proj = pois_gdf.to_crs(epsg=32634)

for node, data in G_tram.nodes(data=True):
    if 'x' in data and 'y' in data:
        stop_point_geom = Point(data['x'], data['y'])
        # Convert the stop point to the projected CRS for distance calculations
        stop_point_proj = gpd.GeoSeries([stop_point_geom], crs="EPSG:4326").to_crs(epsg=32634).iloc[0]

        buffer_zone = stop_point_proj.buffer(proximity_radius_meters)

        # Check for intersection with POIs
        possible_matches_index = list(pois_gdf_proj.sindex.intersection(buffer_zone.bounds))
        nearby_pois = pois_gdf_proj.iloc[possible_matches_index][pois_gdf_proj.iloc[possible_matches_index].intersects(buffer_zone)]

        # Assign weight based on proximity to POIs
        # A simple weighting: count of nearby POIs. More POIs = higher importance.
        G_tram.nodes[node]['importance_weight'] = len(nearby_pois)
        G_tram.nodes[node]['nearby_poi_categories'] = nearby_pois['category'].unique().tolist()
    else:
        G_tram.nodes[node]['importance_weight'] = 0
        G_tram.nodes[node]['nearby_poi_categories'] = []

print("Importance weights assigned to tram stops.")

# --- Identify "pętla" stops ---
pętla_stops = [node for node, data in G_tram.nodes(data=True) if data.get('type') == 'pętla']
print(f"Found {len(pętla_stops)} 'pętla' stops.")

if len(pętla_stops) < 2:
    print("Not enough 'pętla' stops to create a route between them. Exiting.")
    exit()

# --- Find a random route prioritizing high-importance stops ---
print("Finding a random route prioritizing high-importance stops...")

# Select two random distinct 'pętla' stops
start_node, end_node = np.random.choice(pętla_stops, 2, replace=False)

print(f"Random start 'pętla' stop: {G_tram.nodes[start_node].get('name', start_node)}")
print(f"Random end 'pętla' stop: {G_tram.nodes[end_node].get('name', end_node)}")

# Define a custom weight for pathfinding: invert importance so that higher importance
# means a *lower* "cost" to traverse, thus prioritizing them.
# We'll use a small epsilon to avoid division by zero or very large numbers if weight is 0.
for u, v, k, data in G_tram.edges(keys=True, data=True):
    # For edges, we'll try to get the importance of the *destination* node
    # or apply a default if not found.
    # The 'length' attribute is usually used for pathfinding in osmnx
    # We want to make paths through important nodes "cheaper"
    target_node_importance = G_tram.nodes[v].get('importance_weight', 0)
    # The 'weight' for pathfinding typically represents 'cost'.
    # A higher importance should result in a lower cost.
    # Let's say, 'base_cost' (e.g., edge length) / (importance + 1)
    # Adding 1 to importance avoids division by zero and ensures that even
    # stops with 0 importance have a cost.
    # If the graph has 'length' attribute on edges, use it. Otherwise, use a default.
    edge_length = data.get('length', 1) # Default to 1 if no length
    data['weighted_cost'] = edge_length / (target_node_importance + 1)

# Find the shortest path using the 'weighted_cost' attribute
try:
    route = nx.shortest_path(G_tram, source=start_node, target=end_node, weight='weighted_cost')
    print("Route found successfully.")
except nx.NetworkXNoPath:
    print("No path found between the selected 'pętla' stops.")
    route = []

# --- Save the weighted graph ---
output_graphml_file = "krakow_tram_graph_weighted_importance.graphml"
print(f"Saving the weighted tram graph to {output_graphml_file}...")
try:
    ox.save_graphml(G_tram, output_graphml_file)
    print(f"Weighted tram graph successfully saved to {output_graphml_file}.")
except Exception as e:
    print(f"Error saving weighted tram graph: {e}")

# --- Visualize the graph with weighted stops and the route ---
print("Generating visualization of the tram network, weighted stops, and the route...")

fig, ax = plt.subplots(figsize=(18, 18))

# Plot the entire tram network
# Use the 'length' attribute for edge width for a more realistic look
edge_widths = [d.get('length', 1) for u, v, k, d in G_tram.edges(keys=True, data=True)]
# Normalize edge widths for better visualization
if edge_widths:
    max_width = max(edge_widths)
    if max_width > 0:
        edge_widths = [w / max_width * 2 + 0.5 for w in edge_widths] # Scale for visibility
    else:
        edge_widths = [0.5] * len(edge_widths) # All same if no length data

ox.plot_graph_edges(G_tram, ax=ax, plot_width=edge_widths, edge_color='lightgray', edge_alpha=0.6, bgcolor='white', show=False, close=False)


# Plot POIs for context
if not pois_gdf.empty:
    pois_gdf.plot(ax=ax, marker='x', color='green', markersize=20, alpha=0.6, label='POIs', zorder=2)

# Create a GeoDataFrame of tram stops with their weights for plotting
tram_stops_plot_data = []
for node, data in G_tram.nodes(data=True):
    if 'x' in data and 'y' in data:
        tram_stops_plot_data.append({
            'geometry': Point(data['x'], data['y']),
            'osmid': node,
            'importance_weight': data.get('importance_weight', 0),
            'type': data.get('type'),
            'name': data.get('name', 'N/A')
        })
tram_stops_plot_gdf = gpd.GeoDataFrame(tram_stops_plot_data, crs="EPSG:4326")

# Plot weighted tram stops
if not tram_stops_plot_gdf.empty:
    # Plot 'pętla' stops
    pętla_plot_gdf = tram_stops_plot_gdf[tram_stops_plot_gdf['type'] == 'pętla']
    if not pętla_plot_gdf.empty:
        pętla_plot_gdf.plot(ax=ax, marker='s', color='blue', markersize=100, alpha=0.9, label='Pętla Stops', zorder=4)
        # Add labels for pętla stops
        for x, y, label in zip(pętla_plot_gdf.geometry.x, pętla_plot_gdf.geometry.y, pętla_plot_gdf['name']):
            ax.annotate(label, xy=(x, y), xytext=(5, 5), textcoords="offset points", fontsize=8, color='darkblue', weight='bold')

    # Plot other stops, colored by importance
    other_stops_gdf = tram_stops_plot_gdf[tram_stops_plot_gdf['type'] != 'pętla']
    if not other_stops_gdf.empty:
        # Normalize importance for marker size/color
        max_importance = other_stops_gdf['importance_weight'].max()
        if max_importance > 0:
            other_stops_gdf['scaled_importance'] = (other_stops_gdf['importance_weight'] / max_importance)
        else:
            other_stops_gdf['scaled_importance'] = 0

        # Use colormap for importance
        cmap = plt.cm.get_cmap('YlOrRd') # Yellow-Orange-Red for importance
        other_stops_gdf.plot(ax=ax, marker='o',
                             color=[cmap(val) for val in other_stops_gdf['scaled_importance']],
                             markersize=other_stops_gdf['scaled_importance'] * 150 + 20, # Scale size
                             alpha=0.7, label='Tram Stops (Importance)', zorder=3)

# Plot the calculated route
if route:
    ox.plot_graph_route(G_tram, route, ax=ax, route_color='red', route_linewidth=4, route_alpha=0.9, show=False, close=False, zorder=5)
    print("Route plotted in red.")

# Mark start and end nodes of the route
if route:
    start_point = G_tram.nodes[route[0]]
    end_point = G_tram.nodes[route[-1]]
    ax.plot(start_point['x'], start_point['y'], marker='*', color='gold', markersize=25, markeredgecolor='black', label='Route Start', zorder=6)
    ax.plot(end_point['x'], end_point['y'], marker='X', color='darkgreen', markersize=20, markeredgecolor='black', label='Route End', zorder=6)


ax.set_title(f"Kraków Tram Network with POI-Weighted Stops and Random 'Pętla' Route")
ax.legend(title="Legend", loc="upper left", bbox_to_anchor=(1, 1))
ax.set_axis_off()
plt.tight_layout()
plt.show()

print("Map generation complete.")