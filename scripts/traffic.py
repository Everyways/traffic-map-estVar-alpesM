"""Trafic routier : RD 06 (CD06), réseau national (TMJA DGITM), RD 83 (CD83 2017).

Sorties :
  data/traffic_lines.geojson   tronçons colorés par TMJA
  data/traffic_points.geojson  points de comptage CD06 (avec ou sans tronçon raccroché)
  data/traffic_heat.geojson    échantillons le long des tronçons pour la heatmap de densité
Champs normalisés : tmja, annee, source, type_comptage (+ route, pl_pct, note).
"""

import json
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, substring, unary_union

from common import datagouv_dataset, fetch, latest_resource, log, write_geojson
from config import (CACHE_DIR, CD06_PERM_SLUG, CD06_TEMP_SLUG, CD83_PAGE, CD83_SHP, CD83_WFS,
                    CRS_METRIC, HEAT_SAMPLE_STEP_M, OVERPASS_URLS, RRN_SLUG, SAME_SECTION_DIST_M,
                    SECTION_HALF_LENGTH_M, SNAP_MAX_DIST_M)
from perimeter import load_perimeter

OUT_COLS = ["route", "tmja", "annee", "source", "type_comptage", "pl_pct", "note"]


def _lower(gdf):
    gdf.columns = [c if c == "geometry" else c.lower() for c in gdf.columns]
    return gdf


def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", ".").str.replace(" ", ""), errors="coerce")


def _route_key(text):
    """'RD 6007', 'D6007', 'M 6007', '6007' -> '6007' ; 'RD 2085A' -> '2085A'."""
    if text is None:
        return None
    m = re.search(r"(\d+)\s*([A-Z]?)\b", str(text).upper())
    return f"{m.group(1).lstrip('0') or '0'}{m.group(2)}" if m else None


# --- CD06 ----------------------------------------------------------------------------------

def _read_cd06(slug):
    ds = datagouv_dataset(slug)
    res = latest_resource(ds, ["gpkg"])
    url = res.get("latest") or res["url"]
    gdf = _lower(gpd.read_file(fetch(url, suffix=".gpkg")))
    log(f"{slug} : {len(gdf)} lignes, colonnes {list(gdf.columns)}")
    return gdf, {"titre": ds["title"], "url": f"https://www.data.gouv.fr/datasets/{slug}",
                 "fichier": res["url"], "licence": ds.get("license"),
                 "mise_a_jour": res.get("last_modified")}


def load_cd06_temp():
    gdf, meta = _read_cd06(CD06_TEMP_SLUG)
    out = gpd.GeoDataFrame({
        "route": gdf["route"].astype(str).str.strip(),
        "tmja": _num(gdf["tmj_tv"]),
        "annee": _num(gdf["annee"]),
        "pl_pct": _num(gdf["pourc_pl_cumule"]) if "pourc_pl_cumule" in gdf else np.nan,
        "periode": gdf.get("periode", pd.Series([None] * len(gdf))).astype(str),
        "perm": False,
    }, geometry=gdf.geometry, crs=gdf.crs)
    out["source"] = "CD06 – comptages temporaires"
    out["type_comptage"] = "temporaire (1 semaine)"
    out["note"] = "TMJ mesuré sur une semaine (" + out["periode"] + "), non annualisé"
    return out, meta


def load_cd06_perm():
    gdf, meta = _read_cd06(CD06_PERM_SLUG)
    years = sorted({int(m.group(1)) for c in gdf.columns
                    if (m := re.fullmatch(r"tmja_(\d{4})", c))}, reverse=True)
    if not years:
        raise RuntimeError("CD06 permanents : aucune colonne tmja_AAAA")
    tmja = pd.Series(np.nan, index=gdf.index)
    annee = pd.Series(np.nan, index=gdf.index)
    pl = pd.Series(np.nan, index=gdf.index)
    for y in years:  # année la plus récente disponible pour chaque station
        v = _num(gdf[f"tmja_{y}"])
        take = tmja.isna() & (v > 0)
        tmja[take] = v[take]
        annee[take] = y
        if f"nb_pl_{y}" in gdf:
            p = _num(gdf[f"nb_pl_{y}"])
            pl[take] = (p[take] / v[take] * 100).round(1)
    out = gpd.GeoDataFrame({
        "route": gdf["route"].astype(str).str.strip(),
        "tmja": tmja, "annee": annee, "pl_pct": pl, "perm": True,
    }, geometry=gdf.geometry, crs=gdf.crs)
    out["source"] = "CD06 – comptages permanents"
    out["type_comptage"] = "permanent"
    out["note"] = "TMJA annuel, station " + gdf.get("libelle", pd.Series([""] * len(gdf))).astype(str)
    meta["annees"] = [min(years), max(years)]
    return out, meta


