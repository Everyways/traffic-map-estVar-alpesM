"""Lignes de transport en commun (GTFS, transport.data.gouv.fr) : tracés et fréquences.

La fréquence est calculée pour un jour de référence par réseau : le mardi, dans les
8 semaines suivant la génération et dans la période de validité du GTFS, qui compte
le plus de courses (ce qui écarte les jours fériés et vacances creuses).

Sorties :
  data/transit.geojson               une entité par ligne desservant le périmètre
  .cache/transit_by_commune.json     lignes et courses par commune (fiches communales)
"""

import io
import json
import zipfile
from datetime import date, timedelta

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import unary_union

from common import datagouv_dataset, fetch, fetch_json, log, write_geojson
from config import CACHE_DIR, CRS_METRIC, GTFS_FEEDS, PEAK_WINDOW, TRANSPORT_API
from perimeter import load_perimeter

ROUTE_TYPES = {0: "tram", 1: "métro", 2: "train", 3: "bus", 4: "bateau", 5: "tramway à câble",
               6: "téléphérique", 7: "funiculaire", 11: "trolleybus", 12: "monorail"}
# Types étendus (centaines) : 1xx train, 2xx car, 7xx bus, 9xx tram, 13xx téléphérique.
EXT_ROUTE_TYPES = {1: "train", 2: "car", 4: "métro", 7: "bus", 9: "tram", 10: "bateau",
                   13: "téléphérique", 14: "funiculaire"}


def route_mode(value):
    t = int(value) if str(value).strip().isdigit() else 3
    return ROUTE_TYPES.get(t) if t < 100 else EXT_ROUTE_TYPES.get(t // 100, "bus")


class Gtfs:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = {n.rsplit("/", 1)[-1]: n for n in self.z.namelist()}

    def has(self, name):
        return name in self.names

    def read(self, name, usecols=None):
        with self.z.open(self.names[name]) as f:
            raw = f.read()
        df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding="utf-8-sig", keep_default_na=False)
        df.columns = [c.strip() for c in df.columns]
        if usecols:
            df = df[[c for c in usecols if c in df.columns]]
        return df


def _dataset(slug, catalogue):
    """Fiche détaillée (avec historique) d'un jeu transport.data.gouv.fr.
    Repli sur l'identifiant data.gouv.fr quand le slug n'est pas dans le catalogue."""
    ds = next((d for d in catalogue if d.get("slug") == slug), None)
    ident = ds.get("datagouv_id") or ds.get("id") if ds else None
    if ident is None:
        try:
            ident = datagouv_dataset(slug)["id"]
        except Exception as e:  # noqa: BLE001 - jeu absent des deux portails
            log(f"{slug} : introuvable sur data.gouv.fr ({e})")
            return None
    try:
        return fetch_json(f"{TRANSPORT_API}/{ident}")
    except RuntimeError as e:
        log(f"{slug} : fiche transport.data.gouv.fr indisponible ({e})")
        return None


def _gtfs_resources(ds):
    return [r for r in ds.get("resources", [])
            if (r.get("format") or "").upper() == "GTFS" and r.get("type", "main") == "main"]


def _download(ds, r):
    """GTFS du producteur ; à défaut, dernière copie sauvegardée par transport.data.gouv.fr."""
    url = r.get("url") or r.get("original_url")
    try:
        return fetch(url, suffix=".zip", timeout=90, retries=2), url, None
    except RuntimeError as e:
        backups = sorted((h["payload"] for h in ds.get("history", [])
                          if h.get("resource_id") == r.get("id") and h.get("payload", {}).get("permanent_url")),
                         key=lambda p: p.get("download_datetime", ""), reverse=True)
        if not backups:
            raise
        b = backups[0]
        log(f"{url} injoignable ({e}) : copie de sauvegarde du {b['download_datetime'][:10]}")
        return fetch(b["permanent_url"], suffix=".zip"), b["permanent_url"], b["download_datetime"][:10]


def _active_services(g, day):
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][day.weekday()]
    ymd = day.strftime("%Y%m%d")
    active = set()
    if g.has("calendar.txt"):
        cal = g.read("calendar.txt")
        ok = (cal[wd] == "1") & (cal["start_date"] <= ymd) & (cal["end_date"] >= ymd)
        active |= set(cal.loc[ok, "service_id"])
    if g.has("calendar_dates.txt"):
        cd = g.read("calendar_dates.txt")
        cd = cd[cd["date"] == ymd]
        active |= set(cd.loc[cd["exception_type"] == "1", "service_id"])
        active -= set(cd.loc[cd["exception_type"] == "2", "service_id"])
    return active


