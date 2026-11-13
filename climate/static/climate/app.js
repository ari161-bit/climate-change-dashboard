(function(){
  var root = document.documentElement;
  function current(){ return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'; }
  function set(theme){
    if (theme === 'dark') root.setAttribute('data-theme', 'dark'); else root.removeAttribute('data-theme');
    try { localStorage.setItem('es-theme', theme); } catch (e) {}
    var btn = document.getElementById('theme-toggle');
    if (btn) { btn.textContent = theme === 'dark' ? '\u2600' : '\u263E'; btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'); }
    document.dispatchEvent(new CustomEvent('themechange', {detail: theme}));
  }
  document.addEventListener('DOMContentLoaded', function(){
    var btn = document.getElementById('theme-toggle');
    if (btn) { btn.textContent = current() === 'dark' ? '\u2600' : '\u263E'; btn.addEventListener('click', function(){ set(current() === 'dark' ? 'light' : 'dark'); }); }
  });
})();
