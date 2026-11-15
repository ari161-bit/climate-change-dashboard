/* Today's Weather, live, client-side, via Open-Meteo (free, no API key,
   CORS-enabled, CC BY 4.0). Defaults to Ibadan; visitors can search any
   city or use their own location. This is deliberately framed as WEATHER
   (today, one place) rather than CLIMATE (decades, global average), see
   the callout text below the widget. */
(function(){
  "use strict";
  var mount = document.getElementById("weather-mount");
  if (!mount) return;

  var DEFAULT_LOC = { name: "Ibadan, Nigeria", lat: 7.3775, lon: 3.9470 };

  var WMO = {
    0: ["Clear sky", "☀️"], 1: ["Mainly clear", "🌤️"], 2: ["Partly cloudy", "⛅"], 3: ["Overcast", "☁️"],
    45: ["Fog", "🌫️"], 48: ["Freezing fog", "🌫️"],
    51: ["Light drizzle", "🌦️"], 53: ["Drizzle", "🌦️"], 55: ["Dense drizzle", "🌧️"],
    56: ["Light freezing drizzle", "🌧️"], 57: ["Freezing drizzle", "🌧️"],
    61: ["Light rain", "🌦️"], 63: ["Rain", "🌧️"], 65: ["Heavy rain", "🌧️"],
    66: ["Light freezing rain", "🌧️"], 67: ["Freezing rain", "🌧️"],
    71: ["Light snow", "🌨️"], 73: ["Snow", "🌨️"], 75: ["Heavy snow", "❄️"], 77: ["Snow grains", "🌨️"],
    80: ["Light rain showers", "🌦️"], 81: ["Rain showers", "🌧️"], 82: ["Violent showers", "⛈️"],
    85: ["Snow showers", "🌨️"], 86: ["Heavy snow showers", "❄️"],
    95: ["Thunderstorm", "⛈️"], 96: ["Thunderstorm, hail", "⛈️"], 99: ["Thunderstorm, heavy hail", "⛈️"]
  };
  function describe(code){ return WMO[code] || ["Mixed conditions", "🌡️"]; }
  function escapeHtml(s){
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }

  function skeleton(){
    mount.innerHTML =
      '<div class="weather-controls">' +
        '<input type="text" id="weather-search" placeholder="Search a city, e.g. Lagos, Nairobi, London…">' +
        '<button class="btn btn-ghost btn-sm" id="weather-search-btn" type="button">Search</button>' +
        '<button class="btn btn-ghost btn-sm" id="weather-geo-btn" type="button">📍 Use my location</button>' +
      '</div>' +
      '<div id="weather-display" class="weather-loading">Loading today\u2019s weather…</div>';

    document.getElementById("weather-search-btn").addEventListener("click", searchCity);
    document.getElementById("weather-search").addEventListener("keydown", function(e){
      if (e.key === "Enter"){ e.preventDefault(); searchCity(); }
    });
    document.getElementById("weather-geo-btn").addEventListener("click", useMyLocation);
  }

  function showLoading(){
    var el = document.getElementById("weather-display");
    if (el) { el.className = "weather-loading"; el.textContent = "Loading\u2026"; }
  }
  function showError(msg){
    var el = document.getElementById("weather-display");
    if (el) { el.className = "weather-error"; el.textContent = msg; }
  }

  function loadWeather(loc){
    showLoading();
    var url = "https://api.open-meteo.com/v1/forecast?latitude=" + loc.lat +
      "&longitude=" + loc.lon + "&current_weather=true&timezone=auto";
    fetch(url)
      .then(function(r){ if (!r.ok) throw new Error("Weather lookup failed"); return r.json(); })
      .then(function(data){ renderWeather(loc, data); })
      .catch(function(){ showError("Couldn't load weather right now, try again in a moment."); });
  }

  function renderWeather(loc, data){
    var cw = data.current_weather;
    if (!cw){ showError("No current weather available for that location."); return; }
    var d = describe(cw.weathercode);
    var el = document.getElementById("weather-display");
    if (!el) return;
    el.className = "";
    el.innerHTML =
      '<div class="weather-card">' +
        '<div class="weather-top">' +
          '<div><span class="weather-loc">' + escapeHtml(loc.name) + '</span>' +
          '<span class="weather-updated">Updated ' + new Date(cw.time).toLocaleString() + '</span></div>' +
          '<div class="weather-emoji">' + d[1] + '</div>' +
        '</div>' +
        '<div class="weather-temp">' + Math.round(cw.temperature) + '°C</div>' +
        '<div class="weather-desc">' + d[0] + '</div>' +
        '<div class="weather-stats">' +
          '<div class="weather-stat"><span class="ws-l">Wind</span><span class="ws-v">' + Math.round(cw.windspeed) + ' km/h</span></div>' +
          '<div class="weather-stat"><span class="ws-l">Right now</span><span class="ws-v">' + (cw.is_day ? "Daytime" : "Night-time") + '</span></div>' +
        '</div>' +
      '</div>';
  }

  function searchCity(){
    var input = document.getElementById("weather-search");
    var q = (input.value || "").trim();
    if (!q) return;
    showLoading();
    fetch("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + encodeURIComponent(q))
      .then(function(r){ return r.json(); })
      .then(function(data){
        var hit = data && data.results && data.results[0];
        if (!hit){ showError("Couldn't find \u201c" + q + "\u201d, try a different spelling or a bigger nearby city."); return; }
        var name = hit.name + (hit.admin1 ? ", " + hit.admin1 : "") + (hit.country ? ", " + hit.country : "");
        loadWeather({ name: name, lat: hit.latitude, lon: hit.longitude });
      })
      .catch(function(){ showError("City search isn't working right now, try again shortly."); });
  }

  function useMyLocation(){
    if (!navigator.geolocation){ showError("Your browser doesn't support location lookup."); return; }
    showLoading();
    navigator.geolocation.getCurrentPosition(
      function(pos){
        loadWeather({
          name: "Your location",
          lat: pos.coords.latitude.toFixed(3),
          lon: pos.coords.longitude.toFixed(3)
        });
      },
      function(){ showError("Location access was denied or unavailable, showing Ibadan instead."); loadWeather(DEFAULT_LOC); },
      { timeout: 8000 }
    );
  }

  skeleton();
  loadWeather(DEFAULT_LOC);
})();
