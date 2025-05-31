import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import json
import random
import geopandas as gpd # Although not directly used for plotting the graph, it's good to keep it if needed later
from shapely.geometry import LineString # Same as above

# ---------------------------
# 1. Load the tram network graph
# ---------------------------
output_graphml_file = "krakow_tram_graph.graphml"
print(f"Loading graph from {output_graphml_file}...")
G = nx.read_graphml(output_graphml_file)
print("Graph loaded successfully.")

# ---------------------------
# 2. Find terminus nodes (pętla)
# ---------------------------
def find_terminus_nodes(graph):
    """
    Finds nodes in the graph that are associated with tram stops
    of type 'pętla' (terminus).
    """
    terminus_nodes = []
    for node_id, data in graph.nodes(data=True):
        if 'stops' in data:
            try:
                # 'stops' attribute was stored as a JSON string, so decode it
                stops_data = json.loads(data['stops'])
                for stop in stops_data:
                    if stop.get('type') == 'pętla':
                        terminus_nodes.append(node_id)
                        break # Found a 'pętla' stop at this node, no need to check other stops on this node
            except json.JSONDecodeError:
                # Handle cases where JSON might be malformed for a node's 'stops' data
                pass
    return list(set(terminus_nodes)) # Return unique node IDs

# Get all terminus nodes in the graph
terminus_nodes = find_terminus_nodes(G)
print(f"Found {len(terminus_nodes)} terminus nodes ('pętla').")

if not terminus_nodes:
    print("No terminus nodes ('pętla') found in the graph. Cannot generate and display routes based on them.")
else:
    # ---------------------------
    # 3. Plot the base tram network
    # ---------------------------
    print("\nPlotting the base tram network...")
    # Initialize the plot with the entire tram graph
    # show=False, close=False prevents the plot from immediately displaying/closing
    # so we can add more elements to it.
    fig, ax = ox.plot_graph(G, show=False, close=False,
                            bgcolor='w', edge_color='lightgray', node_color='gray',
                            node_size=5, edge_linewidth=0.5,
                            filepath=None, save=False, dpi=300)

    # ---------------------------
    # 4. Highlight terminus nodes on the plot
    # ---------------------------
    # Get coordinates of terminus nodes to plot them
    terminus_nodes_coords = {node: (G.nodes[node]['x'], G.nodes[node]['y']) for node in terminus_nodes}
    ax.scatter([v[0] for v in terminus_nodes_coords.values()],
               [v[1] for v in terminus_nodes_coords.values()],
               color='red', s=50, zorder=3, label='Terminus (Pętla)') # zorder ensures they appear on top

    # ---------------------------
    # 5. Generate and plot example tram routes
    # ---------------------------
    num_routes_to_generate = 3 # Generate a few routes for clarity on the map
    # Define distinct colors for each route
    colors = ['blue', 'green', 'purple', 'orange', 'cyan', 'magenta', 'lime']
    route_labels = [] # To store labels for the legend

    print(f"\nGenerating {num_routes_to_generate} example tram routes and plotting them:")

    for i in range(num_routes_to_generate):
        if len(terminus_nodes) < 2:
            print("Not enough terminus nodes to generate multiple routes. Skipping route generation.")
            break

        # Randomly pick two distinct terminus nodes for the start and end of the route
        start_node, end_node = random.sample(terminus_nodes, 2)

        # Get readable names for the start and end 'pętla' stops
        start_stop_name = "Unknown Pętla"
        end_stop_name = "Unknown Pętla"
        if 'stops' in G.nodes[start_node]:
            try:
                start_stops_data = json.loads(G.nodes[start_node]['stops'])
                for stop in start_stops_data:
                    if stop.get('type') == 'pętla':
                        start_stop_name = stop.get('name', start_stop_name)
                        break
            except json.JSONDecodeError: pass
        if 'stops' in G.nodes[end_node]:
            try:
                end_stops_data = json.loads(G.nodes[end_node]['stops'])
                for stop in end_stops_data:
                    if stop.get('type') == 'pętla':
                        end_stop_name = stop.get('name', end_stop_name)
                        break
            except json.JSONDecodeError: pass

        print(f"\n--- Example Route {i+1} ---")
        print(f"  Starting from Pętla: '{start_stop_name}' (Node ID: {start_node})")
        print(f"  Ending at Pętla: '{end_stop_name}' (Node ID: {end_node})")

        try:
            # Find the shortest path (list of nodes) between the two terminus nodes
            # 'weight='length'' ensures the path minimizes the total length of the tram tracks
            route_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
            route_length = nx.shortest_path_length(G, source=start_node, target=end_node, weight='length')

            print(f"  Route found with {len(route_nodes)} nodes and total length: {route_length:.2f} meters.")

            # Overlay this specific route onto the existing plot
            # ox.plot_graph_route handles drawing the path as a thicker, colored line
            ox.plot_graph_route(G, route_nodes, route_color=colors[i % len(colors)],
                                route_linewidth=3, route_alpha=0.7,
                                ax=ax, fig=fig, show=False, close=False)

            # Store label for the legend
            route_labels.append((colors[i % len(colors)], f"Route {i+1}: {start_stop_name} -> {end_stop_name}"))

        except nx.NetworkXNoPath:
            print(f"  No path found between {start_stop_name} and {end_stop_name}. Skipping plot for this route.")
        except Exception as e:
            print(f"  An error occurred while finding route: {e}. Skipping plot for this route.")

    # ---------------------------
    # 6. Final plot adjustments and display
    # ---------------------------
    # Create proxy artists for the custom legend entries
    legend_handles = []
    # Add handle for terminus nodes (red dots)
    legend_handles.append(plt.Line2D([0], [0], marker='o', color='red', linestyle='', ms=8, label='Terminus (Pętla)'))
    # Add handles for each generated route
    for color, label in route_labels:
        legend_handles.append(plt.Line2D([0], [0], color=color, lw=3, label=label))

    # Add the legend to the plot, positioned outside to avoid overlapping the map
    ax.legend(handles=legend_handles, loc='upper right', bbox_to_anchor=(1.05, 1), borderaxespad=0.)

    # Adjust layout to make space for the legend, ensuring it doesn't cut off the plot
    plt.tight_layout(rect=[0, 0, 0.95, 1]) # Adjust right boundary to make space for legend

    plt.title('Kraków Tram Network with Example Routes')
    plt.show()
    print("\nPlot displayed successfully.")