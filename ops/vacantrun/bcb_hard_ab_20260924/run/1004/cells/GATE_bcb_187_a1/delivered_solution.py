import numpy as np
import geopandas as gpd
from shapely.geometry import Point

def task_func(dic={'Lon': (-180, 180), 'Lat': (-90, 90)}, cities=['New York', 'London', 'Beijing', 'Tokyo', 'Sydney']):
    if 'Lon' not in dic or 'Lat' not in dic:
        raise ValueError("Missing 'Lon' or 'Lat' keys")
    
    if not isinstance(dic['Lon'], tuple) or not isinstance(dic['Lat'], tuple):
        raise ValueError("'Lon' and 'Lat' values must be tuples")

    data = []
    for city in cities:
        lon = np.random.uniform(dic['Lon'][0], dic['Lon'][1])
        lat = np.random.uniform(dic['Lat'][0], dic['Lat'][1])
        data.append({
            'City': city,
            'Coordinates': Point(lon, lat)
        })

    gdf = gpd.GeoDataFrame(data, geometry='Coordinates')
    return gdf
