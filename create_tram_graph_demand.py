import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString
import os
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import random

# Load tram network
place_name = "Kraków, Poland"
custom_filter = '["railway"~"tram"]'
print(f"Loading tram graph for {place_name}...")
tram_graph = ox.graph_from_place(place_name, simplify=False, custom_filter=custom_filter)
nodes_gdf, edges_gdf = ox.graph_to_gdfs(tram_graph, nodes=True, edges=True)
print(f"Graph has {len(nodes_gdf)} nodes and {len(edges_gdf)} edges.")

# Load tram stops
hour = str(input("Hour: "))
geojson_tram_stops = f"stop_demand_time/stops_demand_hour_{hour}.geojson"
stops_gdf = gpd.read_file(geojson_tram_stops).to_crs(nodes_gdf.crs) if os.path.exists(geojson_tram_stops) else None

def snap_stops_to_graph(G, stops_gdf):
    """Snap stops to nearest nodes and assign demand data"""
    if stops_gdf is None:
        return G
    
    for idx, stop in stops_gdf.iterrows():
        stop_data = {
            "id": stop['OBJECTID'],
            "name": stop['Nazwa_przystanku_nr'],
            "demand": stop['demand'],
            "type": stop['Rodzaj_przystanku']
        }
        
        if stop.geometry.geom_type == 'Point':
            x, y = stop.geometry.x, stop.geometry.y
        else:
            x, y = stop.geometry.centroid.x, stop.geometry.centroid.y
            
        nearest_node = ox.distance.nearest_nodes(G, x, y)
        G.nodes[nearest_node].setdefault('stops', []).append(stop_data)
        G.nodes[nearest_node]['total_demand'] = sum(s['demand'] for s in G.nodes[nearest_node]['stops'])
        
        # Mark nodes with pętla stops
        if stop['Rodzaj_przystanku'] == 'pętla':
            G.nodes[nearest_node]['has_petla'] = True
    
    return G

def remove_railway_crossings(G):
    """Remove railway crossing nodes and reconnect edges"""
    nodes_to_remove = [n for n, d in G.nodes(data=True) 
                      if 'railway' in d and 'railway_crossing' in str(d['railway'])]
    
    for node_id in nodes_to_remove:
        if node_id not in G:
            continue
            
        in_edges = list(G.in_edges(node_id, data=True, keys=True))
        out_edges = list(G.out_edges(node_id, data=True, keys=True))
        
        for u, _, k_in, data_in in in_edges:
            for _, v, k_out, data_out in out_edges:
                # Handle osmid as either int or list
                osmid_in = data_in.get('osmid', [])
                osmid_out = data_out.get('osmid', [])
                
                if not isinstance(osmid_in, list):
                    osmid_in = [osmid_in]
                if not isinstance(osmid_out, list):
                    osmid_out = [osmid_out]
                
                if set(osmid_in) & set(osmid_out):
                    combined_attrs = data_in.copy()
                    combined_attrs['length'] = combined_attrs.get('length', 0) + data_out.get('length', 0)
                    G.add_edge(u, v, **combined_attrs)
        
        G.remove_node(node_id)
    
    print(f"Removed {len(nodes_to_remove)} railway crossing nodes.")
    return G

def find_petla_stops(G):
    """Find pętla stops - nodes with stops that have 'Rodzaj_przystanku': 'pętla'"""
    petla_nodes = []
    for node_id, data in G.nodes(data=True):
        if 'stops' in data:
            for stop in data['stops']:
                if stop.get('type') == 'pętla':
                    petla_nodes.append(node_id)
                    break
    
    print(f"Found {len(petla_nodes)} pętla stops for line generation")
    return petla_nodes

