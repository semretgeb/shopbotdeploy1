/* Cart lives in localStorage, keyed by shop slug so two shops never mix. Prices are re-checked server-side. */
window.Cart = (function () {
  const KEY = 'cart:' + (window.API.slug || 'default');
  let items = load(); // {id: {id, name, price_santim, thumb_url, qty, stock}}
  const listeners = [];

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(items)); } catch (e) { /* ignore */ }
    listeners.forEach((fn) => fn());
  }
  function add(p, qty) {
    const cur = items[p.id] || { id: p.id, name: p.name, price_santim: p.price_santim, thumb_url: p.thumb_url, qty: 0, stock: p.stock };
    cur.qty = Math.min(99, cur.qty + (qty || 1));
    if (cur.stock != null) cur.qty = Math.min(cur.qty, cur.stock);
    cur.name = p.name; cur.price_santim = p.price_santim; cur.thumb_url = p.thumb_url; cur.stock = p.stock;
    items[p.id] = cur;
    save();
  }
  function setQty(id, qty) {
    if (!items[id]) return;
    if (qty <= 0) delete items[id]; else items[id].qty = Math.min(99, qty);
    save();
  }
  function remove(id) { delete items[id]; save(); }
  function clear() { items = {}; save(); }
  function list() { return Object.values(items); }
  function count() { return list().reduce((n, i) => n + i.qty, 0); }
  function total() { return list().reduce((n, i) => n + i.qty * i.price_santim, 0); }
  function onChange(fn) { listeners.push(fn); }
  function qtyOf(id) { return items[id] ? items[id].qty : 0; }

  return { add, setQty, remove, clear, list, count, total, onChange, qtyOf };
})();
