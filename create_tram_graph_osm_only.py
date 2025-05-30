import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString
import os
import json

# ---------------------------
# 1. Load the tram network graph
# ---------------------------
place_name = "Kraków, Poland"
# Custom filter to specifically get tram lines (railway=tram)
custom_filter = '["railway"~"tram"]'
print(f"Loading tram graph for {place_name} with filter: {custom_filter}...")
# Retrieve the graph from OSM, simplifying is set to False to retain original topology
tram_graph = ox.graph_from_place(place_name, simplify=False, custom_filter=custom_filter)
print("Tram graph loaded successfully.")

# Convert the graph to GeoDataFrames for easier manipulation of nodes and edges
nodes_gdf, edges_gdf = ox.graph_to_gdfs(tram_graph, nodes=True, edges=True)
print(f"Graph has {len(nodes_gdf)} nodes and {len(edges_gdf)} edges.")

# ---------------------------
# 2. Download tram stops from OpenStreetMap and load from local GeoJSON
# ---------------------------
print(f"Downloading tram stops for {place_name} from OpenStreetMap...")
# Define tags to query for tram stops. 'railway=tram_stop' is a common tag.
tags = {'railway': 'tram_stop'}
# Use ox.features_from_place to get all features matching the tags within the specified place
stops_osm_gdf = ox.features_from_place(place_name, tags)
print(f"Downloaded {len(stops_osm_gdf)} tram stops from OSM.")

# Ensure the OSM stops_gdf has the same CRS as the graph nodes for spatial operations
stops_osm_gdf = stops_osm_gdf.to_crs(nodes_gdf.crs)

geojson_tram_stops_file = "Przystanki_Komunikacji_Miejskiej_w_Krakowie_6ab29dbb62854448803c0125c291aca3.geojson"
stops_geojson_gdf = None
geojson_stops_lookup = {} # Dictionary for efficient lookup of GeoJSON stops by name

if os.path.exists(geojson_tram_stops_file):
    print(f"Loading tram stops from local GeoJSON file: {geojson_tram_stops_file}...")
    stops_geojson_gdf = gpd.read_file(geojson_tram_stops_file).to_crs(nodes_gdf.crs)
    print(f"Loaded {len(stops_geojson_gdf)} tram stops from GeoJSON.")

    # Create a lookup dictionary for GeoJSON stops by their 'Nazwa_przystanku_nr' for faster matching
    for idx, stop in stops_geojson_gdf.iterrows():
        # Convert name to lowercase for case-insensitive matching
        stop_name = stop['Nazwa_przystanku_nr'].lower()
        geojson_stops_lookup[stop_name] = stop
else:
    print(f"Warning: GeoJSON file '{geojson_tram_stops_file}' not found. Only OSM data will be used for tram stops.")


# ---------------------------
# 3. Snap stops to nearest nodes and build a stop-to-node mapping
#    Prioritize GeoJSON data for ID and specific parameters if a name match is found.
#    Only add stops if they are found in OSM AND (matched in GeoJSON or GeoJSON file is not present).
# ---------------------------
# Create a copy of the graph to modify it
G = tram_graph.copy()
print("Graph copied for processing.")

stop_to_node = {}
print("Snapping tram stops to the nearest graph nodes and merging data...")

# Iterate through each tram stop downloaded from OSM
for idx, stop_osm in stops_osm_gdf.iterrows():
    # Determine the coordinates for snapping from the OSM data
    if stop_osm.geometry.geom_type == 'Point':
        x, y = stop_osm.geometry.x, stop_osm.geometry.y
    elif stop_osm.geometry.geom_type in ['LineString', 'Polygon']:
        x, y = stop_osm.geometry.centroid.x, stop_osm.geometry.centroid.y
    else:
        print(f"Warning: Unsupported geometry type '{stop_osm.geometry.geom_type}' for OSM stop {idx}. Skipping.")
        continue

    # Initialize stop_data with OSM information as a fallback
    stop_data = {
        "id": idx, # Default to OSM ID
        "name": stop_osm.get('name', f"Stop {idx}"), # Default to OSM name
        "type": stop_osm.get('railway', 'tram_stop') # Default to OSM railway tag
    }

    should_add_stop = True # Flag to control if the stop should be added to the graph

    # Attempt to find a matching stop in the GeoJSON data based on name
    osm_stop_name = stop_osm.get('name')
    if stops_geojson_gdf is not None: # Only try to match if GeoJSON was successfully loaded
        if osm_stop_name:
            # Convert OSM name to lowercase for case-insensitive lookup
            matched_geojson_stop = geojson_stops_lookup.get(osm_stop_name.lower())
            
            if matched_geojson_stop is not None:
                # If a match is found, update stop_data with parameters from the GeoJSON file
                stop_data["id"] = matched_geojson_stop['OBJECTID'] # Use ID from GeoJSON
                stop_data["name"] = matched_geojson_stop['Nazwa_przystanku_nr'] # Use name from GeoJSON
                stop_data["type"] = matched_geojson_stop['Rodzaj_przystanku'] # Use type from GeoJSON
                print(f"Matched OSM stop '{osm_stop_name}' (OSM ID: {idx}) with GeoJSON stop '{matched_geojson_stop['Nazwa_przystanku_nr']}' (GeoJSON ID: {matched_geojson_stop['OBJECTID']}).")
            else:
                # No GeoJSON match found for this OSM stop, and GeoJSON file exists, so do not add this stop.
                should_add_stop = False
                print(f"No GeoJSON match found for OSM stop '{osm_stop_name}' (OSM ID: {idx}). Skipping this stop.")
        else:
            # OSM stop has no name, and GeoJSON file exists, so cannot match. Do not add this stop.
            should_add_stop = False
            print(f"OSM stop {idx} has no name. Cannot match with GeoJSON data. Skipping this stop.")
    # If stops_geojson_gdf is None (meaning the file wasn't found), then should_add_stop remains True,
    # and all OSM stops will be added using their default OSM attributes.

    if should_add_stop:
        # Find the nearest graph node to the current (OSM-derived) coordinates
        nearest_node = ox.distance.nearest_nodes(G, x, y)
        # Map the stop's ID (from GeoJSON if matched, else OSM) to its nearest graph node
        stop_to_node[stop_data["id"]] = nearest_node

        # Add the stop data as an attribute to the nearest graph node.
        G.nodes[nearest_node].setdefault('stops', []).append(stop_data)

