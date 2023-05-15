import math
import json
import psycopg2.pool


pool = psycopg2.pool.SimpleConnectionPool(
    host="localhost",
    port="5432",
    database="kathmandu_db",
    user="postgres",
    password="password",
    minconn=1,
    maxconn=10,
)


class LatLan:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude


def a_star_db(start: LatLan, end: LatLan):
    client = pool.getconn()
    query_str = f"""
        SELECT ST_AsGeoJSON(ST_Union((the_geom))) FROM ways WHERE gid in
        (SELECT edge FROM pgr_astar(
            'SELECT gid as id,
            source,
            target,
            length AS cost,
            x1, y1, x2, y2
            FROM ways',
            (SELECT id FROM ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_Point({start.longitude}, {start.latitude}), 4326) LIMIT 1), 
            (SELECT id FROM ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_Point({end.longitude}, {end.latitude}), 4326) LIMIT 1),
            directed := false) foo);
        """
    cursor = client.cursor()
    cursor.execute(query_str)
    res = cursor.fetchone()
    result = res[0]
    client.commit()
    pool.putconn(client)
    return json.loads(result)


