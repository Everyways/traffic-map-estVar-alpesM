# Flux routiers · Est Var & Alpes-Maritimes

Carte interactive des flux routiers de l'Est Var et du littoral et du moyen-pays des
Alpes-Maritimes, pour une étude d'optimisation des transports en commun : repérer les
axes chargés mal desservis.

**Site :** https://everyways.github.io/traffic-map-estVar-alpesM/

## Contenu de la carte

| Couche | Données |
|---|---|
| Trafic par tronçon | Lignes colorées et épaissies selon le TMJA (RD 06, réseau national, RD 83) |
| Densité de trafic | Heatmap des TMJA échantillonnés le long des tronçons |
| Points de comptage | Comptages CD06 (temporaires et permanents) |
| Flux domicile-travail | Lignes origine → destination entre communes (INSEE), seuil réglable |
| Transports en commun | Lignes GTFS colorées par réseau, fréquences en popup |
| Communes | Contours ; clic = fiche communale (actifs, flux, lignes TC, comptages) |

**Pays de Fayence** (9 communes de la CC) : bouton de zoom dédié, panneau de synthèse,
fiches communales, et tous ses flux domicile-travail affichés sans seuil.

Les trous de données sont signalés sur la carte : aucune valeur n'est estimée.

## Périmètre

- **Var** : CC Pays de Fayence, CA Estérel Côte d'Azur Agglomération, CA Dracénie Provence Verdon.
- **Alpes-Maritimes** : CA Cannes Pays de Lérins, CA Sophia Antipolis, CA du Pays de Grasse,
  Métropole Nice Côte d'Azur, CA de la Riviera Française, CC du Pays des Paillons,
  sans les vallées alpines (Roya, Bévéra, Vésubie, Tinée, CC Alpes d'Azur) ni le haut-pays
  grassois et de la CASA.

La liste exacte des communes exclues est dans [`scripts/config.py`](scripts/config.py).

## Sources

Détail, licences et millésimes : [`DATA_SOURCES.md`](DATA_SOURCES.md).

- Département des Alpes-Maritimes : comptages temporaires et permanents (data.gouv.fr / DataSud)
- DGITM : TMJA du réseau routier national (data.gouv.fr)
- Département du Var : comptages routiers 2017 (DataSud)
- INSEE : mobilités professionnelles (base flux domicile-lieu de travail)
- transport.data.gouv.fr : GTFS Zou!, Lignes d'Azur, Palm Bus, Envibus, Sillages, Zest, Le Bus, TEDbus
- geo.api.gouv.fr : contours et codes INSEE ; OpenStreetMap : fond de carte et filaire routier

## Régénérer les données

Les données sont pré-calculées et commitées dans `data/` ; le site ne télécharge aucune
donnée au runtime (seules les tuiles du fond OSM sont chargées).

**Via GitHub Actions** (méthode de référence) : onglet *Actions* → workflow **Données** →
*Run workflow*. Il régénère `data/`, le commite sur `main` puis redéploie le site.
Il se lance aussi à chaque modification de `scripts/` ou `requirements.txt`.

**En local** (Python 3.11+) :

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python scripts/build_all.py        # télécharge dans .cache/, écrit data/
python -m http.server -d _site 8000 # après avoir assemblé site/ + data/ (voir ci-dessous)
```

Pour prévisualiser : `mkdir -p _site && cp -r site/. _site/ && cp -r data _site/`.

Le build échoue si `data/` dépasse 5 Mo.

## Déploiement

GitHub Pages doit être activé avec la source **GitHub Actions**
(*Settings → Pages → Build and deployment → Source*). Le workflow **Pages** publie
`site/` et `data/` à chaque modification.

## Arborescence

```
scripts/   config.py (périmètre, sources) · perimeter.py · traffic.py · flows.py
           transit.py · stats.py · build_all.py · common.py
data/      GeoJSON et JSON générés (commités)
site/      index.html · app.js · style.css · vendor/ (MapLibre GL JS 4.7.1, BSD-3)
```
