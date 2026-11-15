// EarthScape console: shared chart helpers, notifications, sidebar.
(function () {
  "use strict";

  var C = { green: "#16a34a", green2: "#22c55e", forest: "#0b3d2e", lime: "#84cc16", mint: "rgba(34,197,94,.14)",
            pink: "#db2777", amber: "#d97706", blue: "#2563eb", violet: "#7c3aed", teal: "#0d9488", grid: "rgba(15,42,31,.06)" };
  var PALETTE = [C.green, C.blue, C.amber, C.violet, C.teal, C.pink, C.forest, C.lime];
  window.ES = { colors: C, palette: PALETTE };

  if (window.Chart) {
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = "#6f8a7c";
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.tooltip.backgroundColor = "#0b3d2e";
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation.duration = 600;
  }

  ES.data = function (id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  };

  ES.gradient = function (ctx, color) {
    var g = ctx.createLinearGradient(0, 0, 0, ctx.canvas.clientHeight || 300);
    g.addColorStop(0, color.replace("rgb(", "rgba(").replace(")", ",.28)"));
    g.addColorStop(1, "rgba(255,255,255,0)");
    return g;
  };

  ES.axes = function (yTitle, xTitle) {
    return {
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 },
           title: { display: !!xTitle, text: xTitle } },
      y: { grid: { color: C.grid }, title: { display: !!yTitle, text: yTitle } }
    };
  };

  ES.line = function (id, labels, datasets, opts) {
    var el = document.getElementById(id);
    if (!el || !window.Chart) return null;
    datasets.forEach(function (d, i) {
      d.borderColor = d.borderColor || PALETTE[i % PALETTE.length];
      d.borderWidth = d.borderWidth || 2.2;
      d.pointRadius = d.pointRadius === undefined ? 0 : d.pointRadius;
      d.pointHoverRadius = 4;
      d.tension = d.tension === undefined ? 0.3 : d.tension;
      if (d.fill === true) {
        var g = el.getContext("2d").createLinearGradient(0, 0, 0, el.clientHeight || 300);
        g.addColorStop(0, "rgba(34,197,94,.22)"); g.addColorStop(1, "rgba(34,197,94,0)");
        d.backgroundColor = g; d.fill = "origin";
      }
    });
    return new Chart(el, { type: "line", data: { labels: labels, datasets: datasets },
      options: Object.assign({ interaction: { mode: "index", intersect: false }, scales: ES.axes(opts && opts.y, opts && opts.x),
                               plugins: { legend: { display: datasets.length > 1, position: "bottom" } } }, (opts && opts.extra) || {}) });
  };

  ES.bar = function (id, labels, datasets, opts) {
    var el = document.getElementById(id);
    if (!el || !window.Chart) return null;
    datasets.forEach(function (d, i) {
      d.backgroundColor = d.backgroundColor || PALETTE[i % PALETTE.length];
      d.borderRadius = 6; d.maxBarThickness = 38;
    });
    return new Chart(el, { type: "bar", data: { labels: labels, datasets: datasets },
      options: Object.assign({ indexAxis: (opts && opts.horizontal) ? "y" : "x", scales: ES.axes(opts && opts.y, opts && opts.x),
                               plugins: { legend: { display: datasets.length > 1, position: "bottom" } } }, (opts && opts.extra) || {}) });
  };

  ES.scatter = function (id, points, opts) {
    var el = document.getElementById(id);
    if (!el || !window.Chart) return null;
    var ds = [{ label: (opts && opts.label) || "points", data: points, backgroundColor: "rgba(22,163,74,.55)", pointRadius: 4 }];
    if (opts && opts.diagonal) {
      ds.push({ type: "line", label: "perfect prediction", data: opts.diagonal, borderColor: C.pink, borderDash: [6, 5],
                pointRadius: 0, borderWidth: 1.5 });
    }
    return new Chart(el, { type: "scatter", data: { datasets: ds },
      options: { scales: { x: { grid: { color: C.grid }, title: { display: true, text: opts && opts.x } },
                           y: { grid: { color: C.grid }, title: { display: true, text: opts && opts.y } } },
                 plugins: { legend: { position: "bottom" } } } });
  };

  // Choropleth world map (Plotly, ISO-3 codes)
  ES.map = function (id, iso3, values, names, opts) {
    var el = document.getElementById(id);
    if (!el || !window.Plotly) { if (el) el.innerHTML = '<div class="empty"><b>Map unavailable</b>Needs an internet connection to load the map library.</div>'; return; }
    opts = opts || {};
    Plotly.newPlot(el, [{
      type: "choropleth", locationmode: "ISO-3", locations: iso3, z: values, text: names,
      colorscale: opts.colorscale || [[0, "#eff6ff"], [0.35, "#fef9c3"], [0.6, "#fb923c"], [0.8, "#dc2626"], [1, "#7f1d1d"]],
      zmid: opts.zmid, zmin: opts.zmin, zmax: opts.zmax,
      marker: { line: { color: "#ffffff", width: 0.4 } },
      colorbar: { title: { text: opts.unit || "" }, thickness: 12, len: 0.75, outlinewidth: 0 },
      hovertemplate: "<b>%{text}</b><br>" + (opts.label || "value") + ": %{z}<extra></extra>"
    }], {
      margin: { l: 0, r: 0, t: 0, b: 0 }, paper_bgcolor: "rgba(0,0,0,0)",
      geo: { showframe: false, showcoastlines: false, projection: { type: "natural earth" },
             bgcolor: "rgba(0,0,0,0)", showocean: true, oceancolor: "#f3f8f2", landcolor: "#e7efe6", lakecolor: "#f3f8f2" },
      font: { family: "Inter, sans-serif", color: "#3d5a4c" }
    }, { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["select2d", "lasso2d"],
         topojsonURL: "https://cdn.jsdelivr.net/npm/plotly.js@2.35.2/dist/topojson/" });
  };

  // ---- UI: sidebar, dropdowns, notification polling ----
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-toggle]");
    if (t) {
      e.preventDefault();
      var target = document.getElementById(t.getAttribute("data-toggle"));
      document.querySelectorAll(".es-pop.open").forEach(function (p) { if (p !== target) p.classList.remove("open"); });
      if (target) target.classList.toggle("open");
      return;
    }
    if (!e.target.closest(".es-pop")) document.querySelectorAll(".es-pop.open").forEach(function (p) { p.classList.remove("open"); });
  });
  var menu = document.getElementById("es-menu");
  if (menu) menu.addEventListener("click", function () { document.querySelector(".es-side").classList.toggle("open"); });

  function poll() {
    fetch("/climatechanges/api/alerts/unread/", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        var dot = document.getElementById("es-bell-count");
        var side = document.getElementById("es-side-count");
        [dot, side].forEach(function (el) { if (el) { el.textContent = d.count; el.style.display = d.count ? "" : "none"; } });
      }).catch(function () {});
  }
  setInterval(poll, 60000);

  // confirm dangerous buttons
  document.addEventListener("submit", function (e) {
    var b = e.submitter;
    if (b && b.dataset.confirm && !window.confirm(b.dataset.confirm)) e.preventDefault();
  });
})();
