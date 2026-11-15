/* Course progress tracking, uses localStorage on the real deployed site.
   (Note: localStorage is unavailable inside some sandboxed preview frames; this degrades gracefully to in-memory-only tracking there, but works
   normally once this site is deployed to GitHub Pages or any real host.) */
(function(){
  "use strict";
  var KEY = "gw-explorer-progress";
  var TOTAL = 8;
  var memoryFallback = { completed: [] };
  var storageOK = true;

  function read(){
    try{
      var raw = window.localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : { completed: [] };
    }catch(e){
      storageOK = false;
      return memoryFallback;
    }
  }
  function write(data){
    try{
      window.localStorage.setItem(KEY, JSON.stringify(data));
    }catch(e){
      storageOK = false;
      memoryFallback = data;
    }
  }
  function isComplete(num){
    return read().completed.indexOf(num) !== -1;
  }
  function toggle(num){
    var data = read();
    var i = data.completed.indexOf(num);
    if (i === -1) data.completed.push(num); else data.completed.splice(i, 1);
    write(data);
    return isComplete(num);
  }
  function resetAll(){
    write({ completed: [] });
  }
  function count(){
    return read().completed.length;
  }

  window.GWProgress = { isComplete: isComplete, toggle: toggle, resetAll: resetAll, count: count, TOTAL: TOTAL, storageOK: function(){ return storageOK; } };

  /* ---- lesson page: mark-complete button ---- */
  var btn = document.getElementById("mark-complete-btn");
  if (btn){
    var num = parseInt(btn.getAttribute("data-lesson"), 10);
    function renderBtn(){
      var done = isComplete(num);
      btn.textContent = done ? "✓ Lesson complete" : "Mark this lesson complete";
      btn.classList.toggle("btn-primary", !done);
      btn.classList.toggle("btn-ghost", done);
      var status = document.getElementById("complete-status");
      if (status) status.textContent = done ? "Nice work, saved on this device." : "";
    }
    btn.addEventListener("click", function(){ toggle(num); renderBtn(); });
    renderBtn();
    if (!storageOK){
      var warn = document.getElementById("complete-status");
      if (warn) warn.textContent = "Note: this preview can't save progress; it will on the deployed site.";
    }
  }

  /* ---- course index: progress bar + per-lesson checks ---- */
  var bar = document.getElementById("course-progress-bar");
  var countEl = document.getElementById("course-progress-count");
  if (bar || countEl){
    var done = count();
    if (countEl) countEl.textContent = done;
    if (bar) bar.style.width = Math.round((done / TOTAL) * 100) + "%";
    document.querySelectorAll(".lesson-card").forEach(function(card){
      var n = parseInt(card.getAttribute("data-lesson"), 10);
      if (isComplete(n)){
        card.classList.add("is-complete");
        var chip = card.querySelector(".lesson-check");
        if (chip) chip.textContent = "✓ Done";
      }
    });
  }
  var resetBtn = document.getElementById("reset-progress-btn");
  if (resetBtn){
    resetBtn.addEventListener("click", function(){
      if (window.confirm("Reset progress for all 8 lessons on this device?")){
        resetAll();
        window.location.reload();
      }
    });
  }
})();
