/* Carbon footprint mini-calculator, simplified educational estimate, not a precise audit */
(function(){
  "use strict";
  var form = document.getElementById("footprint-form");
  if (!form) return;

  var distanceInput = document.getElementById("cf-distance");
  var distanceOut = document.getElementById("cf-distance-val");
  var resultBox = document.getElementById("cf-result");
  var resultValue = document.getElementById("cf-result-value");
  var resultBar = document.getElementById("cf-result-bar");
  var resultNote = document.getElementById("cf-result-note");

  var TRANSPORT_FACTORS = { // kg CO2 per km
    car_petrol: 0.18,
    car_diesel: 0.17,
    motorcycle: 0.09,
    bus: 0.07,
    walk_cycle: 0.0
  };
  var FLIGHT_T = { none: 0, short: 0.5, long: 1.8 };
  var ELEC_T = { low: 0.3, medium: 0.8, high: 1.6 };
  var GEN_T = { none: 0, occasional: 0.3, frequent: 0.9 };
  var DIET_T = { plant: 0.9, balanced: 1.6, meat: 2.3 };

  function getRadio(name){
    var el = form.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : null;
  }

  function calc(){
    distanceOut.textContent = distanceInput.value;

    var mode = form.transport_mode.value;
    var weeklyKm = parseFloat(distanceInput.value || "0");
    var transportT = (TRANSPORT_FACTORS[mode] * weeklyKm * 52) / 1000;

    var flight = getRadio("flights") || "none";
    var elec = form.electricity.value;
    var gen = getRadio("generator") || "none";
    var diet = getRadio("diet") || "balanced";

    var total = transportT + FLIGHT_T[flight] + ELEC_T[elec] + GEN_T[gen] + DIET_T[diet];
    return Math.max(0.1, total);
  }

  var WORLD_AVG = 4.7; // tCO2e per person per year, illustrative global average used for comparison only

  function render(){
    var total = calc();
    resultValue.textContent = total.toFixed(1);
    var pct = Math.min(100, (total / (WORLD_AVG * 1.6)) * 100);
    resultBar.style.width = pct + "%";

    var note;
    if (total < WORLD_AVG * 0.6){
      note = "That's well below the rough global average of about " + WORLD_AVG + " t: your habits are already doing a lot of the work other people's lifestyles add back.";
    } else if (total < WORLD_AVG * 1.05){
      note = "That's close to the rough global average of about " + WORLD_AVG + " t CO2e per person per year. Small shifts in transport or electricity use move this number more than almost anything else.";
    } else {
      note = "That's above the rough global average of about " + WORLD_AVG + " t. Flights, generator use and daily transport distance tend to move this number the most; see which one of yours is the biggest slice.";
    }
    resultNote.textContent = note;
    resultBox.style.display = "block";
    resultValue.style.animation = "none";
    void resultValue.offsetWidth; /* restart the pop */
    resultValue.style.animation = "quiz-correct .4s var(--ease-spring)";
  }

  form.addEventListener("input", render);
  form.addEventListener("change", render);
  distanceInput.addEventListener("input", function(){ distanceOut.textContent = distanceInput.value; });

  render();
})();