def dedupe_latest(points):
    """Un seul comptage par section : le plus récent (à égalité, le permanent)."""
    pts = points.to_crs(CRS_METRIC).copy()
    pts["key"] = pts["route"].map(_route_key)
    pts = pts.sort_values(["annee", "perm"], ascending=[False, False])
    kept = []
    for _, grp in pts.groupby("key", dropna=False):
        chosen = []
        for idx, geom in zip(grp.index, grp.geometry):
            if all(geom.distance(g) > SAME_SECTION_DIST_M for g in chosen):
                chosen.append(geom)
                kept.append(idx)
    return pts.loc[kept]


# --- Raccrochage au filaire OSM ------------------------------------------------------------

def osm_roads(bounds):
    w, s, e, n = bounds
    query = (f'[out:json][timeout:300];way["highway"]["ref"]({s},{w},{n},{e});out geom tags;')
    last = None
    for url in OVERPASS_URLS:
        try:
            path = fetch(url, suffix=".json", data=query, timeout=400)
            elements = json.loads(path.read_text(encoding="utf-8"))["elements"]
            break
        except Exception as e:  # noqa: BLE001 - on tente le miroir suivant
            last = e
            log(f"Overpass {url} indisponible : {e}")
    else:
        raise RuntimeError(f"Overpass indisponible : {last}")
    rows = []
    for el in elements:
        geom = el.get("geometry")
        if not geom or len(geom) < 2:
            continue
        for ref in str(el["tags"].get("ref", "")).split(";"):
            if re.match(r"^\s*(R?D|M)\s*\d", ref.upper()):
                rows.append({"key": _route_key(ref),
                             "geometry": LineString([(p["lon"], p["lat"]) for p in geom])})
    log(f"OSM : {len(rows)} tronçons de routes départementales/métropolitaines")
    return gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(CRS_METRIC)


def snap_sections(points, roads):
    """Associe à chaque comptage la portion de route OSM de même numéro qui l'entoure :
    jusqu'à mi-distance du comptage voisin, au plus SECTION_HALF_LENGTH_M de chaque côté."""
    lines, snapped = [], pd.Series(False, index=points.index)
    for key, grp in points.groupby("key"):
        cand = roads[roads["key"] == key]
        if cand.empty:
            continue
        near = cand[cand.distance(unary_union(grp.geometry)) < 5000]
        merged = linemerge(list(near.geometry)) if len(near) else None
        if merged is None or merged.is_empty:
            continue
        parts = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
        proj = []
        for idx, pt in zip(grp.index, grp.geometry):
            d = [p.distance(pt) for p in parts]
            i = int(np.argmin(d))
            if d[i] <= SNAP_MAX_DIST_M:
                proj.append((i, parts[i].project(pt), idx))
        for i in {p[0] for p in proj}:
            seq = sorted(p for p in proj if p[0] == i)
            part = parts[i]
            for j, (_, s, idx) in enumerate(seq):
                left = s - SECTION_HALF_LENGTH_M
                right = s + SECTION_HALF_LENGTH_M
                if j > 0:
                    left = max(left, (seq[j - 1][1] + s) / 2)
                if j < len(seq) - 1:
                    right = min(right, (s + seq[j + 1][1]) / 2)
                seg = substring(part, max(left, 0), min(right, part.length))
                if seg.length >= 20:
                    lines.append((idx, seg))
                    snapped[idx] = True
    if lines:
        idxs, geoms = zip(*lines)
        sections = points.loc[list(idxs)].copy()
        sections["geometry"] = list(geoms)
        sections = sections.set_geometry("geometry", crs=CRS_METRIC)
    else:
        sections = points.iloc[0:0].copy()
    sections["note"] = sections["note"] + " · tronçon représenté autour du point de comptage (OSM)"
    log(f"CD06 : {snapped.sum()}/{len(points)} comptages raccrochés à un tronçon OSM")
    return sections, snapped


# --- Réseau routier national ----------------------------------------------------------------

