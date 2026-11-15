/* Live knowledge-base updater for the Data Explorer.
   Source: global-warming.org's free, keyless, CORS-enabled API, which
   republishes NOAA Mauna Loa CO2 (co2-api) and NASA GISTEMP global
   temperature anomaly (temperature-api) data.
   Everything on this page still WORKS with the baked-in 2025 figures if
   the fetch fails or the visitor is offline, this script only upgrades
   the page when live data is actually available, it never blocks or
   breaks anything. Nothing here is cached by the service worker (see
   sw.js), so it's genuinely re-checked on every visit. */
(function () {
  "use strict";

  var liveMount = document.getElementById("live-readings");
  var heroCo2 = document.getElementById("hero-co2-value");
  var heroCo2Label = document.getElementById("hero-co2-label");
  var heroCo2Badge = document.getElementById("hero-co2-badge");
  if (!liveMount && !heroCo2) return; // not on the Data Explorer page

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fmtDate(y, m, d) {
    var dt = new Date(Date.UTC(y, m - 1, d || 1));
    return dt.toLocaleDateString(undefined, { year: "numeric", month: "short", day: d ? "numeric" : undefined });
  }

  function monthName(monthIndex) {
    return ["January","February","March","April","May","June","July","August","September","October","November","December"][monthIndex];
  }

  var state = { co2: null, temp: null };

  function renderLivePanel() {
    if (!liveMount) return;
    if (!state.co2 && !state.temp) {
      liveMount.innerHTML = '<p class="chart-meta">Live figures are loading&hellip;</p>';
      return;
    }
    var rows = "";
    if (state.co2) {
      rows +=
        '<div class="live-row">' +
          '<span class="live-dot" aria-hidden="true"></span>' +
          '<div><div class="live-label">CO2, Mauna Loa, right now</div>' +
          '<div class="live-value">' + state.co2.ppm.toFixed(2) + ' ppm</div>' +
          '<div class="live-meta">Reading for ' + escapeHtml(state.co2.dateLabel) + '</div></div>' +
        '</div>';
    }
    if (state.temp) {
      rows +=
        '<div class="live-row">' +
          '<span class="live-dot" aria-hidden="true"></span>' +
          '<div><div class="live-label">Global temperature anomaly, latest month</div>' +
          '<div class="live-value">' + (state.temp.anomaly >= 0 ? "+" : "") + state.temp.anomaly.toFixed(2) + '\u00B0C</div>' +
          '<div class="live-meta">' + escapeHtml(state.temp.dateLabel) + ' &middot; NASA GISTEMP, vs. the 1951\u20131980 average (a different baseline to the NOAA chart above, so don\u2019t subtract one from the other)</div></div>' +
        '</div>';
    }
    liveMount.innerHTML = rows;
  }

  function renderError() {
    if (!liveMount) return;
    liveMount.innerHTML = '<p class="chart-meta">Couldn\u2019t reach the live data feed right now, the figures further up this page are the most recent confirmed annual numbers instead.</p>';
  }

  function updateHeroReadout() {
    if (!heroCo2 || !state.co2) return;
    var suffix = heroCo2.getAttribute("data-suffix") || "";
    heroCo2.textContent = state.co2.ppm.toFixed(1) + suffix;
    if (heroCo2Label) {
      heroCo2Label.textContent = "CO2, Mauna Loa, right now";
    }
    if (heroCo2Badge) {
      heroCo2Badge.hidden = false;
      heroCo2Badge.textContent = "Live \u00B7 " + state.co2.dateLabel;
    }
  }

  function updateCo2Chart() {
    if (!state.co2 || typeof Chart === "undefined" || typeof Chart.getChart !== "function") return;
    var canvas = document.getElementById("chart-co2");
    if (!canvas) return;
    var chart = Chart.getChart(canvas);
    if (!chart) return;
    var ds = chart.data.datasets[0];
    var lastLabel = chart.data.labels[chart.data.labels.length - 1];
    var liveLabel = "Live (" + state.co2.dateLabel + ")";
    if (lastLabel === liveLabel) return; // already added
    chart.data.labels.push(liveLabel);
    ds.data.push(Number(state.co2.ppm.toFixed(2)));
    if (!ds.pointBackgroundColor || typeof ds.pointBackgroundColor === "string") {
      var colors = ds.data.map(function () { return "#D9691A"; });
      colors[colors.length - 1] = "#C8432F";
      ds.pointBackgroundColor = colors;
    }
    var radii = ds.data.map(function () { return 3.5; });
    radii[radii.length - 1] = 6;
    ds.pointRadius = radii;
    chart.update();
  }

  function loadCo2() {
    return fetch("https://global-warming.org/api/co2-api")
      .then(function (r) { if (!r.ok) throw new Error("co2 fetch failed"); return r.json(); })
      .then(function (data) {
        var rows = data && data.co2;
        if (!rows || !rows.length) throw new Error("no co2 rows");
        var last = rows[rows.length - 1];
        var ppm = parseFloat(last.trend);
        if (!isFinite(ppm)) throw new Error("bad co2 value");
        state.co2 = {
          ppm: ppm,
          dateLabel: fmtDate(parseInt(last.year, 10), parseInt(last.month, 10), parseInt(last.day, 10)),
        };
      });
  }

  function loadTemperature() {
    return fetch("https://global-warming.org/api/temperature-api")
      .then(function (r) { if (!r.ok) throw new Error("temp fetch failed"); return r.json(); })
      .then(function (data) {
        var rows = data && data.result;
        if (!rows || !rows.length) throw new Error("no temp rows");
        var last = rows[rows.length - 1];
        var anomaly = parseFloat(last.station);
        var time = parseFloat(last.time);
        if (!isFinite(anomaly) || !isFinite(time)) throw new Error("bad temp value");
        var year = Math.floor(time);
        var monthIdx = Math.round((time - year) * 12);
        state.temp = {
          anomaly: anomaly,
          dateLabel: monthName(Math.min(11, Math.max(0, monthIdx))) + " " + year,
        };
      });
  }

  renderLivePanel();
  Promise.allSettled
    ? Promise.allSettled([loadCo2(), loadTemperature()]).then(function () {
        renderLivePanel();
        updateHeroReadout();
        updateCo2Chart();
        if (!state.co2 && !state.temp) renderError();
      })
    : Promise.all([loadCo2().catch(function(){}), loadTemperature().catch(function(){})]).then(function () {
        renderLivePanel();
        updateHeroReadout();
        updateCo2Chart();
        if (!state.co2 && !state.temp) renderError();
      });
})();
