import psycopg2
from itertools import count
import networkx as nx
import math
from heapq import heappop, heappush
from networkx.algorithms.shortest_paths.weighted import _weight_function

class LatLan:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude
# Connect to database
conn = psycopg2.connect(database="kathmandu_db", 
                        user="postgres", 
                        password="password", 
                        host="localhost"
                        )

def garbageASTAR(start:LatLan, end:LatLan):
        
        start_lat = start.latitude
        start_lon = start.longitude
        end_lat = end.latitude
        end_lon = end.longitude

        # Find nearest nodes to start and end locations
        cur = conn.cursor()
        cur.execute("SELECT id FROM ways_vertices_pgr ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326) LIMIT 1;", (start_lon, start_lat))
        start_node = cur.fetchone()[0]
        cur.execute("SELECT id FROM ways_vertices_pgr ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326) LIMIT 1;", (end_lon, end_lat))
        end_node = cur.fetchone()[0]

        # Create empty graph
        G = nx.Graph()

        # Add nodes from ways_vertices_pgr table
        cur.execute("SELECT id, ST_Y(the_geom) AS lat, ST_X(the_geom) AS lon FROM ways_vertices_pgr;")
        for row in cur.fetchall():
            G.add_node(row[0], y=row[1], x=row[2])

        # Add edges from ways table
        cur.execute("SELECT source, target, length FROM ways;")
        for row in cur.fetchall():
            G.add_edge(row[0], row[1], length=row[2])

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Radius of the earth in km
            dLat = math.radians(lat2 - lat1)
            dLon = math.radians(lon2 - lon1)
            a = math.sin(dLat / 2) * math.sin(dLat / 2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) * math.sin(dLon / 2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            d = R * c  # Distance in km
            return d
            
        
        def heuristic(node1, node2):
            lat1, lon1 = G.nodes[node1]['y'], G.nodes[node1]['x']
            lat2, lon2 = G.nodes[node2]['y'], G.nodes[node2]['x']
            return haversine(lat1, lon1,lat2, lon2)
        
        def astar_path(G, source, target, weight):
        
            if source not in G or target not in G:
                msg = f"Either source {source} or target {target} is not in G"
                raise nx.NodeNotFound(msg)

            push = heappush
            pop = heappop
            weight = _weight_function(G, weight)

            c = count()
            queue = [(0, next(c), source, 0, None)]

            enqueued = {}
            # Maps explored nodes to parent closest to the source.
            explored = {}
            cur.execute("TRUNCATE algorithm_trace;")
            cur.execute("ALTER SEQUENCE algorithm_trace_id_seq RESTART WITH 1;")
            while queue:
                # Pop the smallest item from queue.
                _, __, curnode, dist, parent = pop(queue)

                if curnode == target:
                    path = [curnode]
                    node = parent
                    while node is not None:
                        path.append(node)
                        node = explored[node]
                    path.reverse()
                    return path

                if curnode in explored:
                    # Do not override the parent of starting node
                    if explored[curnode] is None:
                        continue

                    # Skip bad paths that were enqueued before finding a better one
                    qcost, h = enqueued[curnode]
                    if qcost < dist:
                        continue
                            
                explored[curnode] = parent
                
                for neighbor, w in G[curnode].items():
                    
                    cost = weight(curnode, neighbor, w)
                    
                    if cost is None:
                        continue
                    ncost = dist + cost
                    if neighbor in enqueued:
                        qcost, h = enqueued[neighbor]
                        if qcost <= ncost:
                            continue
                    else:
                        h = heuristic(neighbor, target)
                    enqueued[neighbor] = ncost, h
                    print("G(n)=",dist)
                    print("Current Node",explored[curnode])
                    print("Neighbor Node",neighbor)
                    print("Heuristic value for current node to goal node=",h)
                    
                    cur.execute("INSERT INTO algorithm_trace(current_node,neighbor_node,g_n,heuristic_value) values(%s,%s,%s,%s);",(0 if explored[curnode] is None else explored[curnode],neighbor,dist,h))
                    conn.commit()
                    push(queue, (ncost + h, next(c), neighbor, ncost, curnode))

            raise nx.NetworkXNoPath(f"Node {target} not reachable from {source}")

        
        path = astar_path(G, start_node, end_node,weight="length")
        
        coordinates = []
        for node in path:
            cur.execute("SELECT ST_Y(the_geom), ST_X(the_geom) FROM ways_vertices_pgr WHERE id=%s;", (node,))
            lat, lon = cur.fetchone()
            coordinates.append((lon, lat))

        # Print coordinates
        data = {
                
                'type':'LineString',
                 'coordinates':coordinates
            }

        # Print JSON body
        return data
        

        