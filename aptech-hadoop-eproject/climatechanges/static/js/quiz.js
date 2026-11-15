/* Climate Explorer Quiz, in-memory state only */
(function(){
  "use strict";
  var mount = document.getElementById("quiz-mount");
  if (!mount) return;

  var QUESTIONS = [
    {
      q: "What is the main job of greenhouse gases like CO2 in our atmosphere?",
      options: ["They block all sunlight from reaching Earth", "They trap heat that would otherwise escape to space", "They create the wind", "They make the sky blue"],
      correct: 1,
      explain: "Greenhouse gases let sunlight in but trap some of the heat that Earth's surface radiates back out, like a blanket around the planet."
    },
    {
      q: "About how much has atmospheric CO2 risen since before the Industrial Revolution (around 1750-1800)?",
      options: ["About 5% higher", "About 50% higher", "It hasn't changed", "It's actually lower now"],
      correct: 1,
      explain: "Pre-industrial CO2 was about 280 parts per million (ppm). By 2025 the global average was around 427 ppm, roughly 50% higher."
    },
    {
      q: "Which of these is the LARGEST human source of greenhouse gas emissions worldwide?",
      options: ["Burning fossil fuels for electricity, heat and transport", "Cows burping", "Volcanoes", "Recycling plastic"],
      correct: 0,
      explain: "Burning coal, oil and gas for energy and transport is by far the largest source, agriculture and land-use change are significant too, but smaller."
    },
    {
      q: "Which Nigerian state was hit by some of the country's worst flash floods on record in 2025?",
      options: ["Niger State (Mokwa)", "Cross River", "Ekiti", "Nasarawa"],
      correct: 0,
      explain: "Heavy rainfall and a dam-related surge caused devastating flooding in Mokwa, Niger State, in May 2025, officials called it the worst in decades for the area."
    },
    {
      q: "What does 'renewable energy' mean?",
      options: ["Energy that never runs out, like sunlight and wind", "Energy you can use only once", "Energy made only from oil", "Energy that costs nothing to build"],
      correct: 0,
      explain: "Renewable energy comes from sources that naturally replenish, sunlight, wind, flowing water, and so on, instead of being dug up and burned."
    },
    {
      q: "Roughly what share of the world's electricity came from renewable sources in 2025?",
      options: ["About 1%", "About one third (34%)", "About 90%", "Exactly half"],
      correct: 1,
      explain: "Renewables reached about 34% of global electricity generation in 2025, up from roughly 23% just a decade earlier, fast growth, but still room to go."
    },
    {
      q: "Why does recycling a can or bottle usually produce fewer emissions than making a new one?",
      options: ["It doesn't, recycling uses more energy", "Processing used material generally takes less energy than mining and refining raw material", "Recycled items are smaller", "It only matters for paper"],
      correct: 1,
      explain: "Turning used aluminium, glass or paper back into new products usually takes much less energy than starting from raw ore, sand or trees."
    },
    {
      q: "What's a simple definition of someone's 'carbon footprint'?",
      options: ["The size of shoe they wear", "The total greenhouse gases caused by their activities and lifestyle", "How many trees they've planted", "Their height"],
      correct: 1,
      explain: "A carbon footprint adds up the greenhouse gas emissions linked to things like travel, electricity use, and diet, usually measured in tonnes of CO2-equivalent per year."
    },
    {
      q: "Which of these actions has the biggest day-to-day impact on most people's personal footprint?",
      options: ["Turning off one light switch once", "Reducing car travel, flights, and energy waste", "Buying a new phone case", "Using a paper straw instead of plastic"],
      correct: 1,
      explain: "Transport and energy use tend to dominate a personal footprint far more than small single actions, though every habit adds up."
    },
    {
      q: "Why do scientists say Africa is especially vulnerable to climate change, even though it has produced a small share of historic global emissions?",
      options: ["Africa has no rivers", "Many African economies depend heavily on farming, fishing and rainfall patterns that climate change disrupts", "It never rains in Africa", "Climate change only affects cold countries"],
      correct: 1,
      explain: "Heavy reliance on rain-fed agriculture, coastal cities, and limited infrastructure to absorb shocks make many African communities highly exposed to floods, drought and heat, despite contributing comparatively little to the emissions causing the problem."
    }
  ];

  var idx = 0, score = 0, answered = false;

  function render(){
    if (idx >= QUESTIONS.length){ renderFinal(); return; }
    var item = QUESTIONS[idx];
    answered = false;
    var pct = (idx / QUESTIONS.length) * 100;
    mount.innerHTML =
      '<div class="quiz-progress" aria-hidden="true"><span style="width:' + pct + '%"></span></div>' +
      '<p class="muted mono" style="font-size:.8rem;margin-bottom:6px;">QUESTION ' + (idx+1) + ' OF ' + QUESTIONS.length + '</p>' +
      '<h3 style="font-size:1.3rem;margin-bottom:4px;">' + item.q + '</h3>' +
      '<div class="quiz-options" id="quiz-options"></div>' +
      '<div class="quiz-explain" id="quiz-explain"></div>' +
      '<div class="quiz-foot"><span class="muted mono" style="font-size:.85rem;">Score: ' + score + '</span>' +
      '<button class="btn btn-primary btn-sm" id="quiz-next" style="display:none;">Next →</button></div>';

    var optWrap = document.getElementById("quiz-options");
    item.options.forEach(function(opt, i){
      var b = document.createElement("button");
      b.className = "quiz-opt";
      b.textContent = opt;
      b.addEventListener("click", function(){ choose(i, b); });
      optWrap.appendChild(b);
    });

    document.getElementById("quiz-next").addEventListener("click", function(){ idx++; render(); });
  }

  function choose(i, btn){
    if (answered) return;
    answered = true;
    var item = QUESTIONS[idx];
    var correct = i === item.correct;
    if (correct) score++;
    document.querySelectorAll("#quiz-options .quiz-opt").forEach(function(b, j){
      b.disabled = true;
      if (j === item.correct) b.classList.add("correct");
      else if (j === i) b.classList.add("wrong");
    });
    var ex = document.getElementById("quiz-explain");
    ex.textContent = (correct ? "Correct! " : "Not quite. ") + item.explain;
    ex.classList.add("show");
    if (correct && window.GWConfetti) window.GWConfetti({ count: 36, duration: 1200 });
    document.getElementById("quiz-next").style.display = "inline-flex";
  }

  function renderFinal(){
    var pct = Math.round((score / QUESTIONS.length) * 100);
    var msg;
    if (pct >= 90) msg = "Outstanding: you're already thinking like a climate scientist.";
    else if (pct >= 70) msg = "Great work: you've got a solid handle on the basics.";
    else if (pct >= 40) msg = "Good start, a couple more passes through the Learn pages will sharpen this further.";
    else msg = "Nice try! Head back through the Learn section, then come give this another go.";

    mount.innerHTML =
      '<div class="center reveal-auto is-in">' +
      '<p class="eyebrow" style="justify-content:center;">RESULT</p>' +
      '<div class="rb-value mono" style="font-size:2.8rem;font-weight:700;background:var(--grad-teal);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">' + score + ' / ' + QUESTIONS.length + '</div>' +
      '<p style="font-size:1.05rem;max-width:34em;margin:10px auto 24px;">' + msg + '</p>' +
      '<button class="btn btn-primary" id="quiz-restart">Play again</button>' +
      '</div>';
    document.getElementById("quiz-restart").addEventListener("click", function(){ idx = 0; score = 0; render(); });
    if (pct >= 70 && window.GWConfetti) window.GWConfetti({ count: pct >= 90 ? 130 : 80 });
  }

  render();
})();