def get_edge_length(G, u, v):
    """Get the length of an edge between two nodes, handling multigraph case"""
    if not G.has_edge(u, v):
        return 0
    
    edge_data = G.get_edge_data(u, v)
    
    # If it's a single edge, edge_data contains the attributes directly
    if 'length' in edge_data:
        return edge_data['length']
    
    # If it's multiple edges, edge_data is a dict of dicts keyed by edge key
    # Take the first edge's length (they should be similar for the same road segment)
    if isinstance(edge_data, dict):
        for key, data in edge_data.items():
            if 'length' in data:
                return data['length']
    
    return 0

def generate_tram_lines(G, num_lines=5):
    """Generate multiple tram lines as loops from pętla stops"""
    petla_nodes = find_petla_stops(G)
    if len(petla_nodes) < 1:
        print("No pętla stops found for line generation")
        return []
    
    tram_lines = []
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
    
    for i in range(min(num_lines, len(petla_nodes))):
        start_petla = petla_nodes[i]
        
        # Get pętla stop name
        petla_stop_name = "Unknown Pętla"
        if 'stops' in G.nodes[start_petla]:
            for stop in G.nodes[start_petla]['stops']:
                if stop.get('type') == 'pętla':
                    petla_stop_name = stop['name']
                    break
        
        # Find intermediate high-demand stops for the loop (excluding other pętla stops)
        high_demand_nodes = [(n, d.get('total_demand', 0)) for n, d in G.nodes(data=True) 
                           if (d.get('total_demand', 0) > 0 and n != start_petla and 
                               n not in petla_nodes)]  # Exclude other pętla stops from route
        high_demand_nodes.sort(key=lambda x: x[1], reverse=True)
        
        # Create loop route through top demand stops
        route_nodes = [start_petla]
        current_node = start_petla
        visited = {start_petla}
        
        # Add 3-5 intermediate stops
        targets = [n for n, _ in high_demand_nodes[:8] if n not in visited]
        random.shuffle(targets)
        
        for target in targets[:random.randint(3, 5)]:
            if nx.has_path(G, current_node, target):
                try:
                    path = nx.shortest_path(G, current_node, target, weight='length')
                    route_nodes.extend(path[1:])  # Skip first node to avoid duplication
                    current_node = target
                    visited.update(path)
                except:
                    continue
        
        # Return to starting pętla to complete the loop
        if current_node != start_petla and nx.has_path(G, current_node, start_petla):
            try:
                return_path = nx.shortest_path(G, current_node, start_petla, weight='length')
                route_nodes.extend(return_path[1:])
            except:
                pass
        
        if len(route_nodes) > 3:  # Valid line
            # Calculate line statistics using the fixed edge length function
            total_demand = sum(G.nodes[n].get('total_demand', 0) for n in route_nodes)
            total_length = sum(get_edge_length(G, route_nodes[j], route_nodes[j+1]) 
                             for j in range(len(route_nodes)-1))
            
            line_info = {
                'line_number': i + 1,
                'route': route_nodes,
                'color': colors[i % len(colors)],
                'start_stop': petla_stop_name,
                'total_demand': total_demand,
                'length_km': total_length / 1000,
                'num_stops': len([n for n in route_nodes if G.nodes[n].get('total_demand', 0) > 0])
            }
            tram_lines.append(line_info)
            print(f"Line {i+1}: {petla_stop_name} Loop - {line_info['length_km']:.1f}km, {line_info['num_stops']} stops, demand: {total_demand:.0f}")
    
    return tram_lines

