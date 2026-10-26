# Sources de données

Règle : une donnée introuvable est **signalée**, jamais estimée. Les millésimes et URL
exactes de chaque génération sont enregistrés dans [`data/meta.json`](data/meta.json).

## Champs normalisés (couches trafic)

| Champ | Contenu |
|---|---|
| `tmja` | Trafic moyen journalier, tous véhicules, deux sens (véh./jour) |
| `annee` | Année de la mesure |
| `source` | Producteur et jeu de données |
| `type_comptage` | Permanent, temporaire, tournant… selon la source |
| `route`, `pl_pct`, `note` | Numéro de route, part de poids lourds (%), remarque |

## 1. Routes départementales des Alpes-Maritimes (CD06)

- **Comptages temporaires** : [data.gouv.fr](https://www.data.gouv.fr/datasets/comptage-vehicules-reseau-routier-departemental-des-alpes-maritimes-temporaires)
  (moissonné depuis DataSud), GeoPackage, comptages depuis 2004, **Licence Ouverte 2.0**.
  Valeur `tmj_tv` : TMJ mesuré **sur une semaine**, non annualisé (signalé dans les popups).
- **Comptages permanents** : [data.gouv.fr](https://www.data.gouv.fr/datasets/comptage-vehicules-reseau-routier-departemental-des-alpes-maritimes-permanents),
  GeoPackage, colonnes `tmja_AAAA` par année, **Licence Ouverte 2.0**. Pour chaque station,
  l'année la plus récente disponible est retenue.
- **Un comptage par section** : deux comptages sur la même route à moins de 150 m sont
  considérés comme la même section ; on garde le plus récent (à égalité, le permanent).
- **Raccrochage aux tronçons** : les comptages CD06 sont des points. Chacun est projeté sur
  la route OSM de même numéro (`D`/`M` + numéro, à moins de 60 m) ; le tronçon dessiné
  s'étend jusqu'à mi-distance du comptage voisin, au plus 1,5 km de chaque côté. Les points
  non raccrochés restent visibles dans la couche « Points de comptage » (cerclés de rouge).
  Filaire : © contributeurs OpenStreetMap, **ODbL**, via l'API Overpass.

## 2. Réseau routier national (DGITM)

- [TMJA sur le réseau routier national](https://www.data.gouv.fr/datasets/trafic-moyen-journalier-annuel-sur-le-reseau-routier-national),
  Ministère de la Transition écologique, **Licence Ouverte**. Dernier millésime publié : **2024**
  (`TMJA_RRNc_2024`, shapefile de sections). Le millésime le plus récent est sélectionné
  automatiquement.
- **Autoroutes concédées (A8 Escota)** : pas de jeu ouvert propre à Escota/Vinci. Le fichier
  TMJA comporte un indicateur `concessionPr` ; les sections concédées présentes y sont
  affichées avec la mention « section concédée ». Si aucune n'est présente, la légende
  indique leur exclusion.

## 3. Routes départementales du Var (CD83)

- [Comptages routiers sur le réseau départemental du Var 2017 et 2021](https://www.datasud.fr/explorer/fr/jeux-de-donnees/comptages-routiers-reseau-departemental-var-2017/info),
  Département du Var via DataSud, **Licence Ouverte 2.0**. Seule la couche **2017** est
  exploitable (WFS / shapefile, champs `MJA_2017`, `MJA_2016`) ; 2021 n'existe qu'en PDF.
- **Lacune signalée sur la carte** : données anciennes, aucun jeu ouvert plus récent trouvé
  sur data.gouv.fr ni sur DataSud.

## 4. Flux domicile-travail (INSEE)

- [Mobilités professionnelles en 2023 : déplacements domicile - lieu de travail](https://www.insee.fr/fr/statistiques/8998300),
  recensement de la population, base flux de mobilité, CSV (ensemble des flux).
  Réutilisation libre avec mention de la source (conditions générales de l'INSEE,
  compatibles Licence Ouverte). Repli automatique sur 2022 si 2023 est indisponible.
- Filtre : origine **ou** destination dans le périmètre. Les flux internes à une commune
  alimentent les fiches communales, pas les lignes.
- Lignes conservées : flux ≥ 10 actifs, et **tous** les flux du Pays de Fayence. L'INSEE
  précise que les flux inférieurs à 200 ne sont que des ordres de grandeur.
- Lieux de travail non localisables (étranger hors Monaco) : listés dans les avertissements,
  non cartographiés. Monaco est placé à son centre géographique.

## 5. Transports en commun (GTFS, transport.data.gouv.fr)

| Réseau | Jeu | Producteur |
|---|---|---|
| Zou! Train (TER) | `trains-zou-en-provence-alpes-cote-dazur` | Région Sud |
| Zou! Express | `lignes-des-reseaux-transport-zou-provence-alpes-cote-d-azur-express-3-3` | Région Sud |
| Zou! Proximité | `lignes-des-reseaux-transport-zou-provence-alpes-cote-d-azur-proximite-3-3` | Région Sud |
| Lignes d'Azur | `export-quotidien-au-format-gtfs-du-reseau-de-transport-lignes-d-azur` | Métropole Nice Côte d'Azur |
| Palm Bus | `horaires-theoriques-et-temps-reel-gtfs-gtfs-rt-du-reseau-palmbus-cannes-pays-de-lerins` | CA Cannes Pays de Lérins |
| Envibus | `arrets-horaires-et-parcours-theoriques-des-bus-du-reseau-des-transports-publics-envibus` | CA Sophia Antipolis |
| Sillages | `lignes-regulieres-de-transports-sillages-en-pays-de-grasse-urbain-et-scolaire` | CA du Pays de Grasse |
| Zest | `horaires-reseau-zest` | CA de la Riviera Française |
| Le Bus | `reseau-transport-urbain-le-bus` | CA Estérel Côte d'Azur Agglomération |
| TEDbus | `reseau-tedbus-lignes-regulieres-dracenie-provence-verdon-agglomeration` | CA Dracénie Provence Verdon |

- Licence : celle indiquée par chaque jeu (reprise dans `data/meta.json` et sur la carte).
- **Pays de Fayence** : aucun réseau local publié en GTFS ; desserte par les lignes Zou!.
- Le réseau scolaire Zou! n'est pas représenté (hors offre régulière).
- **Fréquence** : calculée pour un jour de référence par réseau (le mardi des 8 semaines à
  venir qui compte le plus de courses, dans la validité du GTFS) : courses par jour (tous
  sens), départs dans le sens le plus desservi, départs et intervalle moyen entre 7 h et 9 h.
- Tracé : `shapes.txt` du parcours le plus fréquent de la ligne, à défaut la suite des arrêts.
  Seules les lignes ayant au moins un arrêt dans le périmètre sont conservées.

## 6. Communes

- [geo.api.gouv.fr](https://geo.api.gouv.fr) (données IGN Admin Express / INSEE COG),
  **Licence Ouverte** : contours, codes INSEE, EPCI, population.

## Fond de carte

- Tuiles © contributeurs OpenStreetMap (**ODbL**), tile.openstreetmap.org.
- MapLibre GL JS 4.7.1 (BSD-3-Clause), embarqué dans `site/vendor/`.
