/* =============================================================
   Premium interaction layer — additive, progressive, safe.
   Loaded after js/main.js on every page. Auto-detects elements
   already in the DOM (no markup changes required elsewhere) and
   layers scroll reveal, magnetic tilt, button ripple, a cursor
   glow, and a light confetti burst on top of the existing site.
   Respects prefers-reduced-motion and coarse pointers throughout.
   ============================================================= */
(function () {
  "use strict";

  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var fine = window.matchMedia && window.matchMedia("(pointer: fine)").matches;

  /* ---- mark page ready once DOM is parsed, for the fade-in ---- */
  document.documentElement.classList.add("is-ready");

  /* ---- broaden scroll-reveal to common content blocks, staggered per group ---- */
  (function revealAuto() {
    if (reduced) return;
    var groupSelectors = [
      ".grid > .card", ".fact-strip > .fact", ".numbered-list > li",
      ".glossary-grid > .gloss-item", ".lesson-list > .lesson-card",
      ".checklist > li", ".sim-stats > .sim-stat"
    ];
    groupSelectors.forEach(function (sel) {
      var els = document.querySelectorAll(sel);
      els.forEach(function (el, i) {
        if (el.classList.contains("reveal")) return; // already handled by main.js
        el.classList.add("reveal-auto");
        el.style.setProperty("--ri", Math.min(i, 8));
      });
    });
    var singles = document.querySelectorAll(
      ".callout, .worksheet, .tool-panel, .quiz-card, .chart-card, .weather-card, .objective-box, .complete-box"
    );
    singles.forEach(function (el) {
      if (el.classList.contains("reveal")) return;
      el.classList.add("reveal-auto");
    });

    var targets = document.querySelectorAll(".reveal-auto");
    if (!("IntersectionObserver" in window) || !targets.length) {
      targets.forEach(function (el) { el.classList.add("is-in"); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
    );
    targets.forEach(function (el) { io.observe(el); });
  })();

  /* ---- magnetic tilt on cards & panels (fine pointer only) ---- */
  (function tilt() {
    if (reduced || !fine) return;
    var els = document.querySelectorAll(
      ".card, .lesson-card, .sim-panel, .tool-panel, .quiz-card, .weather-card, .hero-media"
    );
    els.forEach(function (el) {
      el.classList.add("tilt-el");
      var rect;
      function onMove(e) {
        rect = el.getBoundingClientRect();
        var px = (e.clientX - rect.left) / rect.width - 0.5;
        var py = (e.clientY - rect.top) / rect.height - 0.5;
        var rx = (py * -5).toFixed(2);
        var ry = (px * 6).toFixed(2);
        el.style.transform = "perspective(900px) rotateX(" + rx + "deg) rotateY(" + ry + "deg) translateY(-4px)";
      }
      function onLeave() {
        el.style.transform = "";
      }
      el.addEventListener("mousemove", onMove);
      el.addEventListener("mouseleave", onLeave);
    });
  })();

  /* ---- button ripple, works alongside the CSS sheen sweep ---- */
  (function ripple() {
    document.addEventListener("pointerdown", function (e) {
      var btn = e.target.closest && e.target.closest(".btn, .icon-btn, .sim-preset, .quiz-opt, .checklist li");
      if (!btn) return;
      var rect = btn.getBoundingClientRect();
      var size = Math.max(rect.width, rect.height) * 1.6;
      var span = document.createElement("span");
      span.className = "ripple";
      span.style.width = span.style.height = size + "px";
      span.style.left = (e.clientX - rect.left - size / 2) + "px";
      span.style.top = (e.clientY - rect.top - size / 2) + "px";
      var prevPos = getComputedStyle(btn).position;
      if (prevPos === "static") btn.style.position = "relative";
      btn.appendChild(span);
      window.setTimeout(function () { span.remove(); }, 650);
    });
  })();

  /* ---- cursor glow (fine pointer only, desktop) ---- */
  (function cursorGlow() {
    if (reduced || !fine) return;
    var glow = document.createElement("div");
    glow.className = "cursor-glow";
    glow.setAttribute("aria-hidden", "true");
    document.body.appendChild(glow);
    var raf = null;
    document.addEventListener("mousemove", function (e) {
      glow.classList.add("is-active");
      if (raf) return;
      raf = requestAnimationFrame(function () {
        glow.style.transform = "translate(" + e.clientX + "px," + e.clientY + "px) translate(-50%,-50%)";
        raf = null;
      });
    });
    document.addEventListener("mouseleave", function () { glow.classList.remove("is-active"); });
  })();

  /* ---- light confetti burst, exposed globally for quiz/certificate wins ---- */
  window.GWConfetti = function (opts) {
    if (reduced) return;
    opts = opts || {};
    var count = opts.count || 90;
    var duration = opts.duration || 2600;
    var canvas = document.getElementById("confetti-canvas");
    var created = false;
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.id = "confetti-canvas";
      canvas.setAttribute("aria-hidden", "true");
      document.body.appendChild(canvas);
      created = true;
    }
    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    function size() {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    size();
    var colors = ["#16847A", "#EE8C3C", "#C8432F", "#4FC7B8", "#F5B87D"];
    var pieces = [];
    for (var i = 0; i < count; i++) {
      pieces.push({
        x: Math.random() * window.innerWidth,
        y: -20 - Math.random() * window.innerHeight * 0.3,
        w: 6 + Math.random() * 6,
        h: 8 + Math.random() * 10,
        rot: Math.random() * 360,
        vRot: (Math.random() - 0.5) * 10,
        vy: 2 + Math.random() * 3,
        vx: (Math.random() - 0.5) * 2,
        color: colors[i % colors.length]
      });
    }
    var start = null;
    function frame(ts) {
      if (!start) start = ts;
      var elapsed = ts - start;
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      pieces.forEach(function (p) {
        p.x += p.vx; p.y += p.vy; p.rot += p.vRot;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rot * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      });
      if (elapsed < duration) {
        requestAnimationFrame(frame);
      } else {
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        if (created) canvas.remove();
      }
    }
    requestAnimationFrame(frame);
    window.addEventListener("resize", size, { passive: true });
  };
})();