def visualize_all_tram_lines(G, tram_lines, stops_gdf=None):
    """Visualize all tram lines on one map"""
    fig, ax = plt.subplots(1, 1, figsize=(20, 16))
    
    # Plot base network
    ox.plot_graph(G, ax=ax, show=False, close=False,
                  node_color='lightgray', node_size=15, node_alpha=0.4,
                  edge_color='lightgray', edge_linewidth=0.5, edge_alpha=0.4)
    
    # Plot demand-based stops with labels
    max_demand = max((d.get('total_demand', 0) for _, d in G.nodes(data=True)), default=1)
    labeled_stops = set()  # Keep track of labeled stops to avoid duplicates
    
    for node_id, data in G.nodes(data=True):
        if data.get('total_demand', 0) > 0:
            x, y = data['x'], data['y']
            demand = data['total_demand']
            intensity = demand / max_demand
            size = 20 + (intensity * 80)
            ax.scatter(x, y, c=plt.cm.YlOrRd(intensity), s=size, alpha=0.7, 
                      edgecolors='black', linewidth=0.3, zorder=3)
            
            # Add stop names for high-demand stops
            if 'stops' in data and demand > max_demand * 0.3:  # Only label high-demand stops
                stop_names = []
                for stop in data['stops']:
                    stop_name = stop.get('name', 'Unknown')
                    if stop_name not in stop_names:
                        stop_names.append(stop_name)
                
                if stop_names and node_id not in labeled_stops:
                    # Use the first (or main) stop name, truncate if too long
                    main_name = stop_names[0][:25] + ('...' if len(stop_names[0]) > 25 else '')
                    ax.annotate(main_name, (x, y), xytext=(5, 5), 
                               textcoords='offset points', fontsize=8,
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8),
                               zorder=5)
                    labeled_stops.add(node_id)
    
    # Plot tram lines
    legend_elements = []
    for line in tram_lines:
        route = line['route']
        color = line['color']
        
        # Plot line edges
        for i in range(len(route) - 1):
            if G.has_edge(route[i], route[i + 1]):
                x1, y1 = G.nodes[route[i]]['x'], G.nodes[route[i]]['y']
                x2, y2 = G.nodes[route[i + 1]]['x'], G.nodes[route[i + 1]]['y']
                ax.plot([x1, x2], [y1, y2], color=color, linewidth=3, alpha=0.8, zorder=4)
        
        # Mark start/end pętla with name labels
        start_node = route[0]
        x, y = G.nodes[start_node]['x'], G.nodes[start_node]['y']
        ax.scatter(x, y, c=color, s=150, marker='D', edgecolors='black', 
                  linewidth=2, zorder=6, alpha=0.9)
        
        # Add pętla name label
        ax.annotate(f"P{line['line_number']}: {line['start_stop'][:20]}", 
                   (x, y), xytext=(10, -10), textcoords='offset points', 
                   fontsize=9, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.8, edgecolor='black'),
                   color='white', zorder=7)
        
        legend_elements.append(mpatches.Patch(color=color, 
                             label=f"Line {line['line_number']}: {line['start_stop'][:20]}... ({line['length_km']:.1f}km)"))
    
    # Add legend
    ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0.02, 0.98), fontsize=10)
    
    ax.set_title('Kraków Tram Network - Multiple Loop Lines', fontsize=16, fontweight='bold')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    
    plt.tight_layout()
    return fig, ax

# Main execution
print("Processing tram network...")
G = tram_graph.copy()
G = snap_stops_to_graph(G, stops_gdf)
G = remove_railway_crossings(G)

print("\nGenerating tram lines...")
tram_lines = generate_tram_lines(G, num_lines=6)

if tram_lines:
    print(f"\nSuccessfully generated {len(tram_lines)} tram lines!")
    
    # Create visualization
    fig, ax = visualize_all_tram_lines(G, tram_lines, stops_gdf)
    plt.savefig('tram_lines_loops.png', dpi=300, bbox_inches='tight')
    print("Visualization saved as 'tram_lines_loops.png'")
    plt.show()
    
    # Save line data
    lines_data = [{k: v for k, v in line.items() if k != 'route'} for line in tram_lines]
    with open('tram_lines_summary.json', 'w', encoding='utf-8') as f:
        json.dump(lines_data, f, ensure_ascii=False, indent=2)
    print("Line data saved to 'tram_lines_summary.json'")
    
else:
    print("Failed to generate tram lines. Check network connectivity and pętla stops.")

print("Process complete!")