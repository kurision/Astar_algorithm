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

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Radius of the earth in km
            dLat = math.radians(lat2 - lat1)
            dLon = math.radians(lon2 - lon1)
            a = math.sin(dLat / 2) * math.sin(dLat / 2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) * math.sin(dLon / 2)
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            d = R * c  # Distance in km
            return d
        # Find nearest nodes to start and end locations
        cur = conn.cursor()
        cur.execute("SELECT id FROM ways_vertices_pgr ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326) LIMIT 1;", (start_lon, start_lat))
        start_node = cur.fetchone()[0]
        cur.execute("SELECT id FROM ways_vertices_pgr ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326) LIMIT 1;", (end_lon, end_lat))
        end_node = cur.fetchone()[0]

        cur.execute("SELECT ST_Y(the_geom), ST_X(the_geom) FROM ways_vertices_pgr WHERE id=%s;", (end_node,))
        lat, lon = cur.fetchone()

        disttest=haversine(end_lat,end_lon,lat,lon)
        if(disttest>10):
            error="Target not reachable from source: Reason being the target is not in graph"
            print(error)
            data = {
                    
                    'type':'LineString',
                    'coordinates':error
            }
            # Print JSON body
            return data

        # Create empty graph
        G = nx.Graph()

        # Add nodes from ways_vertices_pgr table
        cur.execute("SELECT id, ST_Y(the_geom) AS lat, ST_X(the_geom) AS lon FROM ways_vertices_pgr;")
        for row in cur.fetchall():
            G.add_node(row[0], y=row[1], x=row[2])

        # Add edges from ways table
        cur.execute("SELECT source, target, length_m FROM ways;")
        for row in cur.fetchall():
            G.add_edge(row[0], row[1], length=row[2]/1000)

        
            
        
        def heuristic(node1, node2):
            lat1, lon1 = G.nodes[node1]['y'], G.nodes[node1]['x']
            lat2, lon2 = G.nodes[node2]['y'], G.nodes[node2]['x']
            return haversine(lat1, lon1,lat2, lon2)
        
        def astar_path(G, source, target, weight):
        

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
                    print();
                    cur.execute("SELECT ST_Y(the_geom), ST_X(the_geom) FROM ways_vertices_pgr WHERE id=%s;", (curnode,))
                    latNode, lonNode = cur.fetchone()
                    print("Current Node",explored[curnode]," (", latNode,",",lonNode,")")
                    cur.execute("SELECT ST_Y(the_geom), ST_X(the_geom) FROM ways_vertices_pgr WHERE id=%s;", (neighbor,))
                    latNode, lonNode = cur.fetchone()
                    print("Neighbor Node",neighbor," (", latNode,",",lonNode,")")
                    print("G(n)=",ncost)
                    print("H(n)=",h)
                    print("F(n): ",ncost+h)
                    cur.execute("INSERT INTO algorithm_trace(current_node,neighbor_node,g_n,heuristic_value,f_n) values(%s,%s,%s,%s,%s);",(0 if explored[curnode] is None else explored[curnode],neighbor,ncost,h,ncost+h))
                    conn.commit()
                    push(queue, (ncost + h, next(c), neighbor, ncost, curnode))
                    if neighbor == target:
                        path = [neighbor]
                        node = parent
                        while node is not None:
                            path.append(node)
                            node = explored[node]
                        path.reverse()
                        return path
            eror=f"Node {target} not reachable from {source}"
            return eror

        
        path = astar_path(G, start_node, end_node,weight="length")
        print(start_node,end_node)
        print(path)
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
        

        