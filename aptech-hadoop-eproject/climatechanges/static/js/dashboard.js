/* Class Dashboard, fetches roster-data.json (built by the GitHub Action)
   and renders it. Handles the "no data yet" first-run state gracefully. */
(function(){
  "use strict";
  var mount = document.getElementById("dashboard-mount");
  if (!mount) return;

  function escapeHtml(s){
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }

  function timeAgo(iso){
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    var diff = Math.max(0, Date.now() - d.getTime());
    var mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + "m ago";
    var hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + "h ago";
    var days = Math.floor(hrs / 24);
    return days + "d ago";
  }

  function stat(value, label){
    return '<div class="fact"><div class="fv">' + value + '</div><div class="fl">' + label + '</div></div>';
  }

  function renderEmpty(){
    mount.innerHTML =
      '<div class="callout callout--note">' +
      '<span class="callout-label">No check-ins yet</span>' +
      '<p>This page reads <code>roster-data.json</code>, which a free GitHub Action regenerates automatically whenever someone submits the <a href="checkin.html">Check In</a> form. Once the first check-in Issue lands in the repo, this dashboard fills in on its own: usually within minutes, or up to a few hours on the scheduled fallback run.</p>' +
      '<p style="margin-top:10px;">Site owner: if this message persists after a real check-in, open the repo\u2019s <strong>Actions</strong> tab and confirm the "Update Class Dashboard" workflow ran successfully.</p>' +
      '</div>';
  }

  function renderError(){
    mount.innerHTML =
      '<div class="callout callout--note"><span class="callout-label">Dashboard data not found yet</span>' +
      '<p>That\u2019s expected before the first check-in or the first Action run. See the note above for what happens next.</p></div>';
  }

  function render(data){
    var students = data.students || [];
    var checkins = data.checkins || [];
    if (!students.length){ renderEmpty(); return; }

    var classCodes = Array.from(new Set(
      students.map(function(s){ return (s.class_code || "").trim(); }).filter(Boolean)
    )).sort();

    var selectedClass = "";

    function statsHtml(list){
      var avg = list.length ? list.reduce(function(s, x){ return s + (x.progress || 0); }, 0) / list.length : 0;
      var finished = list.filter(function(s){ return s.progress >= 8; }).length;
      return '<div class="grid grid-4 reveal" style="margin-bottom:10px;">' +
        stat(list.length, "Students checked in") +
        stat(checkins.length, "Total check-ins") +
        stat(list.length ? avg.toFixed(1) : "0", "Avg. lessons / student") +
        stat(finished, "Finished all 8") +
        '</div>';
    }

    function listHtml(list){
      var html = '<ol class="lesson-list reveal">';
      list.forEach(function(s){
        var pct = Math.round(((s.progress || 0) / 8) * 100);
        var done = (s.progress || 0) >= 8;
        var classBadge = s.class_code ? ' &middot; <span class="mono">' + escapeHtml(s.class_code) + '</span>' : "";
        html += '<li class="lesson-card' + (done ? " is-complete" : "") + '" style="cursor:default;">' +
          '<span class="ln">' + (s.progress != null ? s.progress : "?") + '</span>' +
          '<div style="flex:1;min-width:0;">' +
            '<div class="lc-title">' + escapeHtml(s.name) + '</div>' +
            '<div class="lc-obj">' + (s.progress || 0) + ' of 8 lessons &middot; last check-in ' + escapeHtml(timeAgo(s.updated_at || s.created_at) || "recently") + classBadge + '</div>' +
            '<div class="result-bar" style="margin-top:8px;height:8px;background:var(--line-soft);"><span style="width:' + pct + '%;"></span></div>' +
          '</div>' +
          (s.issue_url ? '<a class="lesson-check" href="' + s.issue_url + '" target="_blank" rel="noopener">Issue →</a>' : "") +
          '</li>';
      });
      html += '</ol>';
      return html;
    }

    var filterHtml = "";
    if (classCodes.length){
      filterHtml = '<div class="field" style="max-width:320px;margin-bottom:18px;">' +
        '<label for="dashboard-class-filter">Filter by class / school code</label>' +
        '<select id="dashboard-class-filter" style="margin-top:6px;">' +
        '<option value="">All classes (' + students.length + ')</option>' +
        classCodes.map(function(c){
          var count = students.filter(function(s){ return (s.class_code || "").trim() === c; }).length;
          return '<option value="' + escapeHtml(c) + '">' + escapeHtml(c) + ' (' + count + ')</option>';
        }).join("") +
        '</select></div>';
    }

    mount.innerHTML = filterHtml +
      '<div id="dashboard-stats">' + statsHtml(students) + '</div>' +
      '<p class="muted" style="font-size:.8rem;margin:0 0 20px;">Last updated ' +
        escapeHtml(timeAgo(data.generated_at) || "recently") + ' · refreshes automatically</p>' +
      '<div id="dashboard-list">' + listHtml(students) + '</div>';

    var filterSelect = document.getElementById("dashboard-class-filter");
    if (filterSelect){
      filterSelect.addEventListener("change", function(){
        selectedClass = filterSelect.value;
        var filtered = selectedClass
          ? students.filter(function(s){ return (s.class_code || "").trim() === selectedClass; })
          : students;
        document.getElementById("dashboard-stats").innerHTML = statsHtml(filtered);
        document.getElementById("dashboard-list").innerHTML = listHtml(filtered);
      });
    }
  }

  fetch("roster-data.json", { cache: "no-store" })
    .then(function(r){ if (!r.ok) throw new Error("not found"); return r.json(); })
    .then(render)
    .catch(renderError);
})();
