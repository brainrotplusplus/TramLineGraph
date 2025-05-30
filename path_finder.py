import json
import random
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

GRAPHML_PATH = "krakow_tram_graph.graphml"

def load_graph(graphml_path):
    """
    Load the GraphML file and process node attributes:
    - Convert x, y coordinates to floats.
    - Convert "stops" attribute from JSON string to list.
    """
    G = nx.read_graphml(graphml_path)

    for node, data in G.nodes(data=True):
        # Convert coordinate strings to float
        if "x" in data:
            try:
                data["x"] = float(data["x"])
            except Exception:
                pass
        if "y" in data:
            try:
                data["y"] = float(data["y"])
            except Exception:
                pass
        # Convert "stops" from JSON string to a Python list (if exists)
        if "stops" in data:
            try:
                data["stops"] = json.loads(data["stops"])
            except Exception:
                pass
    return G

def get_random_stop(G):
    """
    Select a random node that has at least one stop in the "stops" attribute,
    and then randomly select one of the stops from that node.
    Returns a tuple: (node_id, stop_name)
    """
    nodes_with_stops = [(node, data["stops"]) for node, data in G.nodes(data=True) if "stops" in data and data["stops"]]
    if not nodes_with_stops:
        return None, None

    node_id, stops_list = random.choice(nodes_with_stops)
    stop_name = random.choice(stops_list)
    return node_id, stop_name

def compute_random_route(G):
    start_node, start_stop = get_random_stop(G)
    end_node, end_stop = get_random_stop(G)
    
    while end_node == start_node:
        end_node, end_stop = get_random_stop(G)
    
    print(f"Randomly selected start stop: {start_stop} (node: {start_node})")
    print(f"Randomly selected end stop: {end_stop} (node: {end_node})")
    
    try:
        route = nx.shortest_path(G, source=start_node, target=end_node, weight="length")
        print("Shortest path (node ids):", route)
    except nx.NetworkXNoPath:
        print("No route found between the selected stops!")
        route = None
    return route

def plot_graph_ax(ax, G, route=None):
    """
    Plot the tram network graph on the given axis.
    Draw nodes, edges and, if a route is provided, highlight it.
    Additionally, stop nodes are plotted in green and annotates stop names.
    """
    pos = {}
    for node, data in G.nodes(data=True):
        if "x" in data and "y" in data:
            pos[node] = (data["x"], data["y"])

    ax.clear()

    # Plot all nodes in blue.
    all_x = [coord[0] for coord in pos.values()]
    all_y = [coord[1] for coord in pos.values()]
    ax.scatter(all_x, all_y, s=10, c='blue', alpha=0.6)

    # Plot all edges.
    for u, v in G.edges():
        if u in pos and v in pos:
            x_vals = [pos[u][0], pos[v][0]]
            y_vals = [pos[u][1], pos[v][1]]
            ax.plot(x_vals, y_vals, color='gray', alpha=0.5)

    # Highlight the route if provided.
    if route is not None and len(route) > 0:
        route_x = [pos[node][0] for node in route if node in pos]
        route_y = [pos[node][1] for node in route if node in pos]
        ax.scatter(route_x, route_y, s=30, c='red')
        for i in range(len(route) - 1):
            u = route[i]
            v = route[i + 1]
            if u in pos and v in pos:
                x_vals = [pos[u][0], pos[v][0]]
                y_vals = [pos[u][1], pos[v][1]]
                ax.plot(x_vals, y_vals, color='red', linewidth=2)

    # Optionally annotate nodes with stops info from JSON.
    for node, data in G.nodes(data=True):
        if "stops" in data and data["stops"]:
            # Plot a bigger green dot at the node if stops exist.
            if node in pos:
                ax.scatter(pos[node][0], pos[node][1], s=40, c='green', zorder=4)
                
            if isinstance(data["stops"], list):
                stops = data["stops"]
            else:
                try:
                    stops = json.loads(data["stops"])
                except json.JSONDecodeError:
                    print(f"Node {node}: invalid JSON in stops.")
                    continue
            # Annotate each stop's name near the node.
            if node in pos:
                for i, stop in enumerate(stops):
                    stop_name = f"{stop.get("name", "")} ({stop.get("id", "unknown")})"
                    ax.annotate(stop_name,
                                (pos[node][0], pos[node][1]),
                                fontsize=8,
                                color='darkgreen')

    ax.set_title("Tram Network with Highlighted Route")
    ax.axis("off")

def main():
    G = load_graph(GRAPHML_PATH)
    print("Graph loaded successfully.")
    
    # Create the initial figure and axis for the graph plot.
    fig, ax = plt.subplots(figsize=(12, 12))
    plt.subplots_adjust(bottom=0.2)
    
    # Compute and plot the initial random route.
    route = compute_random_route(G)
    plot_graph_ax(ax, G, route)
    
    # Add a button for generating a new random route.
    button_ax = plt.axes([0.4, 0.05, 0.2, 0.075])
    button = Button(button_ax, 'New Route')
    
    def update_route(event):
        new_route = compute_random_route(G)
        plot_graph_ax(ax, G, new_route)
        plt.draw()
    
    button.on_clicked(update_route)
    plt.show()

if __name__ == '__main__':
    main()