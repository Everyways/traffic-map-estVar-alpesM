/* Carte des flux routiers Est Var – Alpes-Maritimes. Données statiques dans data/. */
(function () {
  "use strict";

  const fmt = new Intl.NumberFormat("fr-FR");
  const n = (v) => (v === null || v === undefined ? "–" : fmt.format(v));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (sel) => document.querySelector(sel);

  const FLOW_STEPS = [10, 25, 50, 100, 200, 500, 1000, 2000];
  const TMJA_STOPS = [
    [0, "#ffffb2"], [5000, "#fed976"], [10000, "#feb24c"], [20000, "#fd8d3c"],
    [40000, "#f03b20"], [80000, "#bd0026"], [120000, "#67001f"],
  ];
  const HOME = { bounds: [[6.25, 43.38], [7.58, 43.92]] };

  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256, maxzoom: 19,
          attribution: '© <a href="https://www.openstreetmap.org/copyright">contributeurs OpenStreetMap</a>',
        },
      },
      layers: [{ id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -0.6, "raster-opacity": 0.9 } }],
    },
    bounds: HOME.bounds,
    maxZoom: 17,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

  const getJSON = (f) => fetch("data/" + f).then((r) => {
    if (!r.ok) throw new Error(f + " : " + r.status);
    return r.json();
  });

  Promise.all([
    "communes.geojson", "traffic_lines.geojson", "traffic_points.geojson", "traffic_heat.geojson",
    "flows.geojson", "transit.geojson", "communes_stats.json", "focus.json", "meta.json",
  ].map(getJSON)).then(([communes, lines, points, heat, flows, transit, stats, focus, meta]) => {
    const ready = () => init({ communes, lines, points, heat, flows, transit, stats, focus, meta });
    if (map.loaded()) ready(); else map.on("load", ready);
  }).catch((e) => {
    $("#warning").innerHTML = "Données introuvables : " + esc(e.message) +
      ". Les fichiers de data/ n'ont peut-être pas encore été générés (voir README).";
  });

  function tmjaColor() {
    const e = ["interpolate", ["linear"], ["get", "tmja"]];
    TMJA_STOPS.forEach(([v, c]) => e.push(v, c));
    return e;
  }

  function init(d) {
    const focusCodes = new Set(d.communes.features.filter((f) => f.properties.focus).map((f) => f.properties.code));
    const focusBounds = bbox(d.communes.features.filter((f) => f.properties.focus));

    map.addSource("communes", { type: "geojson", data: d.communes, promoteId: "code" });
    map.addSource("lines", { type: "geojson", data: d.lines });
    map.addSource("points", { type: "geojson", data: d.points });
    map.addSource("heat", { type: "geojson", data: d.heat });
    map.addSource("flows", { type: "geojson", data: d.flows });
    map.addSource("transit", { type: "geojson", data: d.transit });

    // Communes
    map.addLayer({ id: "communes-fill", type: "fill", source: "communes",
      paint: { "fill-color": ["case", ["get", "focus"], "#ef8a17", "#000"],
               "fill-opacity": ["case", ["boolean", ["feature-state", "sel"], false], 0.18, ["get", "focus"], 0.06, 0.0] } });
    map.addLayer({ id: "communes-line", type: "line", source: "communes",
      paint: { "line-color": ["case", ["get", "focus"], "#ef8a17", "#6e7781"],
               "line-width": ["case", ["get", "focus"], 2, 0.7], "line-opacity": 0.8 } });
    // Heatmap de densité
    map.addLayer({ id: "heat", type: "heatmap", source: "heat", layout: { visibility: "none" },
      paint: {
        "heatmap-weight": ["interpolate", ["linear"], ["get", "w"], 0, 0, 80000, 1],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 8, 0.6, 13, 2],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 8, 6, 13, 24],
        "heatmap-opacity": 0.75,
      } });
    // Flux domicile-travail
    map.addLayer({ id: "flows", type: "line", source: "flows", layout: { visibility: "none", "line-cap": "round" },
      paint: {
        "line-color": ["case", ["get", "f"], "#ef8a17", "#3a86ff"],
        "line-width": ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 3, 0.5, 30, 4, 100, 12],
        "line-opacity": 0.55,
      } });
    // Transports en commun
    map.addLayer({ id: "transit", type: "line", source: "transit", layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["get", "couleur"],
        "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1.2, 14, 3.5],
        "line-opacity": 0.85,
        "line-dasharray": ["literal", [2, 1]],
      } });
    // Trafic par tronçon
    map.addLayer({ id: "traffic", type: "line", source: "lines", layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": tmjaColor(),
        "line-width": ["interpolate", ["linear"], ["zoom"],
          8, ["interpolate", ["linear"], ["get", "tmja"], 0, 1, 20000, 2.5, 100000, 6],
          13, ["interpolate", ["linear"], ["get", "tmja"], 0, 2, 20000, 6, 100000, 14]],
        "line-opacity": 0.9,
      } });
    map.addLayer({ id: "points", type: "circle", source: "points", layout: { visibility: "none" },
      paint: { "circle-radius": 4, "circle-color": tmjaColor(),
               "circle-stroke-color": ["case", ["get", "raccroche"], "#333", "#d1495b"], "circle-stroke-width": 1.2 } });

    setupToggles(d);
    setupFlows(focusCodes);
    setupNetworks(d.transit);
    renderLegend(d.meta);
    renderWarnings(d.meta);
    renderSources(d.meta);
    renderFocus(d.focus);
    setupPopups(d.stats);
    setupPanel();

    $("#zoom-focus").onclick = () => {
      map.fitBounds(focusBounds, { padding: 40 });
      $("#flow-focus-only").checked = true;
      setVisible("flows", true);
      applyFlowFilter(focusCodes);
    };
    $("#zoom-all").onclick = () => {
      map.fitBounds(HOME.bounds, { padding: 20 });
      $("#flow-focus-only").checked = false;
      applyFlowFilter(focusCodes);
    };
  }

  function bbox(features) {
    let b = [180, 90, -180, -90];
    const walk = (c) => (typeof c[0] === "number"
      ? (b = [Math.min(b[0], c[0]), Math.min(b[1], c[1]), Math.max(b[2], c[0]), Math.max(b[3], c[1])])
      : c.forEach(walk));
    features.forEach((f) => walk(f.geometry.coordinates));
    return [[b[0], b[1]], [b[2], b[3]]];
  }

  // --- Couches -------------------------------------------------------------------------------

  const LAYER_GROUPS = { communes: ["communes-fill", "communes-line"] };
  function setVisible(layer, on) {
    (LAYER_GROUPS[layer] || [layer]).forEach((id) => map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    const box = document.querySelector(`input[data-layer="${layer}"]`);
    if (box) box.checked = on;
    if (layer === "flows") $("#flows-controls").hidden = !on;
    if (layer === "transit") $("#transit-controls").hidden = !on;
  }

  function setupToggles() {
    document.querySelectorAll("input[data-layer]").forEach((box) => {
      box.addEventListener("change", () => setVisible(box.dataset.layer, box.checked));
    });
  }

  function applyFlowFilter(focusCodes) {
    const thr = FLOW_STEPS[+$("#flow-threshold").value];
    $("#flow-threshold-value").textContent = "≥ " + n(thr);
    const focusAll = $("#flow-focus-all").checked;
    const focusOnly = $("#flow-focus-only").checked;
    const above = [">=", ["get", "v"], thr];
    const isFocus = ["==", ["get", "f"], true];
    let filter = focusAll ? ["any", above, isFocus] : above;
    if (focusOnly) filter = ["all", isFocus, focusAll ? true : above];
    map.setFilter("flows", filter);
  }

  function setupFlows(focusCodes) {
    ["#flow-threshold", "#flow-focus-all", "#flow-focus-only"].forEach((s) =>
      $(s).addEventListener("input", () => applyFlowFilter(focusCodes)));
    applyFlowFilter(focusCodes);
  }

  function setupNetworks(transit) {
    const nets = new Map();
    transit.features.forEach((f) => nets.set(f.properties.reseau, f.properties.couleur));
    const box = $("#networks");
    const active = new Set(nets.keys());
    [...nets.entries()].sort().forEach(([name, colour]) => {
      const l = document.createElement("label");
      l.innerHTML = `<input type="checkbox" checked> <span class="swatch" style="background:${esc(colour)}"></span>${esc(name)}`;
      l.querySelector("input").addEventListener("change", (e) => {
        e.target.checked ? active.add(name) : active.delete(name);
        map.setFilter("transit", ["in", ["get", "reseau"], ["literal", [...active]]]);
      });
      box.appendChild(l);
    });
    if (!nets.size) box.textContent = "Aucune ligne disponible.";
  }

  // --- Panneaux -----------------------------------------------------------------------------

  function renderLegend(meta) {
    const rows = TMJA_STOPS.map(([v, c], i) => {
      const next = TMJA_STOPS[i + 1];
      const label = next ? `${n(v)} – ${n(next[0])}` : `≥ ${n(v)}`;
      return `<div class="legend-row"><span class="swatch" style="background:${c}"></span>${label} véh./jour</div>`;
    }).join("");
    const conc = meta.sources.trafic.rrn.sections_concedees || 0;
    $("#legend").innerHTML = `
      <div class="legend-note"><b>Trafic</b> : couleur et épaisseur selon le TMJA (véhicules/jour, deux sens).</div>
      ${rows}
      <div class="legend-note">${conc
        ? `Autoroutes concédées (A8…) : ${conc} sections issues du fichier TMJA national.`
        : "Autoroutes concédées (A8 Escota) : aucune donnée ouverte, exclues de la carte."}</div>
      <div class="legend-note"><b>Flux domicile-travail</b> : épaisseur selon le nombre d'actifs
        (<span class="swatch" style="background:#3a86ff"></span>autres,
        <span class="swatch" style="background:#ef8a17"></span>Pays de Fayence).</div>
      <div class="legend-note"><b>Transports en commun</b> : tirets colorés par réseau ; fréquence dans la fenêtre au clic.</div>
      <div class="legend-note"><b>Points de comptage</b> : cerclés de rouge si non raccrochés à un tronçon.</div>`;
  }

  function renderWarnings(meta) {
    const items = (meta.lacunes || []).map((t) => `<li>${esc(t)}</li>`).join("");
    $("#warning").innerHTML = `<b>Trous de données</b> — aucune valeur n'est estimée :<ul>${items}</ul>`;
  }

  function renderSources(meta) {
    const s = meta.sources;
    const link = (u, t) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`;
    const t = s.trafic;
    const parts = [
      `${link(t.cd06_temporaires.url, "CD06 – comptages temporaires")} (${t.cd06_temporaires.annees.join("–")}), Licence Ouverte`,
      `${link(t.cd06_permanents.url, "CD06 – comptages permanents")}, Licence Ouverte`,
      `${link(t.rrn.url, "TMJA réseau routier national " + t.rrn.millesime)} (DGITM), Licence Ouverte`,
      `${link(t.cd83.url, "CD83 – comptages routiers " + t.cd83.millesime)} (DataSud), Licence Ouverte`,
      `${link(s.flux.url, "INSEE – mobilités professionnelles " + s.flux.millesime)}`,
      ...s.tc.filter((e) => e.statut === "ok").map((e) => `${link(e.url, "GTFS " + e.reseau)}${e.licence ? " (" + esc(e.licence) + ")" : ""}`),
      `Contours : ${link("https://geo.api.gouv.fr", "geo.api.gouv.fr")} (IGN / INSEE)`,
      `Fond et filaire routier : ${link("https://www.openstreetmap.org/copyright", "© contributeurs OpenStreetMap")} (ODbL)`,
    ];
    $("#sources").innerHTML = `<ul class="tags">${parts.map((p) => `<li>${p}</li>`).join("")}</ul>
      <p class="hint">Données générées le ${esc(meta.genere_le)}. Détail : DATA_SOURCES.md du dépôt.</p>`;
  }

  function bars(list) {
    if (!list || !list.length) return "<p class='hint'>Aucun flux.</p>";
    const max = list[0].flux || 1;
    return `<ul class="bars">${list.map((x) => `<li><i style="width:${(100 * x.flux / max).toFixed(0)}%"></i>
      <span>${esc(x.nom)}</span><b>${n(x.flux)}</b></li>`).join("")}</ul>`;
  }

  function kpi(v, label) { return `<div class="kpi"><b>${v}</b><span>${label}</span></div>`; }
  const pct = (a, b) => (b ? Math.round(100 * a / b) + " %" : "–");

  function renderFocus(f) {
    $("#focus-summary").innerHTML = `
      <div class="kpis">
        ${kpi(n(f.population), "habitants")}
        ${kpi(n(f.actifs), "actifs occupés résidents")}
        ${kpi(pct(f.travaillent_dans_territoire, f.actifs), "travaillent dans le Pays de Fayence")}
        ${kpi(n(f.travaillent_hors_territoire), "sortent du territoire chaque jour")}
        ${kpi(n(f.emplois), "emplois occupés")}
        ${kpi(n(f.entrants_exterieurs), "actifs entrant de l'extérieur")}
        ${kpi(n(f.tc_lignes.length), "lignes TC desservantes")}
        ${kpi(n(f.tc_courses), "courses TC/jour (jour de réf.)")}
      </div>
      <h3>Principales destinations hors territoire</h3>${bars(f.top_dest_ext)}
      <h3>Principales origines des entrants</h3>${bars(f.top_orig_ext)}
      <h3>Lignes TC</h3><p class="tags">${f.tc_lignes.map(esc).join(" · ") || "Aucune ligne GTFS."}</p>
      <h3>Comptages routiers</h3>${f.comptages.length ? `<ul class="bars">${f.comptages.slice(0, 10).map((c) =>
        `<li><span>${esc(c.route)} (${esc(c.commune)}, ${c.annee})</span><b>${n(c.tmja)}</b></li>`).join("")}</ul>`
        : "<p class='hint'>Aucun comptage ouvert.</p>"}
      <p class="hint">Communes : ${f.communes.map(esc).join(", ")}.</p>`;
  }

  function renderFiche(code, s) {
    $("#fiche-section").hidden = false;
    $("#fiche-title").textContent = s.nom;
    $("#fiche").innerHTML = `
      <div class="kpis">
        ${kpi(n(s.population), "habitants")}
        ${kpi(n(s.actifs), "actifs occupés résidents")}
        ${kpi(pct(s.sur_place, s.actifs), "travaillent dans la commune")}
        ${kpi(n(s.sortants), "sortants")}
        ${kpi(n(s.emplois), "emplois occupés")}
        ${kpi(n(s.entrants), "entrants")}
        ${kpi(n(s.tc_lignes.length), "lignes TC")}
        ${kpi(n(s.tc_courses), "courses TC/jour")}
      </div>
      <h3>Top 5 destinations</h3>${bars(s.top_dest)}
      <h3>Top 5 origines</h3>${bars(s.top_orig)}
      <h3>Lignes TC</h3><p class="tags">${s.tc_lignes.map(esc).join(" · ") || "Aucune ligne GTFS."}</p>
      <h3>Comptages routiers</h3>${s.comptages.length ? `<ul class="bars">${s.comptages.map((c) =>
        `<li><span>${esc(c.route)} (${c.annee})</span><b>${n(c.tmja)}</b></li>`).join("")}</ul>`
        : "<p class='hint'>Aucun comptage ouvert dans la commune.</p>"}
      <p class="hint">Code INSEE ${esc(code)} · flux INSEE, comptages et GTFS : voir sources.</p>`;
    $("#fiche-section").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // --- Popups ----------------------------------------------------------------------------------

  function row(k, v) { return v === null || v === undefined || v === "" ? "" : `<tr><td>${k}</td><td>${v}</td></tr>`; }

  function setupPopups(stats) {
    const popup = new maplibregl.Popup({ closeButton: true, maxWidth: "300px" });
    const order = ["traffic", "points", "transit", "flows", "communes-fill"];
    let selected = null;
    order.forEach((id) => {
      map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
    });
    map.on("click", (e) => {
      const layers = order.filter((id) => map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none");
      const hits = map.queryRenderedFeatures(e.point, { layers });
      if (!hits.length) return;
      hits.sort((a, b) => order.indexOf(a.layer.id) - order.indexOf(b.layer.id));
      const f = hits[0], p = f.properties;
      let html = "";
      if (f.layer.id === "traffic" || f.layer.id === "points") {
        html = `<h4>${esc(p.route)}</h4><table>
          ${row("TMJA", n(p.tmja) + " véh./jour")}${row("Année", p.annee)}
          ${row("Source", esc(p.source))}${row("Type", esc(p.type_comptage))}
          ${row("Poids lourds", p.pl_pct ? p.pl_pct + " %" : "")}${row("Note", esc(p.note))}</table>`;
      } else if (f.layer.id === "transit") {
        html = `<h4>${esc(p.reseau)} · ${esc(p.ligne)}</h4><table>
          ${row("Ligne", esc(p.nom))}${row("Mode", esc(p.mode))}
          ${row("Courses/jour", n(p.departs_total) + " (tous sens)")}
          ${row("Sens le plus desservi", p.departs_sens ? n(p.departs_sens) + " départs" : "")}
          ${row("Pointe 7h–9h", p.pointe !== null && p.pointe !== undefined ? n(p.pointe) + " départs" + (p.intervalle_pointe ? ` (≈ 1 toutes les ${p.intervalle_pointe} min)` : "") : "")}
          ${row("Jour de référence", esc(p.date_ref))}</table>`;
      } else if (f.layer.id === "flows") {
        html = `<h4>${esc(p.on)} → ${esc(p.dn)}</h4><table>
          ${row("Actifs", n(Math.round(p.v)))}
          ${row("Fiabilité", p.v < 200 ? "ordre de grandeur (< 200)" : "")}
          ${row("Source", "INSEE, mobilités professionnelles")}</table>`;
      } else {
        const code = p.code;
        if (selected) map.setFeatureState({ source: "communes", id: selected }, { sel: false });
        selected = code;
        map.setFeatureState({ source: "communes", id: code }, { sel: true });
        if (stats[code]) renderFiche(code, stats[code]);
        openPanel();
        html = `<h4>${esc(p.nom)}</h4><table>${row("EPCI", esc(p.epci_nom))}${row("Habitants", n(p.population))}</table>
          <p class="hint">Fiche détaillée dans le panneau.</p>`;
      }
      popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
    });
  }

  // --- Panneau mobile ---------------------------------------------------------------------------

  function openPanel() {
    $("#panel").classList.remove("collapsed");
    $("#panel-toggle").setAttribute("aria-expanded", "true");
  }

  function setupPanel() {
    const btn = $("#panel-toggle"), panel = $("#panel");
    if (window.matchMedia("(max-width: 720px)").matches) {
      panel.classList.add("collapsed");
      btn.setAttribute("aria-expanded", "false");
    }
    btn.onclick = () => {
      const collapsed = panel.classList.toggle("collapsed");
      btn.setAttribute("aria-expanded", String(!collapsed));
    };
  }
})();
