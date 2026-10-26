"""Chaîne complète : téléchargement -> nettoyage -> GeoJSON légers dans data/.

Usage : python scripts/build_all.py
"""

import sys
from datetime import date

import flows
import perimeter
import stats
import traffic
import transit
from common import log, write_json
from config import DATA_DIR

MAX_TOTAL_MB = 5.0


def main():
    meta = {"genere_le": date.today().isoformat(), "sources": {}, "lacunes": []}
    perimeter.build()
    meta["sources"]["trafic"] = traffic.build()
    meta["sources"]["flux"] = flows.build()
    meta["sources"]["tc"] = transit.build()
    stats.build()

    t = meta["sources"]["trafic"]
    gaps = meta["lacunes"]
    gaps.append("RD du Var : seul le jeu CD83 de 2017 est ouvert ; valeurs anciennes, "
                "couverture partielle du réseau départemental.")
    gaps.append("Comptages temporaires CD06 : TMJ mesuré sur une semaine, non annualisé ; "
                "le tronçon dessiné entoure le point de comptage (≤ 1,5 km de chaque côté).")
    if t["rrn"].get("sections_concedees", 0) == 0:
        gaps.append("Autoroutes concédées (A8 Escota) : aucune donnée ouverte, exclues de la heatmap.")
    for e in meta["sources"]["tc"]:
        if e["statut"] != "ok":
            gaps.append(f"GTFS {e['reseau']} : {e['statut']}.")
    gaps.append("Pays de Fayence : pas de réseau urbain publié en GTFS ; desserte par les lignes Zou!.")
    gaps.append("Dracénie : seules les lignes régulières TEDbus publiées en GTFS sont représentées.")
    nl = meta["sources"]["flux"].get("non_localises") or {}
    if nl:
        top = sorted(nl.items(), key=lambda kv: -kv[1])[:3]
        gaps.append(f"Flux domicile-travail vers l'étranger hors Monaco non cartographiés : "
                    f"{sum(nl.values())} actifs (dont " + ", ".join(f"{k} {v}" for k, v in top) + ").")
    write_json(meta, "meta.json")

    total = sum(p.stat().st_size for p in DATA_DIR.iterdir() if p.is_file()) / 1e6
    log(f"taille totale de data/ : {total:.2f} Mo")
    if total > MAX_TOTAL_MB:
        log(f"ERREUR : data/ dépasse {MAX_TOTAL_MB} Mo")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
