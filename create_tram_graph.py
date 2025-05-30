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
custom_filter = '["railway"~"tram"]'
print(f"Loading tram graph for {place_name} with filter: {custom_filter}...")
tram_graph = ox.graph_from_place(place_name, simplify=False, custom_filter=custom_filter)
print("Tram graph loaded successfully.")

nodes_gdf, edges_gdf = ox.graph_to_gdfs(tram_graph, nodes=True, edges=True)
print(f"Graph has {len(nodes_gdf)} nodes and {len(edges_gdf)} edges.")

# ---------------------------
# 2. Load and reproject the tram stops
# ---------------------------
geojson_tram_stops = "Przystanki_Komunikacji_Miejskiej_w_Krakowie_6ab29dbb62854448803c0125c291aca3.geojson"
stops_gdf = None 

if os.path.exists(geojson_tram_stops):
    print(f"Loading tram stops from {geojson_tram_stops}...")
    stops_gdf = gpd.read_file(geojson_tram_stops).to_crs(nodes_gdf.crs)
    print(f"Loaded {len(stops_gdf)} tram stops.")
else:
    print(f"Warning: GeoJSON file '{geojson_tram_stops}' not found. Skipping tram stop processing.")

# ---------------------------
# 3. Snap stops to nearest nodes and build a stop-to-node mapping
# ---------------------------
G = tram_graph.copy()
print("Graph copied for processing.")

# Snapping tram stops to the nearest graph nodes
if stops_gdf is not None:
    stop_to_node = {}
    print("Snapping tram stops to the nearest graph nodes...")

    for idx, stop in stops_gdf.iterrows():
        stop_data = {
            "id": stop['OBJECTID'],
            "name": stop['Nazwa_przystanku_nr'],
            "type": stop['Rodzaj_przystanku']
        }
        
        # Check the geometry type and assign x, y accordingly
        if stop.geometry.geom_type == 'Point':
            x, y = stop.geometry.x, stop.geometry.y
        elif stop.geometry.geom_type in ['LineString', 'Polygon']:
            # For LineString or Polygon, use the centroid
            x, y = stop.geometry.centroid.x, stop.geometry.centroid.y
        else:
            print(f"Warning: Unsupported geometry type '{stop.geometry.geom_type}' for stop {stop_data['id']}. Skipping.")
            continue  # Skip this stop if the geometry type is unsupported

        nearest_node = ox.distance.nearest_nodes(G, x, y)
        stop_to_node[stop_data["id"]] = nearest_node

        G.nodes[nearest_node].setdefault('stops', []).append(stop_data)

    # Convert stops attribute from list of dictionaries to a JSON string for GraphML compatibility
    for n, data in G.nodes(data=True):
        if "stops" in data and isinstance(data["stops"], list):
            data["stops"] = json.dumps(data["stops"], ensure_ascii=False)

    print("Tram stops snapped and assigned to graph nodes.")

# ---------------------------
# 4. Remove railway_crossing nodes and reconnect edges
# ---------------------------
print("Identifying and processing railway_crossing nodes for removal and reconnection...")

nodes_to_remove = []
for node_id, data in G.nodes(data=True):
    if 'railway' in data and 'railway_crossing' in data['railway']:
        nodes_to_remove.append(node_id)
        data['is_railway_crossing'] = True
        data['is_railway_switch'] = False
    elif 'railway' in data and data['railway'] == 'switch':
        data['is_railway_switch'] = True
        data['is_railway_crossing'] = False
    else:
        data['is_railway_crossing'] = False
        data['is_railway_switch'] = False

print(f"Found {len(nodes_to_remove)} railway_crossing nodes identified for removal.")

for node_id in nodes_to_remove:
    if node_id not in G:
        continue

    in_edges = list(G.in_edges(node_id, data=True, keys=True))
    out_edges = list(G.out_edges(node_id, data=True, keys=True))
    connections_to_add = []

    for u, _, k_in, data_in in in_edges:
        for _, v, k_out, data_out in out_edges:
            osmid_in = data_in.get('osmid', [])
            osmid_out = data_out.get('osmid', [])

            if not isinstance(osmid_in, list):
                osmid_in = [osmid_in]
            if not isinstance(osmid_out, list):
                osmid_out = [osmid_out]

            if set(osmid_in) & set(osmid_out):
                combined_attrs = data_in.copy()
                if 'length' in data_out:
                    combined_attrs['length'] = combined_attrs.get('length', 0) + data_out['length']
                if 'geometry' in data_in and 'geometry' in data_out:
                    try:
                        if isinstance(data_in['geometry'], LineString) and isinstance(data_out['geometry'], LineString):
                            if data_in['geometry'].coords[-1] == data_out['geometry'].coords[0]:
                                combined_attrs['geometry'] = LineString(
                                    list(data_in['geometry'].coords) + list(data_out['geometry'].coords)[1:]
                                )
                            else:
                                print(f"Warning: Geometries for node {node_id} could not be precisely merged due to coordinate mismatch. Geometry attribute for new edge will be removed to avoid incorrect shapes.")
                                combined_attrs.pop('geometry', None)
                        else:
                            combined_attrs.pop('geometry', None)
                    except Exception as e:
                        print(f"Error merging geometries for node {node_id}: {e}. Geometry attribute removed.")
                        combined_attrs.pop('geometry', None)

                connections_to_add.append((u, v, combined_attrs))

    for u, v, attrs in connections_to_add:
        G.add_edge(u, v, **attrs)

    G.remove_node(node_id)
    print(f"Removed railway_crossing node {node_id} and reconnected its original ways.")

print("Finished processing railway_crossing nodes. Graph topology modified as requested.")

# Save the modified graph to GraphML format
output_graphml_file = "krakow_tram_graph.graphml"
nx.write_graphml(G, output_graphml_file)
print(f"Graph successfully saved to {output_graphml_file}. Railway_crossing nodes have been removed and ways reconnected.")