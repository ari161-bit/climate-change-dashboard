(function () {
  "use strict";

  var intro = document.getElementById("cinematic-intro");
  if (!intro) return;

  var seen = false;
  try {
    seen = window.sessionStorage.getItem("earthscape-intro-seen") === "1";
  } catch (error) {
    seen = false;
  }
  var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (seen || reducedMotion) return;

  intro.hidden = false;
  intro.setAttribute("aria-hidden", "false");
  intro.classList.add("is-active");

  var finished = false;
  function finish() {
    if (finished) return;
    finished = true;
    intro.classList.add("is-leaving");
    intro.setAttribute("aria-hidden", "true");
    try {
      window.sessionStorage.setItem("earthscape-intro-seen", "1");
    } catch (error) {
      // The intro still exits when browser storage is disabled.
    }
    window.setTimeout(function () {
      intro.hidden = true;
      intro.classList.remove("is-active", "is-leaving");
    }, 1000);
  }

  var skip = document.getElementById("intro-skip");
  if (skip) skip.addEventListener("click", finish);
  document.addEventListener("keydown", function (event) {
    if (!finished && (event.key === "Escape" || event.key === "Enter")) finish();
  });
  window.setTimeout(finish, 2900);

  var art = document.querySelector(".eco-art");
  if (art && !reducedMotion && window.matchMedia("(hover: hover)").matches) {
    art.addEventListener("pointermove", function (event) {
      var bounds = art.getBoundingClientRect();
      var x = (event.clientX - bounds.left) / bounds.width - 0.5;
      var y = (event.clientY - bounds.top) / bounds.height - 0.5;
      art.style.transform = "perspective(1100px) rotateY(" + (x * 7).toFixed(2) + "deg) rotateX(" + (-y * 5).toFixed(2) + "deg)";
    });
    art.addEventListener("pointerleave", function () {
      art.style.transform = "";
    });
  }

  var revealItems = document.querySelectorAll(".eco-home .eco-section .wrap > *, .eco-home .eco-stat");
  if ("IntersectionObserver" in window && !reducedMotion) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("cin-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealItems.forEach(function (element, index) {
      element.classList.add("cin-reveal");
      element.style.transitionDelay = (index % 4) * 70 + "ms";
      observer.observe(element);
    });
  }
})();