def load_rrn(perimeter_m):
    ds = datagouv_dataset(RRN_SLUG)
    cands = []
    for r in ds["resources"]:
        m = re.search(r"(20\d{2})", r.get("title", ""))
        if m and "shp" in r.get("title", "").lower():
            cands.append((int(m.group(1)), r))
    year, res = max(cands, key=lambda c: c[0])
    path = fetch(res["url"], suffix=".zip")
    gdf = _lower(gpd.read_file(f"zip://{path}"))
    log(f"TMJA RRN {year} : {len(gdf)} sections, colonnes {list(gdf.columns)}, crs {gdf.crs}")
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_METRIC)
    if gdf.geometry.isna().all():
        gdf["geometry"] = [LineString([(a, b), (c, d)]) for a, b, c, d in
                           zip(_num(gdf["xd"]), _num(gdf["yd"]), _num(gdf["xf"]), _num(gdf["yf"]))]
        gdf = gdf.set_geometry("geometry", crs=CRS_METRIC)
    gdf = gdf.to_crs(CRS_METRIC)
    gdf = gdf[gdf.intersects(perimeter_m.buffer(500))].copy()

    # Les noms de champs du shapefile sont tronqués à 10 caractères (typecompta, anneemesur…).
    def col(*prefixes, text=False):
        for prefix in prefixes:
            for c in gdf.columns:
                if c.startswith(prefix) and (not text or _num(gdf[c]).isna().all()):
                    return gdf[c]
        return pd.Series([None] * len(gdf), index=gdf.index)

    conc = col("concession").astype(str).str.upper().str.startswith("C")
    ratio = _num(col("ratio", "pctpl"))
    out = gpd.GeoDataFrame({
        "route": col("route").astype(str).str.replace(r"^([A-Z]+)0*(\d)", r"\1\2", regex=True),
        "tmja": _num(col("tmja")),
        "annee": _num(col("anneemes")).fillna(year),
        "source": np.where(conc, f"TMJA RRN {year} (DGITM) – section concédée",
                           f"TMJA RRN {year} (DGITM)"),
        "type_comptage": col("typecomp", text=True).astype(str).str.lower(),
        "pl_pct": ratio,
        "note": np.where(conc, "Autoroute concédée", ""),
    }, geometry=gdf.geometry, crs=CRS_METRIC)
    out = out[out["tmja"] > 0]
    log(f"TMJA RRN : {len(out)} sections dans le périmètre, dont {int(conc.loc[out.index].sum())} concédées")
    meta = {"titre": ds["title"], "url": f"https://www.data.gouv.fr/datasets/{RRN_SLUG}",
            "fichier": res["url"], "licence": ds.get("license"), "millesime": year,
            "sections": len(out), "sections_concedees": int(conc.loc[out.index].sum())}
    return out, meta


# --- RD 83 (2017) ---------------------------------------------------------------------------

def load_cd83(perimeter_m):
    try:
        gdf = gpd.read_file(fetch(CD83_WFS, suffix=".geojson"))
        fichier = CD83_WFS
    except Exception as e:  # noqa: BLE001 - repli sur l'archive SHP
        log(f"WFS CD83 indisponible ({e}), repli sur l'archive SHP")
        gdf = gpd.read_file(f"zip://{fetch(CD83_SHP, suffix='.zip')}")
        fichier = CD83_SHP
    gdf = _lower(gdf)
    log(f"CD83 : {len(gdf)} entités, colonnes {list(gdf.columns)}, crs {gdf.crs}")
    gdf = gdf.to_crs(CRS_METRIC)
    gdf = gdf[gdf.intersects(perimeter_m.buffer(200))].copy()
    years = sorted({int(m.group(1)) for c in gdf.columns
                    if (m := re.fullmatch(r"t?mja_(\d{4})", c))}, reverse=True)
    if not years:
        raise RuntimeError("CD83 : aucune colonne MJA_AAAA")
    tmja = pd.Series(np.nan, index=gdf.index)
    annee = pd.Series(np.nan, index=gdf.index)
    for y in years:
        c = f"mja_{y}" if f"mja_{y}" in gdf else f"tmja_{y}"
        v = _num(gdf[c])
        take = tmja.isna() & (v > 0)
        tmja[take], annee[take] = v[take], y
    route_col = next((c for c in gdf.columns if re.search(r"route|^rd|axe|voie", c)), None)
    type_col = next((c for c in gdf.columns if "type" in c), None)
    out = gpd.GeoDataFrame({
        "route": gdf[route_col].astype(str) if route_col else "",
        "tmja": tmja, "annee": annee,
        "source": "CD83 – comptages routiers 2017 (DataSud)",
        "type_comptage": gdf[type_col].astype(str).str.lower() if type_col else "non précisé",
        "pl_pct": np.nan,
        "note": "Donnée ancienne (2017) : seul jeu ouvert disponible pour les RD du Var",
    }, geometry=gdf.geometry, crs=CRS_METRIC)
    out = out[out["tmja"] > 0]
    log(f"CD83 : {len(out)} sections dans le périmètre (années {years})")
    return out, {"titre": "Comptages routiers sur le réseau départemental du Var_2017 et 2021",
                 "url": CD83_PAGE, "fichier": fichier, "licence": "lov2",
                 "millesime": max(years), "sections": len(out)}


