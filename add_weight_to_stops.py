import os
import json
import geopandas as gpd
from shapely.geometry import Point

# Ścieżka do pliku GeoJSON z przystankami
geojson_file = "Przystanki_Komunikacji_Miejskiej_w_Krakowie_6ab29dbb62854448803c0125c291aca3.geojson"

# Wczytanie przystanków do GeoDataFrame
stops_gdf = gpd.read_file(geojson_file)

# Upewnij się, że geometrie są punktami
stops_gdf['geometry'] = stops_gdf['geometry'].apply(
    lambda geom: geom if geom.geom_type == 'Point' else geom.centroid
)

# Dodaj kolumnę do sumaryzacji demand
stops_gdf['demand'] = 0.0

# Ustal docelowy CRS (np. Web Mercator)
proj_crs = "EPSG:3857"

# Przelicz przystanki do CRS docelowego
stops_gdf_proj = stops_gdf.to_crs(proj_crs)

# Katalog z plikami hexbin oraz katalog na wyjściowe pliki z demand
hexbin_dir = "poi_demand_time"
output_dir = "stop_demand_time"
os.makedirs(output_dir, exist_ok=True)

# Iteruj przez pliki hexbin_hour_00.json do hexbin_hour_23.json
for hour in range(24):
    filename = os.path.join(hexbin_dir, f"hexbin_hour_{hour:02d}.json")
    if not os.path.exists(filename):
        print(f"Plik {filename} nie istnieje, pomijam godzinę {hour:02d}.")
        continue
    with open(filename, 'r', encoding='utf-8') as f:
        hex_data = json.load(f)
    # Dla każdego hexbina znajdź najbliższy przystanek i dodaj demand
    for cell in hex_data:
        lon = cell.get("longitude")
        lat = cell.get("latitude")
        demand = cell.get("demand", 0)
        if lon is None or lat is None:
            continue
        # Utwórz punkt w CRS oryginalnym i przelicz do CRS docelowego
        cell_point = Point(lon, lat)
        cell_point_proj = gpd.GeoSeries([cell_point], crs=stops_gdf.crs).to_crs(proj_crs).iloc[0]
        distances = stops_gdf_proj.geometry.distance(cell_point_proj)
        if distances.empty:
            continue
        nearest_index = distances.idxmin()
        # Dodaj demand do najbliższego przystanku
        stops_gdf.at[nearest_index, 'demand'] += demand
    # Zapisz GeoJSON z aktualnym stanem demand do osobnego pliku
    output_filename = os.path.join(output_dir, f"stops_demand_hour_{hour:02d}.geojson")
    stops_gdf.to_file(output_filename, driver="GeoJSON")
    print(f"Zapisano plik: {output_filename}")