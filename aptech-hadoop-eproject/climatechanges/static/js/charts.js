/* Data Explorer charts, figures sourced from NOAA Global Monitoring Laboratory (Mauna Loa
   Observatory annual mean CO2) and NOAA NCEI global climate reports. See source notes on the page. */
(function(){
  "use strict";
  if (typeof Chart === "undefined") return;

  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.color = "#45564E";

  var co2Canvas = document.getElementById("chart-co2");
  if (co2Canvas){
    new Chart(co2Canvas, {
      type: "line",
      data: {
        labels: ["1958","1970","1980","1990","2000","2010","2015","2020","2024","2025"],
        datasets: [{
          label: "Mauna Loa annual mean CO2 (ppm)",
          data: [315.98, 325.68, 338.75, 354.45, 369.71, 389.90, 400.83, 414.24, 424.61, 427.35],
          borderColor: "#0B5560",
          backgroundColor: "rgba(14,92,86,.10)",
          borderWidth: 2.5,
          pointBackgroundColor: "#D9691A",
          pointRadius: 3.5,
          fill: true,
          tension: .35
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { title: { display: true, text: "ppm (parts per million)" }, grid: { color: "#E4ECE2" } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  var warmCanvas = document.getElementById("chart-warm");
  if (warmCanvas){
    new Chart(warmCanvas, {
      type: "bar",
      data: {
        labels: ["2023", "2024 (record)", "2025"],
        datasets: [{
          label: "°C above 20th-century (1901 to 2000) average",
          data: [1.19, 1.29, 1.17],
          backgroundColor: ["#EE8C3C", "#C8432F", "#EE8C3C"],
          borderRadius: 8,
          maxBarThickness: 70
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { title: { display: true, text: "°C anomaly" }, grid: { color: "#E4ECE2" } },
          x: { grid: { display: false } }
        }
      }
    });
  }
})();
