"""Outils partagés : téléchargement avec cache, écriture GeoJSON allégée, journal."""

import hashlib
import json
import sys
import time
from pathlib import Path

import requests
from shapely.geometry import mapping

from config import CACHE_DIR, DATA_DIR, DATAGOUV_API

USER_AGENT = "traffic-map-estvar-alpesm (+https://github.com/Everyways/traffic-map-estVar-alpesM)"
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def log(*args):
    print("[build]", *args, file=sys.stderr, flush=True)


def fetch(url, *, suffix="", data=None, timeout=300, retries=4, refresh=False):
    """Télécharge `url` (GET, ou POST si `data`) dans le cache et renvoie le chemin local."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1((url + (data or "")).encode()).hexdigest()[:16]
    path = CACHE_DIR / f"{key}{suffix}"
    if path.exists() and not refresh:
        return path
    last = None
    for attempt in range(retries):
        try:
            if data is None:
                r = _session.get(url, timeout=timeout, stream=True)
            else:
                r = _session.post(url, data={"data": data}, timeout=timeout, stream=True)
            r.raise_for_status()
            tmp = path.with_suffix(path.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            tmp.replace(path)
            log(f"téléchargé {url} ({path.stat().st_size / 1e6:.1f} Mo)")
            return path
        except requests.RequestException as e:
            last = e
            wait = 2 ** (attempt + 1)
            log(f"échec {url} ({e}), nouvel essai dans {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"téléchargement impossible : {url} ({last})")


def fetch_json(url, **kw):
    return json.loads(fetch(url, suffix=".json", **kw).read_text(encoding="utf-8"))


def datagouv_dataset(slug):
    return fetch_json(f"{DATAGOUV_API}/datasets/{slug}/")


def latest_resource(dataset, formats):
    """Ressource la plus récente parmi les formats donnés (ordre de préférence)."""
    for fmt in formats:
        res = [r for r in dataset["resources"] if (r.get("format") or "").lower() == fmt]
        if res:
            return max(res, key=lambda r: r.get("last_modified") or "")
    raise RuntimeError(f"aucune ressource {formats} dans {dataset.get('slug')}")


def _round_coords(coords, nd):
    if isinstance(coords[0], (float, int)):
        return [round(c, nd) for c in coords[:2]]
    return [_round_coords(c, nd) for c in coords]


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN
        return None
    if hasattr(v, "item"):  # numpy scalar
        return v.item()
    return v


def write_geojson(gdf, name, *, precision=5, props=None):
    """Écrit un GeoDataFrame (WGS84) en GeoJSON compact dans data/."""
    gdf = gdf.to_crs("EPSG:4326")
    cols = props if props is not None else [c for c in gdf.columns if c != "geometry"]
    feats = []
    for row in gdf.itertuples(index=False):
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        g = mapping(geom)
        g = {"type": g["type"], "coordinates": _round_coords(g["coordinates"], precision)}
        feats.append({
            "type": "Feature",
            "geometry": g,
            "properties": {c: _clean(getattr(row, c)) for c in cols},
        })
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / name
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": feats},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    log(f"écrit {path.name} : {len(feats)} entités, {path.stat().st_size / 1e3:.0f} ko")
    return path


def write_json(obj, name):
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / name
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=_clean),
                    encoding="utf-8")
    log(f"écrit {path.name} : {path.stat().st_size / 1e3:.0f} ko")
    return path


def read_json(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
