"""Flux domicile-travail commune à commune (INSEE, base flux de mobilité).

Sorties :
  data/flows.geojson   lignes origine -> destination (hors flux internes à une commune)
  .cache/flows_table.csv  table complète filtrée sur le périmètre (pour les statistiques)
"""

import re
import zipfile

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from common import fetch, log, write_geojson
from config import CACHE_DIR, FLOWS_MIN_KEEP, INSEE_FLOWS_PAGES, MONACO_CENTRE
from perimeter import france_centres, load_perimeter


def _insee_csv():
    for year, page in INSEE_FLOWS_PAGES:
        try:
            html = fetch(page, suffix=".html").read_text(encoding="utf-8", errors="replace")
        except RuntimeError as e:
            log(f"INSEE {year} indisponible : {e}")
            continue
        m = re.search(r'href="([^"]*fichier/[^"]*csv[^"]*\.zip)"', html)
        if not m:
            log(f"INSEE {year} : lien CSV introuvable sur {page}")
            continue
        url = m.group(1)
        if url.startswith("/"):
            url = "https://www.insee.fr" + url
        return year, page, url, fetch(url, suffix=".zip")
    raise RuntimeError("aucun millésime INSEE des flux domicile-travail accessible")


def load_table():
    year, page, url, path = _insee_csv()
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as f:
            df = pd.read_csv(f, sep=";", dtype=str, encoding="utf-8")
    flux_col = next(c for c in df.columns if c.upper().startswith("NBFLUX"))
    df = df.rename(columns={flux_col: "flux"})
    df["flux"] = pd.to_numeric(df["flux"].str.replace(",", "."), errors="coerce").fillna(0)
    log(f"INSEE {year} : {len(df)} couples, colonnes {list(df.columns)}")
    meta = {"titre": f"Mobilités professionnelles en {year} : déplacements domicile - lieu de travail",
            "url": page, "fichier": url, "millesime": int(year), "variable": flux_col,
            "licence": "Licence Ouverte (conditions de réutilisation de l'INSEE)"}
    return df, meta


def build():
    per = load_perimeter()
    codes = set(per["code"])
    focus = set(per.loc[per["focus"], "code"])
    df, meta = load_table()
    df = df[df["CODGEO"].isin(codes) | df["DCLT"].isin(codes)].copy()
    df.to_csv(CACHE_DIR / "flows_table.csv", index=False)

    centres = france_centres()
    for lib_col, code_col in (("LIBGEO", "CODGEO"), ("L_DCLT", "DCLT")):
        mon = df[lib_col].fillna("").str.contains("Monaco", case=False)
        for c in df.loc[mon, code_col].unique():
            centres.setdefault(c, (*MONACO_CENTRE, "Monaco"))

    ext = df[df["CODGEO"] != df["DCLT"]].copy()
    ext["focus"] = ext["CODGEO"].isin(focus) | ext["DCLT"].isin(focus)
    known = ext["CODGEO"].isin(centres) & ext["DCLT"].isin(centres)
    unresolved = (ext.loc[~known]
                  .assign(lieu=lambda d: d["L_DCLT"].where(~d["DCLT"].isin(centres), d["LIBGEO"]))
                  .groupby("lieu")["flux"].sum().round().sort_values(ascending=False))
    if len(unresolved):
        log(f"flux non localisables : {unresolved.to_dict()}")
    ext = ext[known & ((ext["flux"] >= FLOWS_MIN_KEEP) | ext["focus"])]

    gdf = gpd.GeoDataFrame({
        "o": ext["CODGEO"], "on": ext["LIBGEO"], "d": ext["DCLT"], "dn": ext["L_DCLT"],
        "v": ext["flux"].round(1), "f": ext["focus"],
        "geometry": [LineString([centres[o][:2], centres[d][:2]]) for o, d in zip(ext["CODGEO"], ext["DCLT"])],
    }, crs="EPSG:4326").sort_values("v")
    write_geojson(gdf, "flows.geojson", precision=4)

    meta.update({
        "couples_perimetre": int(len(df)),
        "flux_lignes": int(len(gdf)),
        "seuil_conserve": FLOWS_MIN_KEEP,
        "non_localises": {k: int(v) for k, v in unresolved.items()},
    })
    return meta


if __name__ == "__main__":
    print(build())
