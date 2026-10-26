"""Périmètre d'étude et références des sources.

Toutes les URL de fichiers sont résolues dynamiquement via les API des portails
(data.gouv.fr, transport.data.gouv.fr, INSEE) afin de suivre les nouveaux
millésimes ; seules les adresses d'API et les identifiants de jeux sont figés ici.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"

# Projection métrique pour les calculs (Lambert 93).
CRS_METRIC = "EPSG:2154"
CRS_WGS84 = "EPSG:4326"

# --- Périmètre -------------------------------------------------------------

# Var : EPCI retenus en entier.
EPCI_VAR = {
    "200004802": "CC Pays de Fayence",
    "200035319": "CA Estérel Côte d'Azur Agglomération",
    "248300493": "CA Dracénie Provence Verdon Agglomération",
}

# Alpes-Maritimes : EPCI du littoral et du moyen-pays, vallées alpines exclues
# commune par commune ci-dessous. La CC Alpes d'Azur (200039931) est exclue.
EPCI_AM = {
    "200039915": "CA Cannes Pays de Lérins",
    "240600585": "CA Sophia Antipolis",
    "200039857": "CA du Pays de Grasse",
    "200030195": "Métropole Nice Côte d'Azur",
    "240600551": "CA de la Riviera Française",
    "240600593": "CC du Pays des Paillons",
}

EXCLUDED_COMMUNES = {
    # Roya
    "06023": "Breil-sur-Roya", "06062": "Fontan", "06132": "Saorge",
    "06163": "Tende", "06162": "La Brigue",
    # Bévéra
    "06136": "Sospel", "06086": "Moulinet",
    # Vésubie
    "06151": "Utelle", "06055": "Duranus", "06074": "Lantosque",
    "06103": "Roquebillière", "06013": "Belvédère", "06020": "La Bollène-Vésubie",
    "06156": "Venanson", "06127": "Saint-Martin-Vésubie",
    # Tinée
    "06009": "Bairols", "06042": "Clans", "06072": "Ilonse", "06073": "Isola",
    "06080": "Marie", "06102": "Rimplas", "06110": "Roubion", "06111": "Roure",
    "06119": "Saint-Dalmas-le-Selvage", "06120": "Saint-Étienne-de-Tinée",
    "06129": "Saint-Sauveur-sur-Tinée", "06153": "Valdeblore", "06144": "La Tour",
    "06146": "Tournefort",
    # Haut-pays grassois
    "06002": "Amirat", "06003": "Andon", "06024": "Briançonnet", "06028": "Caille",
    "06045": "Collongues", "06058": "Escragnolles", "06063": "Gars", "06081": "Le Mas",
    "06087": "Les Mujouls", "06116": "Saint-Auban", "06134": "Séranon",
    "06154": "Valderoure",
    # Haut-pays de la CASA
    "06070": "Gréolières", "06041": "Cipières", "06037": "Caussols",
    "06050": "Coursegoules", "06017": "Bézaudun-les-Alpes", "06022": "Bouyon",
    "06047": "Conségudes", "06061": "Les Ferres", "06107": "La Roque-en-Provence",
}

# Zoom détaillé : Pays de Fayence (= CC Pays de Fayence).
FOCUS_EPCI = "200004802"
FOCUS_NAME = "Pays de Fayence"

GEO_API = "https://geo.api.gouv.fr"

# --- Trafic routier --------------------------------------------------------

DATAGOUV_API = "https://www.data.gouv.fr/api/1"
CD06_TEMP_SLUG = "comptage-vehicules-reseau-routier-departemental-des-alpes-maritimes-temporaires"
CD06_PERM_SLUG = "comptage-vehicules-reseau-routier-departemental-des-alpes-maritimes-permanents"
RRN_SLUG = "trafic-moyen-journalier-annuel-sur-le-reseau-routier-national"

# Var : seul jeu ouvert trouvé (DataSud, comptages 2017). Service WFS + archive SHP.
CD83_WFS = (
    "https://www.datasud.fr/geoserver/conseil-departemental-du-var/ows"
    "?service=WFS&version=1.0.0&request=GetFeature"
    "&typeName=conseil-departemental-du-var:cd83_comptage_routier_2017_shp.zip"
    "&outputFormat=application/json&srsName=EPSG:4326"
)
CD83_SHP = "https://www.datasud.fr/fr/dataset/datasets/245/resource/321/download/"
CD83_PAGE = "https://www.datasud.fr/explorer/fr/jeux-de-donnees/comptages-routiers-reseau-departemental-var-2017/info"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Raccrochage des comptages ponctuels CD06 au filaire OSM.
SNAP_MAX_DIST_M = 60          # distance max point de comptage -> route OSM de même numéro
SECTION_HALF_LENGTH_M = 1500  # demi-longueur max du tronçon représenté
SAME_SECTION_DIST_M = 150     # deux comptages plus proches = même section
HEAT_SAMPLE_STEP_M = 400      # pas d'échantillonnage des tronçons pour la heatmap

# --- Flux domicile-travail -------------------------------------------------

INSEE_FLOWS_PAGES = [
    # Du plus récent au plus ancien : le premier qui répond est utilisé.
    ("2023", "https://www.insee.fr/fr/statistiques/8998300"),
    ("2022", "https://www.insee.fr/fr/statistiques/8582949"),
]
FLOWS_MIN_KEEP = 10  # flux conservés dans le GeoJSON (hors Pays de Fayence : tous conservés)
MONACO_CENTRE = (7.4206, 43.7375)

# --- Transports en commun --------------------------------------------------

TRANSPORT_API = "https://transport.data.gouv.fr/api/datasets"
GTFS_FEEDS = [
    # (slug transport.data.gouv.fr, nom du réseau, couleur)
    ("trains-zou-en-provence-alpes-cote-dazur", "Zou! Train (TER)", "#1d3557"),
    ("lignes-des-reseaux-transport-zou-provence-alpes-cote-d-azur-express-3-3", "Zou! Express", "#e63946"),
    ("lignes-des-reseaux-transport-zou-provence-alpes-cote-d-azur-proximite-3-3", "Zou! Proximité", "#f4a261"),
    ("export-quotidien-au-format-gtfs-du-reseau-de-transport-lignes-d-azur", "Lignes d'Azur", "#0077b6"),
    ("horaires-theoriques-et-temps-reel-gtfs-gtfs-rt-du-reseau-palmbus-cannes-pays-de-lerins", "Palm Bus", "#2a9d8f"),
    ("arrets-horaires-et-parcours-theoriques-des-bus-du-reseau-des-transports-publics-envibus", "Envibus", "#8338ec"),
    ("lignes-regulieres-de-transports-sillages-en-pays-de-grasse-urbain-et-scolaire", "Sillages", "#c9184a"),
    ("horaires-reseau-zest", "Zest", "#6a994e"),
    ("reseau-transport-urbain-le-bus", "Le Bus (Estérel Côte d'Azur)", "#ff006e"),
    ("reseau-tedbus-lignes-regulieres-dracenie-provence-verdon-agglomeration", "TEDbus", "#7f5539"),
]
PEAK_WINDOW = ("07:00:00", "09:00:00")
