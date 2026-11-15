/* Action Hub checklist, in-memory only (resets on reload by design) */
(function(){
  "use strict";
  var list = document.querySelectorAll(".checklist li");
  var countEl = document.getElementById("impact-count");
  var totalEl = document.getElementById("impact-total");
  if (!list.length || !countEl) return;

  if (totalEl) totalEl.textContent = list.length;

  function update(){
    var checked = document.querySelectorAll(".checklist li.checked").length;
    countEl.textContent = checked;
  }

  list.forEach(function(li){
    var box = li.querySelector("input[type=checkbox]");
    if (!box) return;
    function toggle(){
      box.checked = !box.checked;
      li.classList.toggle("checked", box.checked);
      update();
    }
    li.addEventListener("click", function(e){
      if (e.target === box) { li.classList.toggle("checked", box.checked); update(); return; }
      toggle();
    });
    li.setAttribute("tabindex", "0");
    li.setAttribute("role", "checkbox");
    li.setAttribute("aria-checked", "false");
    li.addEventListener("keydown", function(e){
      if (e.key === "Enter" || e.key === " "){ e.preventDefault(); toggle(); li.setAttribute("aria-checked", box.checked); }
    });
    box.addEventListener("change", function(){ li.setAttribute("aria-checked", box.checked); });
  });

  update();
})();
