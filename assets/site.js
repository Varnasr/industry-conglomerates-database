/* Header controls shared by every page: the theme button, the Display menu
   (theme and reading font) and, on a phone, the Menu button for the links.
   The choices live in localStorage under ind.theme and reading-font, the same
   key the other ImpactMojo sites use for OpenDyslexic. A small inline script in
   each page's <head> applies both before first paint, so nothing flashes. */
(function () {
  'use strict';
  var root = document.documentElement;
  var mq = window.matchMedia ? matchMedia('(prefers-color-scheme: dark)') : null;

  function get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }
  function set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (_) {} }

  function themeChoice() { var t = get('ind.theme'); return t === 'dark' || t === 'light' ? t : 'system'; }
  function isDark() {
    var t = root.getAttribute('data-theme');
    return t ? t === 'dark' : !!(mq && mq.matches);
  }
  function applyTheme(choice) {
    if (choice === 'system') { root.removeAttribute('data-theme'); set('ind.theme', null); }
    else { root.setAttribute('data-theme', choice); set('ind.theme', choice); }
    sync();
    document.dispatchEvent(new CustomEvent('themechange', { detail: { dark: isDark() } }));
  }
  function applyFont(on) {
    root.classList.toggle('dyslexic-font', on);
    set('reading-font', on ? 'opendyslexic' : null);
    sync();
  }

  var themeBtn = document.getElementById('themeBtn');
  var displayBtn = document.getElementById('displayBtn');
  var panel = document.getElementById('displayPanel');
  var menuBtn = document.getElementById('menuBtn');
  var nav = document.getElementById('siteNav');

  function sync() {
    var dark = isDark();
    if (themeBtn) {
      themeBtn.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
      themeBtn.setAttribute('aria-pressed', String(dark));
      themeBtn.querySelector('.tool-l').textContent = dark ? 'Dark' : 'Light';
    }
    if (panel) {
      var c = themeChoice(), f = root.classList.contains('dyslexic-font') ? 'dyslexic' : 'standard';
      panel.querySelectorAll('[data-theme-choice]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-theme-choice') === c)); });
      panel.querySelectorAll('[data-font-choice]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-font-choice') === f)); });
    }
  }

  if (themeBtn) themeBtn.addEventListener('click', function () { applyTheme(isDark() ? 'light' : 'dark'); });

  function closePanel(focusBack) {
    if (!panel || panel.hidden) return;
    panel.hidden = true; displayBtn.setAttribute('aria-expanded', 'false');
    if (focusBack) displayBtn.focus();
  }
  function closeMenu(focusBack) {
    if (!nav || !nav.classList.contains('open')) return;
    nav.classList.remove('open'); menuBtn.setAttribute('aria-expanded', 'false');
    if (focusBack) menuBtn.focus();
  }
  if (displayBtn && panel) {
    displayBtn.addEventListener('click', function () {
      var open = panel.hidden;
      closeMenu(false);
      panel.hidden = !open; displayBtn.setAttribute('aria-expanded', String(open));
      if (open) { var first = panel.querySelector('button[aria-pressed="true"]') || panel.querySelector('button'); if (first) first.focus(); }
    });
    panel.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      if (b.hasAttribute('data-theme-choice')) applyTheme(b.getAttribute('data-theme-choice'));
      if (b.hasAttribute('data-font-choice')) applyFont(b.getAttribute('data-font-choice') === 'dyslexic');
      if (b.hasAttribute('data-close')) closePanel(true);
    });
  }
  if (menuBtn && nav) {
    menuBtn.addEventListener('click', function () {
      var open = !nav.classList.contains('open');
      closePanel(false);
      nav.classList.toggle('open', open); menuBtn.setAttribute('aria-expanded', String(open));
    });
  }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closePanel(true); closeMenu(true); } });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.top')) { closePanel(false); closeMenu(false); }
  });
  if (mq && mq.addEventListener) mq.addEventListener('change', function () {
    if (themeChoice() === 'system') { sync(); document.dispatchEvent(new CustomEvent('themechange', { detail: { dark: isDark() } })); }
  });

  var y = document.getElementById('copyrightYear');
  if (y) y.textContent = new Date().getFullYear();
  sync();
})();
