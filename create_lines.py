import networkx as nx
import json
import random

# Load the tram graph from the GraphML file
output_graphml_file = "krakow_tram_graph.graphml"
print(f"Loading graph from {output_graphml_file}...")
G = nx.read_graphml(output_graphml_file)
print("Graph loaded successfully.")

# Function to find nodes that are tram termini (pętla)
def find_terminus_nodes(graph):
    terminus_nodes = []
    for node_id, data in graph.nodes(data=True):
        if 'stops' in data:
            try:
                # 'stops' attribute was stored as a JSON string
                stops_data = json.loads(data['stops'])
                for stop in stops_data:
                    if stop.get('type') == 'pętla':
                        terminus_nodes.append(node_id)
                        break # Found a 'pętla' stop at this node, no need to check other stops on this node
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON for node {node_id}'s 'stops' attribute: {data['stops']}")
    return list(set(terminus_nodes)) # Use set to get unique nodes

# Find all terminus nodes
terminus_nodes = find_terminus_nodes(G)
print(f"Found {len(terminus_nodes)} terminus nodes (pętla).")

if not terminus_nodes:
    print("No terminus nodes (pętla) found in the graph. Cannot generate routes based on them.")
else:
    # Generate a few example tram routes between random terminus nodes
    num_routes_to_generate = 5
    print(f"\nGenerating {num_routes_to_generate} example tram routes:")

    for i in range(num_routes_to_generate):
        if len(terminus_nodes) < 2:
            print("Not enough terminus nodes to generate multiple routes.")
            break

        # Pick two distinct random terminus nodes
        start_node, end_node = random.sample(terminus_nodes, 2)

        # Get stop names for the start and end nodes if available
        start_stop_name = "Unknown"
        end_stop_name = "Unknown"
        if 'stops' in G.nodes[start_node]:
            try:
                start_stops_data = json.loads(G.nodes[start_node]['stops'])
                for stop in start_stops_data:
                    if stop.get('type') == 'pętla':
                        start_stop_name = stop.get('name', 'Unknown Pętla')
                        break
            except json.JSONDecodeError:
                pass
        if 'stops' in G.nodes[end_node]:
            try:
                end_stops_data = json.loads(G.nodes[end_node]['stops'])
                for stop in end_stops_data:
                    if stop.get('type') == 'pętla':
                        end_stop_name = stop.get('name', 'Unknown Pętla')
                        break
            except json.JSONDecodeError:
                pass

        print(f"\n--- Example Route {i+1} ---")
        print(f"  Starting from Pętla: '{start_stop_name}' (Node ID: {start_node})")
        print(f"  Ending at Pętla: '{end_stop_name}' (Node ID: {end_node})")

        try:
            # Find the shortest path between the two terminus nodes
            # We assume 'length' is a reliable weight for tram lines
            route_nodes = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
            route_length = nx.shortest_path_length(G, source=start_node, target=end_node, weight='length')

            print(f"  Route found with {len(route_nodes)} nodes and total length: {route_length:.2f} meters")
            
            # To show actual stops along the route, iterate through the route nodes
            # and check for 'stops' attribute
            stops_on_route = []
            for node in route_nodes:
                if 'stops' in G.nodes[node]:
                    try:
                        node_stops_data = json.loads(G.nodes[node]['stops'])
                        for stop in node_stops_data:
                            # You can refine this to only include specific types of stops if needed
                            stops_on_route.append(stop.get('name', f"Stop at node {node}"))
                    except json.JSONDecodeError:
                        pass # Handle cases where JSON might be malformed

            if stops_on_route:
                print(f"  Key stops along this route: {', '.join(list(set(stops_on_route)))}") # Use set to avoid duplicates
            else:
                print("  No named stops found directly on the nodes of this route (they might be on edges, or missing 'stops' attribute).")

        except nx.NetworkXNoPath:
            print(f"  No path found between {start_stop_name} and {end_stop_name}.")
        except Exception as e:
            print(f"  An error occurred while finding route: {e}")