# --- Assemblage ----------------------------------------------------------------------------

def heat_samples(lines):
    rows = []
    for geom, tmja in zip(lines.geometry, lines["tmja"]):
        for part in getattr(geom, "geoms", [geom]):
            n = max(1, int(part.length // HEAT_SAMPLE_STEP_M))
            for k in range(n):
                rows.append({"w": float(tmja), "geometry": part.interpolate((k + 0.5) / n, normalized=True)})
    return gpd.GeoDataFrame(rows, crs=CRS_METRIC)


def build():
    per = load_perimeter().to_crs(CRS_METRIC)
    per_union = unary_union(per.geometry)
    meta = {}

    temp, meta["cd06_temporaires"] = load_cd06_temp()
    perm, meta["cd06_permanents"] = load_cd06_perm()
    pts = pd.concat([temp.to_crs(CRS_METRIC), perm.to_crs(CRS_METRIC)], ignore_index=True)
    pts = gpd.GeoDataFrame(pts, geometry="geometry", crs=CRS_METRIC)
    pts = pts[(pts["tmja"] > 0) & pts["annee"].notna() & pts.within(per_union.buffer(100))]
    pts = dedupe_latest(pts)
    meta["cd06_temporaires"]["comptages_retenus"] = int((~pts["perm"]).sum())
    meta["cd06_permanents"]["comptages_retenus"] = int(pts["perm"].sum())
    meta["cd06_temporaires"]["annees"] = [int(pts.loc[~pts.perm, "annee"].min()),
                                          int(pts.loc[~pts.perm, "annee"].max())]

    bounds = gpd.GeoSeries([per_union.buffer(2000)], crs=CRS_METRIC).to_crs("EPSG:4326").total_bounds
    roads = osm_roads(bounds)
    sections, snapped = snap_sections(pts, roads)
    pts["raccroche"] = snapped
    meta["cd06_temporaires"]["raccroches_osm"] = int(snapped[~pts.perm].sum())
    meta["cd06_permanents"]["raccroches_osm"] = int(snapped[pts.perm].sum())

    rrn, meta["rrn"] = load_rrn(per_union)
    cd83, meta["cd83"] = load_cd83(per_union)

    lines = pd.concat([sections[OUT_COLS + ["geometry"]], rrn, cd83], ignore_index=True)
    lines = gpd.GeoDataFrame(lines, geometry="geometry", crs=CRS_METRIC)
    lines["tmja"] = lines["tmja"].round().astype(int)
    lines["annee"] = lines["annee"].astype(int)
    lines["geometry"] = lines.geometry.simplify(10)
    lines = lines.sort_values("tmja")  # les plus chargés dessinés au-dessus
    write_geojson(lines, "traffic_lines.geojson", props=OUT_COLS)

    pts_out = pts.copy()
    pts_out["tmja"] = pts_out["tmja"].round().astype(int)
    pts_out["annee"] = pts_out["annee"].astype(int)
    write_geojson(pts_out, "traffic_points.geojson", props=OUT_COLS + ["raccroche"])

    heat = pd.concat([heat_samples(lines),
                      gpd.GeoDataFrame({"w": pts_out.loc[~pts_out.raccroche, "tmja"].astype(float)},
                                       geometry=pts_out.loc[~pts_out.raccroche].geometry,
                                       crs=CRS_METRIC)], ignore_index=True)
    write_geojson(gpd.GeoDataFrame(heat, geometry="geometry", crs=CRS_METRIC),
                  "traffic_heat.geojson", precision=4)

    # Comptages par commune (fiches communales) : points CD06 + milieu des tronçons.
    allc = pd.concat([pts_out[OUT_COLS + ["geometry"]],
                      gpd.GeoDataFrame(lines[OUT_COLS], geometry=lines.geometry.interpolate(0.5, normalized=True),
                                       crs=CRS_METRIC).loc[~lines.source.str.startswith("CD06")]],
                     ignore_index=True)
    allc = gpd.GeoDataFrame(allc, geometry="geometry", crs=CRS_METRIC)
    joined = gpd.sjoin(allc, per[["code", "geometry"]], predicate="within")
    by_commune = {}
    for code, grp in joined.groupby("code"):
        grp = grp.sort_values("tmja", ascending=False)
        by_commune[code] = [{"route": r.route, "tmja": int(r.tmja), "annee": int(r.annee),
                             "source": r.source} for r in grp.head(10).itertuples()]
    Path(CACHE_DIR / "counts_by_commune.json").write_text(json.dumps(by_commune, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, ensure_ascii=False, default=str))
