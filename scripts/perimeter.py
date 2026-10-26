"""Périmètre d'étude : contours et codes INSEE des communes (geo.api.gouv.fr)."""

import geopandas as gpd
import pandas as pd

from common import fetch, fetch_json, log, write_geojson
from config import (CACHE_DIR, CRS_METRIC, EPCI_AM, EPCI_VAR, EXCLUDED_COMMUNES,
                    FOCUS_EPCI, GEO_API)

FIELDS = "nom,code,codeEpci,codeDepartement,population,centre,contour"


def build():
    epcis = {**EPCI_VAR, **EPCI_AM}
    frames = []
    for code, name in epcis.items():
        path = fetch(f"{GEO_API}/epcis/{code}/communes?fields={FIELDS}&format=geojson&geometry=contour",
                     suffix=".geojson")
        g = gpd.read_file(path)
        g["epci"] = code
        g["epci_nom"] = name
        frames.append(g)
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    excluded = gdf["code"].isin(EXCLUDED_COMMUNES)
    missing = set(EXCLUDED_COMMUNES) - set(gdf["code"])
    if missing:
        raise RuntimeError(f"communes exclues introuvables dans les EPCI : {sorted(missing)}")
    gdf = gdf[~excluded].copy()
    gdf["dep"] = gdf["codeDepartement"]
    gdf["focus"] = gdf["epci"] == FOCUS_EPCI
    gdf["population"] = gdf["population"].fillna(0).astype(int)
    log(f"périmètre : {len(gdf)} communes "
        f"({(gdf.dep == '06').sum()} dans le 06, {(gdf.dep == '83').sum()} dans le 83)")

    # Contours simplifiés (≈ 40 m) pour l'affichage.
    disp = gdf.to_crs(CRS_METRIC)
    disp["geometry"] = disp.geometry.simplify(40, preserve_topology=True)
    write_geojson(disp, "communes.geojson",
                  props=["code", "nom", "dep", "epci", "epci_nom", "population", "focus"])

    # Géométries complètes conservées en cache pour les jointures spatiales.
    gdf[["code", "nom", "dep", "epci", "focus", "population", "geometry"]].to_file(
        CACHE_DIR / "perimeter_full.gpkg", driver="GPKG")
    return gdf


def load_perimeter():
    """Communes du périmètre, géométries complètes (WGS84)."""
    return gpd.read_file(CACHE_DIR / "perimeter_full.gpkg")


def france_centres():
    """Centre de toutes les communes et arrondissements municipaux de France : {code: (lon, lat, nom)}."""
    out = {}
    for extra in ("", "&type=arrondissement-municipal"):
        for c in fetch_json(f"{GEO_API}/communes?fields=code,nom,centre&format=json{extra}"):
            if c.get("centre"):
                lon, lat = c["centre"]["coordinates"]
                out[c["code"]] = (lon, lat, c["nom"])
    log(f"centres de communes France : {len(out)}")
    return out


if __name__ == "__main__":
    build()
