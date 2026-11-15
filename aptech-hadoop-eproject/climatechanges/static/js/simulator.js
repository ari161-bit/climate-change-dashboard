/* Climate Simulator: drag the CO2 slider, watch the greenhouse effect
   happen. This is a deliberately simplified, illustrative model (not a
   forecast) so the physics stays honest at a glance:
     - Sunlight (yellow) reaches the surface and re-radiates as heat (red).
     - More CO2 molecules in the atmosphere layer = more heat rays get
       bounced back down instead of escaping to space.
     - The warming estimate uses the standard, real logarithmic CO2-forcing
       relationship, deltaT = TCR * log2(CO2 / 280), with TCR (Transient
       Climate Response) set to 1.8 degC, inside IPCC AR6's likely range.
       It is a genuine simplification of the real science, not invented
       from scratch, and the page says so. */
(function () {
  "use strict";
  var canvas = document.getElementById("sim-canvas");
  if (!canvas) return;

  var ctx = canvas.getContext("2d");
  var slider = document.getElementById("sim-co2-slider");
  var ppmReadout = document.getElementById("sim-ppm-readout");
  var ppmReadout2 = document.getElementById("sim-ppm-readout-2");
  var warmingReadout = document.getElementById("sim-warming-readout");
  var escapeReadout = document.getElementById("sim-escape-readout");
  var milestoneLabel = document.getElementById("sim-milestone-label");
  var presetBtns = document.querySelectorAll(".sim-preset");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var PRE_INDUSTRIAL = 280;
  var TCR = 1.8; // degC, transient climate response, IPCC AR6 likely-range estimate
  var MILESTONES = [
    { ppm: 280, label: "Pre-industrial (~1850)" },
    { ppm: 350, label: "1988: the \u201Csafe\u201D threshold many scientists point to" },
    { ppm: 427, label: "Today (2025 Mauna Loa annual mean)" },
    { ppm: 450, label: "A commonly cited 1.5\u00B0C-pathway ballpark" },
    { ppm: 560, label: "Double pre-industrial CO2" },
    { ppm: 800, label: "A high-emissions 2100 scenario" },
  ];

  function warmingFor(ppm) {
    return TCR * (Math.log(ppm / PRE_INDUSTRIAL) / Math.log(2));
  }

  function escapeFractionFor(ppm) {
    // Illustrative only: maps ppm to a 0-1 "how much heat still escapes"
    // figure purely so the visual has something to scale against. Not a
    // real radiative-transfer calculation.
    var extra = Math.max(0, ppm - PRE_INDUSTRIAL);
    var trapped = 1 - Math.exp(-extra / 550);
    return Math.max(0.08, 1 - trapped * 0.62);
  }

  function nearestMilestone(ppm) {
    var best = MILESTONES[0];
    var bestDist = Infinity;
    MILESTONES.forEach(function (m) {
      var d = Math.abs(m.ppm - ppm);
      if (d < bestDist) { bestDist = d; best = m; }
    });
    return best;
  }

  function moleculeCount(ppm) {
    var t = (ppm - PRE_INDUSTRIAL) / (900 - PRE_INDUSTRIAL);
    t = Math.max(0, Math.min(1, t));
    return Math.round(10 + t * 46);
  }

  // ---- canvas setup (device-pixel-ratio aware) ----
  var W = 0, H = 0, dpr = Math.max(1, window.devicePixelRatio || 1);
  function resize() {
    var rect = canvas.getBoundingClientRect();
    W = Math.max(280, rect.width);
    H = Math.max(220, rect.height);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);

  // ---- particle model ----
  var molecules = []; // greenhouse molecules floating in the atmosphere band
  var sunRays = [];   // incoming sunlight
  var heatRays = [];  // outgoing / bouncing infrared

  function seedMolecules(count) {
    molecules = [];
    for (var i = 0; i < count; i++) {
      molecules.push({
        x: Math.random(),
        y: 0.14 + Math.random() * 0.46,
        r: 3 + Math.random() * 2.4,
        vx: (Math.random() - 0.5) * 0.00012,
        vy: (Math.random() - 0.5) * 0.00008,
      });
    }
  }

  function spawnSunRay() {
    sunRays.push({ x: Math.random(), y: -0.02, vy: 0.012 + Math.random() * 0.004 });
  }
  function spawnHeatRay(x) {
    heatRays.push({ x: x, y: 0.86, vy: -(0.01 + Math.random() * 0.006), bounced: false });
  }

  var currentPpm = 427;
  var lastSpawn = 0;

  function step(ts) {
    if (!reduceMotion) {
      if (!lastSpawn || ts - lastSpawn > 260) {
        spawnSunRay();
        lastSpawn = ts;
      }
      updatePhysics();
    }
    draw();
    requestAnimationFrame(step);
  }

  function updatePhysics() {
    var escapeChance = escapeFractionFor(currentPpm);

    // sun rays fall, hit ground, spawn a heat ray
    for (var i = sunRays.length - 1; i >= 0; i--) {
      var s = sunRays[i];
      s.y += s.vy;
      if (s.y >= 0.86) {
        spawnHeatRay(s.x);
        sunRays.splice(i, 1);
      }
    }
    if (sunRays.length > 26) sunRays.splice(0, sunRays.length - 26);

    // heat rays rise; near the molecule band they may bounce back down
    // depending on how much CO2 is present (lower escapeChance = more bounces)
    for (var j = heatRays.length - 1; j >= 0; j--) {
      var h = heatRays[j];
      h.y += h.vy;
      var inBand = h.y < 0.6 && h.y > 0.12;
      if (inBand && !h.bounced && Math.random() > escapeChance * 0.985) {
        h.bounced = true;
        h.vy = Math.abs(h.vy);
      }
      if (h.y < -0.03 || h.y > 0.95) heatRays.splice(j, 1);
    }
    if (heatRays.length > 40) heatRays.splice(0, heatRays.length - 40);

    // drifting molecules
    molecules.forEach(function (m) {
      m.x += m.vx; m.y += m.vy;
      if (m.x < 0 || m.x > 1) m.vx *= -1;
      if (m.y < 0.1 || m.y > 0.62) m.vy *= -1;
    });
  }

  function lerpColor(a, b, t) {
    return [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * t); });
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    var warming = warmingFor(currentPpm);
    var warmT = Math.max(0, Math.min(1, warming / 4));
    var skyTop = lerpColor([214, 236, 232], [255, 214, 189], warmT);
    var skyBot = lerpColor([236, 246, 240], [255, 236, 214], warmT);
    var grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, "rgb(" + skyTop.join(",") + ")");
    grad.addColorStop(1, "rgb(" + skyBot.join(",") + ")");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    // sun
    ctx.beginPath();
    ctx.fillStyle = "#F5B942";
    ctx.arc(W * 0.88, H * 0.1, Math.max(14, W * 0.035), 0, Math.PI * 2);
    ctx.fill();

    // ground
    var groundY = H * 0.86;
    var groundGrad = ctx.createLinearGradient(0, groundY, 0, H);
    var groundColor = lerpColor([14, 92, 86], [200, 67, 47], warmT * 0.5);
    groundGrad.addColorStop(0, "rgb(" + groundColor.join(",") + ")");
    groundGrad.addColorStop(1, "rgba(10,70,65,0.9)");
    ctx.fillStyle = groundGrad;
    ctx.fillRect(0, groundY, W, H - groundY);

    // greenhouse molecule band
    ctx.save();
    molecules.forEach(function (m) {
      ctx.beginPath();
      ctx.fillStyle = "rgba(217,105,26,0.55)";
      ctx.arc(m.x * W, m.y * H, m.r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();

    // sun rays
    ctx.strokeStyle = "rgba(245,185,66,0.85)";
    ctx.lineWidth = 2;
    sunRays.forEach(function (s) {
      ctx.beginPath();
      ctx.moveTo(s.x * W, s.y * H);
      ctx.lineTo(s.x * W, s.y * H + 10);
      ctx.stroke();
    });

    // heat rays
    heatRays.forEach(function (h) {
      ctx.strokeStyle = h.bounced ? "rgba(200,67,47,0.9)" : "rgba(238,140,60,0.85)";
      ctx.beginPath();
      ctx.moveTo(h.x * W, h.y * H);
      ctx.lineTo(h.x * W, h.y * H + (h.vy < 0 ? 9 : -9));
      ctx.stroke();
    });
  }

  function applyPpm(ppm) {
    currentPpm = Math.max(280, Math.min(1000, ppm));
    if (slider) slider.value = String(Math.round(currentPpm));
    seedMolecules(moleculeCount(currentPpm));
    var warming = warmingFor(currentPpm);
    var escapePct = Math.round(escapeFractionFor(currentPpm) * 100);
    if (ppmReadout) ppmReadout.textContent = Math.round(currentPpm) + " ppm";
    if (ppmReadout2) ppmReadout2.textContent = Math.round(currentPpm) + " ppm";
    if (warmingReadout) warmingReadout.textContent = (warming >= 0 ? "+" : "") + warming.toFixed(2) + "\u00B0C";
    if (escapeReadout) escapeReadout.textContent = escapePct + "%";
    if (milestoneLabel) milestoneLabel.textContent = nearestMilestone(currentPpm).label;
  }

  if (slider) {
    slider.addEventListener("input", function () { applyPpm(parseFloat(slider.value)); });
  }
  presetBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { applyPpm(parseFloat(btn.getAttribute("data-ppm"))); });
  });

  resize();
  applyPpm(slider ? parseFloat(slider.value) : 427);
  if (reduceMotion) { draw(); } else { requestAnimationFrame(step); }
})();