# Convert the 'stops' attribute from a list of dictionaries to a JSON string.
for n, data in G.nodes(data=True):
    if "stops" in data and isinstance(data["stops"], list):
        data["stops"] = json.dumps(data["stops"], ensure_ascii=False)

print("Tram stops snapped and assigned to graph nodes, with GeoJSON data integrated where matched.")

# ---------------------------
# 4. Remove railway_crossing nodes and reconnect edges
# ---------------------------
print("Identifying and processing railway_crossing nodes for removal and reconnection...")

nodes_to_remove = []
# Iterate through all nodes in the graph to identify railway_crossing nodes
for node_id, data in G.nodes(data=True):
    # Check if the node has a 'railway' tag and if its value is 'railway_crossing'
    if 'railway' in data and data['railway'] == 'railway_crossing':
        nodes_to_remove.append(node_id)
        # Add a flag to the node data indicating it's a railway crossing
        data['is_railway_crossing'] = True
        data['is_railway_switch'] = False # Ensure switch flag is false
    # Also identify railway switches, but these are not removed
    elif 'railway' in data and data['railway'] == 'switch':
        data['is_railway_switch'] = True
        data['is_railway_crossing'] = False # Ensure crossing flag is false
    else:
        data['is_railway_crossing'] = False # Default to false for other nodes
        data['is_railway_switch'] = False # Default to false for other nodes

print(f"Found {len(nodes_to_remove)} railway_crossing nodes identified for removal.")

# Process each identified railway_crossing node
for node_id in nodes_to_remove:
    # Check if the node still exists in the graph (it might have been removed by a previous iteration)
    if node_id not in G:
        continue

    # Get incoming and outgoing edges of the node to be removed
    in_edges = list(G.in_edges(node_id, data=True, keys=True))
    out_edges = list(G.out_edges(node_id, data=True, keys=True))
    connections_to_add = [] # List to store new edges that will bypass the removed node

    # For each incoming edge, connect its source node to the destination of each outgoing edge
    for u, _, k_in, data_in in in_edges:
        for _, v, k_out, data_out in out_edges:
            # Get OSM IDs of the original ways to ensure we connect segments of the same way
            osmid_in = data_in.get('osmid', [])
            osmid_out = data_out.get('osmid', [])

            # Ensure osmid is a list for consistent processing
            if not isinstance(osmid_in, list):
                osmid_in = [osmid_in]
            if not isinstance(osmid_out, list):
                osmid_out = [osmid_out]

            # Only connect if the incoming and outgoing edges belong to the same original OSM way
            if set(osmid_in) & set(osmid_out):
                # Combine attributes from the incoming and outgoing edges for the new edge
                combined_attrs = data_in.copy()
                # Sum the lengths of the original segments
                if 'length' in data_out:
                    combined_attrs['length'] = combined_attrs.get('length', 0) + data_out['length']
                
                # Attempt to merge geometries if both original edges have them
                if 'geometry' in data_in and 'geometry' in data_out:
                    try:
                        # Check if both geometries are LineStrings and if they connect end-to-start
                        if isinstance(data_in['geometry'], LineString) and isinstance(data_out['geometry'], LineString):
                            if data_in['geometry'].coords[-1] == data_out['geometry'].coords[0]:
                                # If they connect, merge their coordinates to form a single LineString
                                combined_attrs['geometry'] = LineString(
                                    list(data_in['geometry'].coords) + list(data_out['geometry'].coords)[1:]
                                )
                            else:
                                # If coordinates don't match, warn and remove geometry to avoid incorrect shapes
                                print(f"Warning: Geometries for node {node_id} could not be precisely merged due to coordinate mismatch. Geometry attribute for new edge will be removed to avoid incorrect shapes.")
                                combined_attrs.pop('geometry', None)
                        else:
                            # If geometries are not LineStrings, remove geometry attribute
                            combined_attrs.pop('geometry', None)
                    except Exception as e:
                        # Catch any errors during geometry merging and remove the attribute
                        print(f"Error merging geometries for node {node_id}: {e}. Geometry attribute removed.")
                        combined_attrs.pop('geometry', None)

                # Add the new connection to the list
                connections_to_add.append((u, v, combined_attrs))

    # Add all new edges to the graph
    for u, v, attrs in connections_to_add:
        G.add_edge(u, v, **attrs)

    # Finally, remove the railway_crossing node from the graph
    G.remove_node(node_id)
    print(f"Removed railway_crossing node {node_id} and reconnected its original ways.")

print("Finished processing railway_crossing nodes. Graph topology modified as requested.")

# Save the modified graph to GraphML format
output_graphml_file = "krakow_tram_graph.graphml"
nx.write_graphml(G, output_graphml_file)
print(f"Graph successfully saved to {output_graphml_file}. Railway_crossing nodes have been removed and ways reconnected.")
