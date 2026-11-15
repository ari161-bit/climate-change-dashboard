// Galaxy theme effects: shooting stars, card spotlight, scroll-in sections.
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // shooting stars
  if (!reduce) {
    var sky = document.createElement("div");
    sky.className = "gx-sky";
    sky.setAttribute("aria-hidden", "true");
    document.body.prepend(sky);
    function shoot() {
      var s = document.createElement("span");
      s.className = "gx-star";
      s.style.left = (40 + Math.random() * 70) + "vw";
      s.style.top = (Math.random() * 45) + "vh";
      sky.appendChild(s);
      setTimeout(function () { s.remove(); }, 1600);
      setTimeout(shoot, 2500 + Math.random() * 4000);
    }
    setTimeout(shoot, 1200);
  }

  // spotlight follows the mouse inside cards
  document.addEventListener("pointermove", function (e) {
    var el = e.target.closest && e.target.closest(".card, .lesson-card, .ds-card, .side-card, .login-card, .signup-card");
    if (!el) return;
    var r = el.getBoundingClientRect();
    el.style.setProperty("--mx", (e.clientX - r.left) + "px");
    el.style.setProperty("--my", (e.clientY - r.top) + "px");
  }, { passive: true });

  // sections fade/slide in as you scroll
  if (!reduce && "IntersectionObserver" in window) {
    var targets = document.querySelectorAll("main .section .wrap > *, .ds-card, .ds-stat");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("gx-show"); io.unobserve(en.target); }
      });
    }, { threshold: 0.12 });
    targets.forEach(function (t, i) {
      if (t.getBoundingClientRect().top < window.innerHeight) return; // already on screen
      t.classList.add("gx-in");
      t.style.transitionDelay = (i % 4) * 70 + "ms";
      io.observe(t);
    });
  }
})();

// highlight the nav link for the current page
(function () {
  var here = location.pathname.replace(/index\.html$/, "");
  document.querySelectorAll(".nav-desktop .nav-link").forEach(function (a) {
    var path = new URL(a.href, location.href).pathname;
    a.classList.toggle("is-active", path === here);
  });
})();