def _feed_range(g):
    dates = []
    if g.has("calendar.txt"):
        cal = g.read("calendar.txt")
        dates += list(cal["start_date"]) + list(cal["end_date"])
    if g.has("calendar_dates.txt"):
        dates += list(g.read("calendar_dates.txt")["date"])
    dates = [d for d in dates if len(d) == 8]
    to_date = lambda s: date(int(s[:4]), int(s[4:6]), int(s[6:]))  # noqa: E731
    return to_date(min(dates)), to_date(max(dates))


def reference_day(g, trips):
    start, end = _feed_range(g)
    today = date.today()
    lo = max(start, today) if end >= today else start
    days = [lo + timedelta(days=i) for i in range(0, 56)]
    days = [d for d in days if d.weekday() == 1 and d <= end] or \
           [lo + timedelta(days=i) for i in range(0, 7) if lo + timedelta(days=i) <= end]
    best = max(days, key=lambda d: trips["service_id"].isin(_active_services(g, d)).sum())
    return best, _active_services(g, best)


def _seconds(t):
    h, m, s = (t.str.split(":", expand=True).astype(float).T.values)
    return h * 3600 + m * 60 + s


def process_feed(path, network, colour, per, per_union):
    g = Gtfs(path)
    routes = g.read("routes.txt")
    for c in ("route_short_name", "route_long_name", "route_type"):
        if c not in routes:
            routes[c] = ""
    trips = g.read("trips.txt", ["route_id", "service_id", "trip_id", "direction_id", "shape_id"])
    for c in ("direction_id", "shape_id"):
        if c not in trips:
            trips[c] = ""
    stops = g.read("stops.txt", ["stop_id", "stop_lat", "stop_lon", "location_type"])
    stops = stops[stops["stop_lat"] != ""]
    stops = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(
        stops["stop_lon"].astype(float), stops["stop_lat"].astype(float)), crs="EPSG:4326")
    stops = gpd.sjoin(stops, per[["code", "geometry"]], how="left", predicate="within")
    stop_commune = stops.set_index("stop_id")["code"].dropna().to_dict()

    st = g.read("stop_times.txt", ["trip_id", "stop_id", "stop_sequence", "departure_time"])
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    st["commune"] = st["stop_id"].map(stop_commune)
    served_trips = set(st.loc[st["commune"].notna(), "trip_id"])
    trips = trips[trips["trip_id"].isin(served_trips)]
    if trips.empty:
        log(f"{network} : aucune ligne ne dessert le périmètre")
        return [], {}, None
    ref, active = reference_day(g, trips)
    trips = trips.assign(active=trips["service_id"].isin(active))

    first = (st[st["trip_id"].isin(trips["trip_id"])]
             .sort_values("stop_sequence").groupby("trip_id").first())
    trips = trips.merge(first[["departure_time"]], left_on="trip_id", right_index=True, how="left")
    trips["dep_s"] = _seconds(trips["departure_time"].replace("", "00:00:00"))
    p0, p1 = (_seconds(pd.Series([t])).item() for t in PEAK_WINDOW)

    shapes = None
    if g.has("shapes.txt") and (trips["shape_id"] != "").any():
        sh = g.read("shapes.txt", ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
        sh = sh[sh["shape_id"].isin(set(trips["shape_id"]))]
        sh["shape_pt_sequence"] = sh["shape_pt_sequence"].astype(int)
        shapes = {sid: LineString(list(zip(grp["shape_pt_lon"].astype(float), grp["shape_pt_lat"].astype(float))))
                  for sid, grp in sh.sort_values("shape_pt_sequence").groupby("shape_id") if len(grp) > 1}
    stop_xy = dict(zip(stops["stop_id"], zip(stops.geometry.x, stops.geometry.y)))

    feats = []
    clip = per_union.buffer(3000)
    for rid, rt in trips.groupby("route_id"):
        r = routes[routes["route_id"] == rid].iloc[0]
        act = rt[rt["active"]]
        by_dir = act.groupby("direction_id").size()
        dirs_known = (rt["direction_id"] != "").any()
        busiest = by_dir.idxmax() if len(by_dir) else None
        bd = act[act["direction_id"] == busiest] if busiest is not None else act.iloc[0:0]
        peak = int(((bd["dep_s"] >= p0) & (bd["dep_s"] < p1)).sum())
        # Tracé : le parcours le plus fréquent de la ligne.
        pool = act if len(act) else rt
        geom = None
        if shapes is not None:
            sid = pool["shape_id"].value_counts().index[0]
            geom = shapes.get(sid)
        if geom is None:
            tid = pool["trip_id"].iloc[0]
            seq = st[st["trip_id"] == tid].sort_values("stop_sequence")["stop_id"]
            pts = [stop_xy[s] for s in seq if s in stop_xy]
            geom = LineString(pts) if len(pts) > 1 else None
        if geom is None:
            continue
        gm = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(CRS_METRIC).iloc[0].intersection(clip)
        if gm.is_empty:
            continue
        feats.append({
            "reseau": network, "couleur": colour,
            "ligne": r["route_short_name"] or r["route_long_name"] or rid,
            "nom": r["route_long_name"],
            "mode": route_mode(r["route_type"]) or "bus",
            "departs_total": int(len(act)),
            "departs_sens": int(by_dir.max()) if dirs_known and len(by_dir) else None,
            "pointe": peak if dirs_known else None,
            "intervalle_pointe": round(120 / peak) if dirs_known and peak else None,
            "date_ref": ref.isoformat(),
            "geometry": gm.simplify(15),
        })

    # Desserte par commune (courses actives le jour de référence).
    act_ids = set(trips.loc[trips["active"], "trip_id"])
    tc = st[st["trip_id"].isin(act_ids) & st["commune"].notna()][["trip_id", "commune"]].drop_duplicates()
    tc = tc.merge(trips[["trip_id", "route_id"]], on="trip_id")
    names = dict(zip(routes["route_id"], routes["route_short_name"].where(
        routes["route_short_name"] != "", routes["route_long_name"])))
    by_commune = {}
    for code, grp in tc.groupby("commune"):
        by_commune[code] = {"courses": int(grp["trip_id"].nunique()),
                            "lignes": sorted({f"{network} {names.get(x, x)}" for x in grp["route_id"]}),
                            "trips": sorted(set(network + "|" + grp["trip_id"]))}
    log(f"{network} : {len(feats)} lignes, jour de référence {ref}")
    return feats, by_commune, ref.isoformat()


def build():
    per = load_perimeter()
    per_union = unary_union(per.to_crs(CRS_METRIC).geometry)
    catalogue = fetch_json(TRANSPORT_API)
    feats, by_commune, meta = [], {}, []
    for slug, network, colour in GTFS_FEEDS:
        ds = _dataset(slug, catalogue)
        res = _gtfs_resources(ds) if ds else []
        entry = {"reseau": network, "url": f"https://transport.data.gouv.fr/datasets/{slug}"}
        if ds is None or not res:
            log(f"{network} : jeu {slug} introuvable ou sans GTFS")
            entry["statut"] = "introuvable"
            meta.append(entry)
            continue
        entry.update({"titre": ds.get("title"), "licence": ds.get("licence"),
                      "editeur": (ds.get("publisher") or {}).get("name"), "fichiers": []})
        for r in res:
            url = r.get("url") or r.get("original_url")
            try:
                path, url, backup = _download(ds, r)
                f, bc, ref = process_feed(path, network, colour, per, per_union)
            except Exception as e:  # noqa: BLE001 - un GTFS invalide ne bloque pas les autres
                log(f"{network} : GTFS {url} illisible ({e})")
                entry["fichiers"].append({"url": url, "erreur": str(e)})
                continue
            feats += f
            for code, v in bc.items():
                cur = by_commune.setdefault(code, {"courses": 0, "lignes": [], "trips": []})
                cur["courses"] += v["courses"]
                cur["lignes"] = sorted(set(cur["lignes"]) | set(v["lignes"]))
                cur["trips"] = sorted(set(cur["trips"]) | set(v["trips"]))
            entry["fichiers"].append({"url": url, "date_ref": ref, "lignes": len(f), "sauvegarde_du": backup})
        entry["statut"] = "ok" if any("lignes" in x for x in entry["fichiers"]) else "erreur"
        meta.append(entry)

    gdf = gpd.GeoDataFrame(feats, geometry="geometry", crs=CRS_METRIC)
    gdf = gdf.sort_values("departs_total")
    write_geojson(gdf, "transit.geojson")
    (CACHE_DIR / "transit_by_commune.json").write_text(json.dumps(by_commune, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, ensure_ascii=False))
