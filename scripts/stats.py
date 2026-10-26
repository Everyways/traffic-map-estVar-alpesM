"""Fiches communales et synthèse du Pays de Fayence.

Sorties :
  data/communes_stats.json  {code INSEE: fiche}
  data/focus.json           synthèse du territoire zoomé (Pays de Fayence)
"""

import json

import pandas as pd

from common import write_json
from config import CACHE_DIR, FOCUS_NAME
from perimeter import load_perimeter


def _top(df, key, label, n):
    g = df.groupby([key, label])["flux"].sum().sort_values(ascending=False).head(n)
    return [{"code": k, "nom": lib, "flux": int(round(v))} for (k, lib), v in g.items()]


def _load(name):
    path = CACHE_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build():
    per = load_perimeter()
    flows = pd.read_csv(CACHE_DIR / "flows_table.csv", dtype={"CODGEO": str, "DCLT": str})
    tc = _load("transit_by_commune.json")
    counts = _load("counts_by_commune.json")

    fiches = {}
    for r in per.itertuples():
        out = flows[flows["CODGEO"] == r.code]
        inn = flows[flows["DCLT"] == r.code]
        intra = float(out.loc[out["DCLT"] == r.code, "flux"].sum())
        t = tc.get(r.code, {})
        fiches[r.code] = {
            "nom": r.nom, "population": int(r.population),
            "actifs": int(round(out["flux"].sum())),
            "sur_place": int(round(intra)),
            "sortants": int(round(out["flux"].sum() - intra)),
            "emplois": int(round(inn["flux"].sum())),
            "entrants": int(round(inn["flux"].sum() - intra)),
            "top_dest": _top(out[out["DCLT"] != r.code], "DCLT", "L_DCLT", 5),
            "top_orig": _top(inn[inn["CODGEO"] != r.code], "CODGEO", "LIBGEO", 5),
            "tc_lignes": t.get("lignes", []),
            "tc_courses": t.get("courses", 0),
            "comptages": counts.get(r.code, []),
        }
    write_json(fiches, "communes_stats.json")

    focus = per[per["focus"]]
    fc = set(focus["code"])
    out = flows[flows["CODGEO"].isin(fc)]
    inn = flows[flows["DCLT"].isin(fc)]
    internal = out[out["DCLT"].isin(fc)]
    trips, lines = set(), set()
    for c in fc:
        trips |= set(tc.get(c, {}).get("trips", []))
        lines |= set(tc.get(c, {}).get("lignes", []))
    allcounts = sorted((dict(x, commune=fiches[c]["nom"]) for c in fc for x in counts.get(c, [])),
                       key=lambda x: -x["tmja"])
    write_json({
        "nom": FOCUS_NAME,
        "communes": sorted(focus["nom"]),
        "population": int(focus["population"].sum()),
        "actifs": int(round(out["flux"].sum())),
        "travaillent_dans_territoire": int(round(internal["flux"].sum())),
        "travaillent_hors_territoire": int(round(out["flux"].sum() - internal["flux"].sum())),
        "emplois": int(round(inn["flux"].sum())),
        "entrants_exterieurs": int(round(inn["flux"].sum() - internal["flux"].sum())),
        "top_dest_ext": _top(out[~out["DCLT"].isin(fc)], "DCLT", "L_DCLT", 10),
        "top_orig_ext": _top(inn[~inn["CODGEO"].isin(fc)], "CODGEO", "LIBGEO", 10),
        "tc_lignes": sorted(lines),
        "tc_courses": len(trips),
        "comptages": allcounts,
    }, "focus.json")


if __name__ == "__main__":
    build()
