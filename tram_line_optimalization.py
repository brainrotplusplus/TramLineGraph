import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, Polygon
import numpy as np

# Wczytaj dane z pliku Excel
# Kolumny: ID heksagonu, Aktualność danych, Liczba osób zameldowanych na stałe, 
# Liczba osób zameldowanych czasowo, Współrzędna X (układ PL-2000), Współrzędna Y (układ PL-2000)
df = pd.read_excel("ludnosc_dane.xlsx")

# Oblicz łączną liczbę mieszkańców
df["Liczba mieszkańców"] = df["Liczba osób zameldowanych na stałe"] + df["Liczba osób zameldowanych czasowo"]

# Utwórz GeoDataFrame z punktami (środki, np. adresowane miejsca zamieszkania)
gdf_points = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Współrzędna X (układ PL-2000)"], df["Współrzędna Y (układ PL-2000)"]),
    crs="EPSG:2180"
)

# Funkcja tworząca sześciokąt o zadanym środku i promieniu
def create_hexagon(center: tuple, size: float) -> Polygon:
    cx, cy = center
    angles = np.linspace(0, 2 * np.pi, 7)  # 7 punktów, by domknąć figurę
    points = [(cx + size * np.cos(a), cy + size * np.sin(a)) for a in angles]
    return Polygon(points)

hex_size = 200  # Promień heksagonu (dostosuj według potrzeb)

# Generuj siatkę heksagonów na podstawie zasięgu punktów
minx, miny, maxx, maxy = gdf_points.total_bounds
# Rozszerzenie granic, by siatka dobrze pokrywała obszar
minx -= hex_size
miny -= hex_size
maxx += hex_size
maxy += hex_size

hexagons = []
# Odstępy między centrami heksagonów
horiz_spacing = 1.5 * hex_size
vert_spacing = np.sqrt(3) * hex_size

x = minx
col = 0
while x < maxx:
    # Przesuń co drugi wiersz o połowę pionowego odstępu
    y_offset = vert_spacing / 2 if col % 2 else 0
    y = miny + y_offset
    while y < maxy:
        hexagons.append(create_hexagon((x, y), hex_size))
        y += vert_spacing
    x += horiz_spacing
    col += 1

# Jeśli w Excelu mamy 1479 rekordów, każdy reprezentujący heksagon, zamiast generować siatkę,
# przypisz geometryczny sześciokąt dla każdego rekordu na podstawie jego współrzędnych.

df["geometry"] = df.apply(lambda row: create_hexagon(
    (row["Współrzędna X (układ PL-2000)"], row["Współrzędna Y (układ PL-2000)"]),
    hex_size
), axis=1)

gdf_hex = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:2180")

print("Liczba wyświetlonych heksagonów:", gdf_hex.shape[0])

# Wizualizacja heksagonów (opcjonalnie można je dodatkowo przyciąć do granic Krakowa)
vmax = np.percentile(gdf_hex["Liczba mieszkańców"], 90)
fig, ax = plt.subplots(figsize=(10, 10))
gdf_hex.plot(
    ax=ax,
    column="Liczba mieszkańców",
    cmap="OrRd",
    edgecolor="gray",
    legend=True,
    vmin=0,
    vmax=vmax
)
ax.set_title("Mapa heksagonów zaludnienia Krakowa")
plt.show()