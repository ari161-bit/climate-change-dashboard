/* Shared site behaviour: mobile menu, scroll-reveal, counting readouts */
(function(){
  "use strict";

  /* ---- mobile menu (slide-in drawer) ---- */
  var menuBtn = document.getElementById("menu-btn");
  var mobileMenu = document.getElementById("mobile-menu");
  var backdrop = document.getElementById("mobile-menu-backdrop");
  var closeBtn = document.getElementById("mobile-menu-close");
  var scrollLockY = 0;
  var scrollLockCount = 0;

  function lockBodyScroll(){
    if (scrollLockCount === 0){
      scrollLockY = window.scrollY || document.documentElement.scrollTop || 0;
      document.body.style.position = "fixed";
      document.body.style.top = (-scrollLockY) + "px";
      document.body.style.left = "0";
      document.body.style.right = "0";
      document.body.style.width = "100%";
    }
    scrollLockCount++;
  }
  function unlockBodyScroll(){
    if (scrollLockCount <= 0) return;
    scrollLockCount--;
    if (scrollLockCount === 0){
      document.body.style.position = "";
      document.body.style.top = "";
      document.body.style.left = "";
      document.body.style.right = "";
      document.body.style.width = "";
      window.scrollTo(0, scrollLockY);
    }
  }

  function setMenu(open){
    if (!mobileMenu) return;
    mobileMenu.classList.toggle("is-open", open);
    if (backdrop) backdrop.classList.toggle("is-open", open);
    if (menuBtn){
      menuBtn.classList.toggle("is-open", open);
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    }
    if (open) lockBodyScroll(); else unlockBodyScroll();
  }

  if (menuBtn && mobileMenu){
    menuBtn.addEventListener("click", function(){
      setMenu(!mobileMenu.classList.contains("is-open"));
    });
    if (closeBtn) closeBtn.addEventListener("click", function(){ setMenu(false); });
    if (backdrop) backdrop.addEventListener("click", function(){ setMenu(false); });
    document.addEventListener("keydown", function(e){
      if (e.key === "Escape") setMenu(false);
    });
    mobileMenu.querySelectorAll("a").forEach(function(a){
      a.addEventListener("click", function(){ setMenu(false); });
    });
  }

  /* ---- scroll reveal ---- */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length){
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting){
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function(el){ io.observe(el); });
  } else {
    revealEls.forEach(function(el){ el.classList.add("is-visible"); });
  }

  /* ---- animated readout counters ----
     usage: <span class="ro-value js-counter" data-target="427.3" data-decimals="1" data-suffix=""></span> */
  var counters = document.querySelectorAll(".js-counter");
  function animateCounter(el){
    var target = parseFloat(el.getAttribute("data-target") || "0");
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    var prefix = el.getAttribute("data-prefix") || "";
    var suffix = el.getAttribute("data-suffix") || "";
    var dur = 1100;
    var start = null;
    function step(ts){
      if (!start) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      var val = target * eased;
      el.textContent = prefix + val.toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  if (counters.length){
    if ("IntersectionObserver" in window){
      var cio = new IntersectionObserver(function(entries){
        entries.forEach(function(entry){
          if (entry.isIntersecting){
            animateCounter(entry.target);
            cio.unobserve(entry.target);
          }
        });
      }, { threshold: 0.4 });
      counters.forEach(function(el){ cio.observe(el); });
    } else {
      counters.forEach(animateCounter);
    }
  }

  /* ---- current year in footer ---- */
  var yearEl = document.querySelector(".js-year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  /* ---- dark mode toggle (persisted, respects prefers-color-scheme by default) ---- */
  var themeBtn = document.getElementById("theme-toggle");
  function currentTheme(){
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }
  function setTheme(theme){
    if (theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
    try{ localStorage.setItem("gw-theme", theme); }catch(e){}
    if (themeBtn) themeBtn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
  }
  if (themeBtn){
    themeBtn.setAttribute("aria-pressed", currentTheme() === "dark" ? "true" : "false");
    themeBtn.addEventListener("click", function(){
      setTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  /* ---- header shadow once the page scrolls ---- */
  var siteHeader = document.querySelector(".site-header");
  if (siteHeader){
    var updateHeaderShadow = function(){
      siteHeader.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    updateHeaderShadow();
    window.addEventListener("scroll", updateHeaderShadow, { passive: true });
  }

  /* ---- scroll progress bar ---- */
  var progressBar = document.getElementById("scroll-progress-bar");
  if (progressBar){
    var ticking = false;
    function updateProgress(){
      var doc = document.documentElement;
      var scrollTop = doc.scrollTop || document.body.scrollTop;
      var height = (doc.scrollHeight - doc.clientHeight) || 1;
      var pct = Math.min(100, Math.max(0, (scrollTop / height) * 100));
      progressBar.style.width = pct + "%";
      ticking = false;
    }
    updateProgress();
    window.addEventListener("scroll", function(){
      if (!ticking){ window.requestAnimationFrame(updateProgress); ticking = true; }
    }, { passive: true });
    window.addEventListener("resize", updateProgress);
  }

  /* ---- back to top button ---- */
  var backToTop = document.getElementById("back-to-top");
  if (backToTop){
    window.addEventListener("scroll", function(){
      backToTop.classList.toggle("is-visible", window.scrollY > 500);
    }, { passive: true });
    backToTop.addEventListener("click", function(){
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /* ---- command palette: Ctrl/Cmd+K quick jump across all pages ---- */
  var paletteBackdrop = document.getElementById("palette-backdrop");
  var paletteInput = document.getElementById("palette-input");
  var paletteResults = document.getElementById("palette-results");
  var pages = window.SITE_PAGES || [];
  var activeIndex = -1;
  var visibleItems = [];

  function renderPalette(query){
    var q = (query || "").trim().toLowerCase();
    var filtered = !q ? pages : pages.filter(function(p){
      return (p.title + " " + p.desc + " " + p.group).toLowerCase().indexOf(q) !== -1;
    });
    if (!paletteResults) return;
    if (!filtered.length){
      paletteResults.innerHTML = '<div class="palette-empty">No pages match &ldquo;' + q + '&rdquo;.</div>';
      visibleItems = [];
      return;
    }
    var groups = [];
    var seen = {};
    filtered.forEach(function(p){
      if (!seen[p.group]){ seen[p.group] = true; groups.push(p.group); }
    });
    var html = "";
    groups.forEach(function(group){
      html += '<div class="palette-group">' + group + '</div>';
      filtered.filter(function(p){ return p.group === group; }).forEach(function(p){
        html += '<button class="palette-item" data-href="' + p.href + '">' +
          '<span class="pi-ico">' + p.icon + '</span>' +
          '<span><span class="pi-title">' + p.title + '</span>' +
          '<div class="pi-desc">' + p.desc + '</div></span>' +
          '</button>';
      });
    });
    paletteResults.innerHTML = html;
    visibleItems = Array.prototype.slice.call(paletteResults.querySelectorAll(".palette-item"));
    activeIndex = visibleItems.length ? 0 : -1;
    highlightActive();
    visibleItems.forEach(function(item){
      item.addEventListener("click", function(){
        window.location.href = item.getAttribute("data-href");
      });
    });
  }

  function highlightActive(){
    visibleItems.forEach(function(item, i){
      item.classList.toggle("is-active", i === activeIndex);
    });
    if (activeIndex >= 0 && visibleItems[activeIndex]){
      visibleItems[activeIndex].scrollIntoView({ block: "nearest" });
    }
  }

  function openPalette(){
    if (!paletteBackdrop) return;
    renderPalette("");
    paletteBackdrop.classList.add("is-open");
    lockBodyScroll();
    if (paletteInput){ paletteInput.value = ""; paletteInput.focus(); }
  }
  function closePalette(){
    if (!paletteBackdrop) return;
    paletteBackdrop.classList.remove("is-open");
    unlockBodyScroll();
  }

  if (paletteBackdrop){
    paletteBackdrop.addEventListener("click", function(e){
      if (e.target === paletteBackdrop) closePalette();
    });
  }
  if (paletteInput){
    paletteInput.addEventListener("input", function(){
      renderPalette(paletteInput.value);
    });
    paletteInput.addEventListener("keydown", function(e){
      if (e.key === "ArrowDown"){
        e.preventDefault();
        if (visibleItems.length){ activeIndex = (activeIndex + 1) % visibleItems.length; highlightActive(); }
      } else if (e.key === "ArrowUp"){
        e.preventDefault();
        if (visibleItems.length){ activeIndex = (activeIndex - 1 + visibleItems.length) % visibleItems.length; highlightActive(); }
      } else if (e.key === "Enter"){
        e.preventDefault();
        if (activeIndex >= 0 && visibleItems[activeIndex]){
          window.location.href = visibleItems[activeIndex].getAttribute("data-href");
        }
      }
    });
  }
  document.addEventListener("keydown", function(e){
    var isK = e.key === "k" || e.key === "K";
    if ((e.metaKey || e.ctrlKey) && isK){
      e.preventDefault();
      if (paletteBackdrop && paletteBackdrop.classList.contains("is-open")) closePalette();
      else openPalette();
    } else if (e.key === "Escape" && paletteBackdrop && paletteBackdrop.classList.contains("is-open")){
      closePalette();
    }
  });

})();
