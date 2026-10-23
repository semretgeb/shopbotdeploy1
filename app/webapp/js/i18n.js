/* Translations come from the same JSON files the bot uses (GET /api/i18n/{lang}). */
window.I18N = (function () {
  let dict = {};
  let lang = 'am';

  async function load(l) {
    lang = l === 'en' ? 'en' : 'am';
    const res = await fetch(`/api/i18n/${lang}`, { cache: 'force-cache' });
    dict = res.ok ? await res.json() : {};
    document.documentElement.lang = lang;
    try { localStorage.setItem('lang', lang); } catch (e) { /* storage may be unavailable */ }
  }

  function t(key, vars) {
    let s = dict[key] || key;
    if (vars) for (const k in vars) s = s.split(`{${k}}`).join(vars[k]);
    return s;
  }

  function price(santim) {
    const birr = Math.floor(Math.abs(santim) / 100);
    const rest = Math.abs(santim) % 100;
    let num = birr.toLocaleString('en-US');
    if (rest) num += '.' + String(rest).padStart(2, '0');
    if (santim < 0) num = '-' + num;
    return lang === 'am' ? `${num} ብር` : `ETB ${num}`;
  }

  function saved() {
    try { return localStorage.getItem('lang'); } catch (e) { return null; }
  }

  return { load, t, price, saved, get lang() { return lang; } };
})();
