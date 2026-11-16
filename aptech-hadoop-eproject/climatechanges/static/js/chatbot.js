(function () {
  var API = '/climatechanges/api/chat/';
  var history = [];
  var busy = false;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; }
  function csrf() { var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/); return m ? decodeURIComponent(m[1]) : ''; }

  var launch = el('button', 'esc-chat-launch');
  launch.type = 'button'; launch.setAttribute('aria-label', 'Open the EarthScape Assistant');
  launch.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.2A8 8 0 1 1 21 12z"/></svg>';

  var panel = el('section', 'esc-chat');
  panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'EarthScape Assistant'); panel.hidden = true;
  var head = el('header', 'esc-chat-head');
  var title = el('div', 'esc-chat-title');
  title.appendChild(el('strong', '', 'EarthScape Assistant'));
  var status = el('span', 'esc-chat-status', 'Ask about climate or this site');
  title.appendChild(status);
  var close = el('button', 'esc-chat-close', '×'); close.type = 'button'; close.setAttribute('aria-label', 'Close chat');
  head.appendChild(title); head.appendChild(close);
  var log = el('div', 'esc-chat-log'); log.setAttribute('aria-live', 'polite');
  var chips = el('div', 'esc-chat-chips');
  ['How much has the world warmed?', 'Are disasters increasing?', 'How do I cut my carbon footprint?', 'What can the console do?'].forEach(function (q) {
    var b = el('button', 'esc-chip', q); b.type = 'button'; b.addEventListener('click', function () { send(q); }); chips.appendChild(b);
  });
  var form = el('form', 'esc-chat-form');
  var input = el('input'); input.type = 'text'; input.maxLength = 500; input.placeholder = 'Type your question…'; input.autocomplete = 'off'; input.setAttribute('aria-label', 'Your question');
  var go = el('button', '', 'Send'); go.type = 'submit';
  form.appendChild(input); form.appendChild(go);
  panel.appendChild(head); panel.appendChild(log); panel.appendChild(chips); panel.appendChild(form);

  function addMsg(role, text) {
    var m = el('div', 'esc-msg esc-' + role);
    text.split(/(\/climatechanges\/[\w\-\/\.]+)/).forEach(function (part) {
      if (/^\/climatechanges\//.test(part)) { var a = el('a', '', part); a.href = part.replace(/[.,)]+$/, ''); m.appendChild(a); }
      else m.appendChild(document.createTextNode(part));
    });
    log.appendChild(m); log.scrollTop = log.scrollHeight; return m;
  }

  function send(text) {
    text = (text || '').trim();
    if (!text || busy) return;
    busy = true; chips.hidden = true; input.value = '';
    addMsg('user', text); history.push({ role: 'user', content: text });
    var wait = addMsg('bot', 'Thinking…'); wait.classList.add('esc-wait');
    fetch(API, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify({ messages: history.slice(-6), page: /\/alerts\//.test(location.pathname) ? 'alerts' : (/support/.test(location.pathname) ? 'support' : '') }) })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (r) {
        wait.remove();
        var reply = r.ok && r.d.reply ? r.d.reply : (r.d.error || 'Sorry, something went wrong. Please try again.');
        addMsg('bot', reply); history.push({ role: 'assistant', content: reply });
      })
      .catch(function () { wait.remove(); addMsg('bot', 'I could not reach the server. Please check your connection and try again.'); })
      .then(function () { busy = false; input.focus(); });
  }

  function toggle(open) {
    panel.hidden = !open; launch.classList.toggle('esc-on', open);
    if (open) { input.focus(); if (!log.children.length) addMsg('bot', 'Hi! I’m the EarthScape Assistant. Ask me about global warming, our data, or how to use this site.'); }
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-chat-ask]');
    if (!t) return;
    e.preventDefault(); toggle(true); var q = t.getAttribute('data-chat-ask'); if (q) send(q);
  });
  launch.addEventListener('click', function () { toggle(panel.hidden); });
  close.addEventListener('click', function () { toggle(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden) toggle(false); });
  form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });

  function mount() {
    document.body.appendChild(launch); document.body.appendChild(panel);
    fetch(API, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) { status.textContent = d.ai ? 'AI assistant · online' : 'Quick answers from our data'; }).catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
