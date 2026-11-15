/* Class check-in, turns local lesson progress into a pre-filled GitHub Issue
   the student opens and submits themselves. No backend, no secrets, no auto-
   posting: nothing is sent anywhere until the student clicks "Submit new
   issue" on github.com.

   ⚠️ SETUP REQUIRED: change GITHUB_REPO below to match the real repo this
   site is deployed from, e.g. "babatundeawo/global-warming-explorer". Until
   that's changed, the check-in link will 404. */
(function(){
  "use strict";
  var GITHUB_REPO = "babatundeawo/globalwarming";

  var LESSON_TITLES = {
    1: "The Greenhouse Effect", 2: "Causes of Global Warming",
    3: "Effects, Worldwide and at Home", 4: "Why Should We Care?",
    5: "Your Carbon Footprint", 6: "Reduce, Reuse, Recycle",
    7: "Clean Energy", 8: "Taking Action"
  };

  var form = document.getElementById("checkin-form");
  if (!form) return;

  var nameInput = document.getElementById("checkin-name");
  var classInput = document.getElementById("checkin-class");
  var noteInput = document.getElementById("checkin-note");
  var progressList = document.getElementById("checkin-progress-list");
  var progressCount = document.getElementById("checkin-progress-count");
  var submitBtn = document.getElementById("checkin-submit");
  var setupWarning = document.getElementById("checkin-setup-warning");
  var resultBox = document.getElementById("checkin-result");

  if (GITHUB_REPO.indexOf("REPLACE-WITH") !== -1 && setupWarning){
    setupWarning.style.display = "block";
  }

  function getCompletedNums(){
    var nums = [];
    if (window.GWProgress){
      for (var i = 1; i <= window.GWProgress.TOTAL; i++){
        if (window.GWProgress.isComplete(i)) nums.push(i);
      }
    }
    return nums;
  }

  function renderProgress(){
    var nums = getCompletedNums();
    if (progressCount) progressCount.textContent = nums.length;
    if (progressList){
      progressList.innerHTML = nums.length
        ? nums.map(function(n){ return "<li>Lesson " + n + ", " + LESSON_TITLES[n] + "</li>"; }).join("")
        : "<li class=\"muted\">No lessons marked complete on this device yet.</li>";
    }
  }
  renderProgress();

  form.addEventListener("submit", function(e){
    e.preventDefault();
    var name = (nameInput.value || "").trim();
    if (!name){
      nameInput.focus();
      return;
    }
    var classCode = (classInput && classInput.value.trim()) ? classInput.value.trim() : "";
    var nums = getCompletedNums();
    var lessonLines = nums.length
      ? nums.map(function(n){ return "- Lesson " + n + ": " + LESSON_TITLES[n]; }).join("\n")
      : "- No lessons marked complete yet";
    var note = (noteInput && noteInput.value.trim()) ? noteInput.value.trim() : "(none)";

    var title = "Check-in: " + name + ", " + nums.length + "/8 lessons";
    var body =
      "**Name:** " + name + "\n" +
      (classCode ? "**Class:** " + classCode + "\n" : "") +
      "**Progress:** " + nums.length + " of 8 lessons\n\n" +
      "**Completed:**\n" + lessonLines + "\n\n" +
      "**Note to teacher:** " + note + "\n\n" +
      "---\n_Submitted via the Global Warming Explorer course check-in page._";

    var url = "https://github.com/" + GITHUB_REPO + "/issues/new?title="
      + encodeURIComponent(title) + "&body=" + encodeURIComponent(body);

    window.open(url, "_blank", "noopener");
    if (resultBox){
      resultBox.style.display = "block";
      resultBox.textContent = "A new tab just opened on GitHub with your check-in pre-filled. You may need to sign in (it's free), then click \"Submit new issue\" to actually send it, nothing is sent until you do that.";
    }
  });
})();
