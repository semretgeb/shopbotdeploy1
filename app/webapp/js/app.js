/* Hash router + screen controllers. Routes: #/ #/p/:id #/cart #/checkout #/done/:orderId #/orders */
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const t = (k, v) => window.I18N.t(k, v);
  const price = (s) => window.I18N.price(s);
  const S = { shop: null, categories: [], products: [], page: 0, hasMore: false, category: null, query: '', loading: false, me: null, lastOrder: null };

  // ---- Telegram SDK glue ------------------------------------------------------
  function tgReady() {
    if (!tg) return;
    tg.ready(); tg.expand();
    try { tg.setHeaderColor('bg_color'); tg.setBackgroundColor('secondary_bg_color'); } catch (e) { /* older clients */ }
    tg.onEvent('themeChanged', () => { /* CSS vars update automatically */ });
    tg.BackButton.onClick(() => history.back());
    tg.MainButton.onClick(() => { if (S.mainAction) S.mainAction(); });
  }
  function haptic(kind) { try { tg && tg.HapticFeedback.impactOccurred(kind || 'light'); } catch (e) { /* ignore */ } }
  function setBack(show) { if (!tg) return; show ? tg.BackButton.show() : tg.BackButton.hide(); }
  function setMain(text, action, opts) {
    S.mainAction = action;
    if (!tg) return;
    if (!text) { tg.MainButton.hide(); return; }
    tg.MainButton.setParams({ text, is_visible: true, is_active: !(opts && opts.disabled) });
    if (opts && opts.loading) tg.MainButton.showProgress(true); else tg.MainButton.hideProgress();
  }
  function go(hash) { location.hash = hash; }

  // ---- cart bar ---------------------------------------------------------------
  function updateCartBar() {
    const bar = document.getElementById('cart-bar');
    const n = window.Cart.count();
    const route = location.hash.split('/')[1] || '';
    const showOn = ['', 'p'];
    if (n === 0 || !showOn.includes(route)) { bar.hidden = true; return; }
    bar.hidden = false;
    document.getElementById('cart-bar-text').textContent = `🛒 ${t('app.items_n', { n })} · ${price(window.Cart.total())}`;
    document.getElementById('cart-bar-cta').textContent = t('app.view_cart') + ' →';
  }

  // ---- screens ----------------------------------------------------------------
  async function loadProducts(reset) {
    if (S.loading) return;
    S.loading = true;
    if (reset) { S.page = 0; S.products = []; }
    try {
      const q = { page: S.page };
      if (S.category != null) q.category_id = S.category;
      if (S.query) q.q = S.query;
      const data = await window.API.products(q);
      S.products = reset ? data.items : S.products.concat(data.items);
      S.hasMore = data.has_more;
      S.loading = false;
      if (reset) window.UI.renderHome(S); else { window.UI.appendProducts(data.items); const m = document.getElementById('more'); if (m && !S.hasMore) m.remove(); }
      bindHome();
    } catch (e) { S.loading = false; handleError(e, () => loadProducts(true)); }
  }

  function bindHome() {
    const v = document.getElementById('view');
    v.onclick = (ev) => {
      const add = ev.target.closest('[data-add]');
      if (add) { ev.stopPropagation(); const p = S.products.find((x) => x.id === +add.dataset.add); if (p) { window.Cart.add(p, 1); haptic(); window.UI.toast(t('app.added')); } return; }
      const card = ev.target.closest('.card[data-id]');
      if (card) { go(`#/p/${card.dataset.id}`); return; }
      const chip = ev.target.closest('[data-cat]');
      if (chip) { S.category = chip.dataset.cat === '' ? null : +chip.dataset.cat; loadProducts(true); return; }
      if (ev.target.id === 'more') { S.page += 1; loadProducts(false); }
    };
    const search = document.getElementById('search');
    if (search) {
      let timer;
      search.oninput = () => { clearTimeout(timer); timer = setTimeout(() => { S.query = search.value.trim(); loadProducts(true); }, 350); };
      search.onkeydown = (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); search.blur(); } };
    }
  }

  async function showHome() {
    setBack(false); setMain(null);
    if (S.products.length && !S.query && S.category == null) { window.UI.renderHome(S); bindHome(); return; }
    window.UI.skeleton();
    try {
      if (!S.categories.length) S.categories = await window.API.categories();
      await loadProducts(true);
    } catch (e) { handleError(e, showHome); }
  }

  async function showDetail(id) {
    setBack(true); setMain(null);
    let p = S.products.find((x) => x.id === +id);
    try {
      if (!p) { window.UI.skeleton(); p = await window.API.product(id); }
    } catch (e) { return handleError(e, () => showDetail(id)); }
    let qty = 1;
    window.UI.renderDetail(p, qty);
    const v = document.getElementById('view');
    const refresh = () => {
      const q = document.getElementById('qty'); if (q) q.textContent = qty;
      const tot = document.getElementById('add-total'); if (tot) tot.textContent = price(p.price_santim * qty);
    };
    v.onclick = (ev) => {
      const step = ev.target.closest('[data-step]');
      if (step) { qty = Math.max(1, Math.min(p.stock != null ? p.stock : 99, qty + (+step.dataset.step))); refresh(); haptic(); return; }
      if (ev.target.closest('#add-btn')) { window.Cart.add(p, qty); haptic('medium'); window.UI.toast(t('app.added')); go('#/'); }
    };
  }

  function showCart() {
    setBack(true);
    const items = window.Cart.list();
    window.UI.renderCart(items, window.Cart.total(), S.shop);
    setMain(items.length ? `${t('app.checkout')} · ${price(window.Cart.total())}` : null, () => go('#/checkout'));
    const v = document.getElementById('view');
    v.onclick = (ev) => {
      const step = ev.target.closest('[data-step]');
      if (step) { window.Cart.setQty(+step.dataset.id, window.Cart.qtyOf(+step.dataset.id) + (+step.dataset.step)); haptic(); showCart(); return; }
      const rm = ev.target.closest('[data-remove]');
      if (rm) { window.Cart.remove(+rm.dataset.remove); showCart(); return; }
      if (ev.target.id === 'checkout') go('#/checkout');
      if (ev.target.id === 'browse') go('#/');
    };
  }

  async function showCheckout() {
    setBack(true); setMain(null);
    const items = window.Cart.list();
    if (!items.length) return go('#/cart');
    if (!S.me) { try { S.me = await window.API.me(); } catch (e) { S.me = {}; } }
    window.UI.renderCheckout(items, window.Cart.total(), S.me, S.shop);
    const form = document.getElementById('checkout-form');
    const submit = async () => {
      const val = (id) => (document.getElementById(id).value || '').trim();
      let ok = true;
      ['full_name', 'phone', 'address'].forEach((id) => { const bad = val(id).length < (id === 'address' ? 3 : 2); window.UI.setFieldError(id, bad ? t('app.required') : ''); if (bad) ok = false; });
      if (ok && val('phone').replace(/[^\d+]/g, '').replace(/^\+/, '').length < 7) { window.UI.setFieldError('phone', t('app.invalid_phone')); ok = false; }
      if (!ok) { haptic('heavy'); return; }
      const body = {
        items: items.map((i) => ({ product_id: i.id, qty: i.qty })),
        full_name: val('full_name'), phone: val('phone'), address: val('address'), note: val('note') || null,
        payment_method: (form.querySelector('input[name=pm]:checked') || {}).value || 'cod', save_details: true,
      };
      const btn = document.getElementById('place');
      btn.disabled = true; btn.textContent = t('app.placing'); setMain(t('app.placing'), null, { loading: true, disabled: true });
      try {
        const order = await window.API.placeOrder(body);
        S.lastOrder = order; S.me = { full_name: body.full_name, phone: body.phone, address: body.address };
        window.Cart.clear(); haptic('medium');
        S.products = []; // stock changed; refetch next time
        location.replace(`#/done/${order.id}`);
      } catch (e) {
        btn.disabled = false; btn.textContent = `${t('app.place_order')} · ${price(window.Cart.total())}`;
        setMain(`${t('app.place_order')} · ${price(window.Cart.total())}`, submit);
        if (e.code === 'out_of_stock' || e.code === 'product_unavailable') { window.UI.toast(e.message || e.code, 2500); S.products = []; }
        else handleError(e, null, true);
      }
    };
    form.onsubmit = (ev) => { ev.preventDefault(); submit(); };
    setMain(`${t('app.place_order')} · ${price(window.Cart.total())}`, submit);
  }

  async function showDone(orderId) {
    setBack(false); setMain(null);
    let o = S.lastOrder && S.lastOrder.id === +orderId ? S.lastOrder : null;
    try { if (!o) { window.UI.skeleton(); o = await window.API.order(orderId); } } catch (e) { return handleError(e, () => showDone(orderId)); }
    window.UI.renderConfirmation(o, S.shop);
    const v = document.getElementById('view');
    v.onclick = async (ev) => {
      if (ev.target.id === 'track') { tg ? tg.close() : go('#/'); return; }
      if (ev.target.id === 'continue' || ev.target.id === 'later') { go('#/'); return; }
      if (ev.target.id === 'proof-btn') { document.getElementById('proof').click(); return; }
      if (ev.target.id === 'payinfo') { try { await navigator.clipboard.writeText(ev.target.textContent); window.UI.toast(t('app.copied')); } catch (e) { /* no clipboard */ } }
    };
    const input = document.getElementById('proof');
    if (input) input.onchange = async () => {
      const file = input.files[0]; if (!file) return;
      if (file.size > 5 * 1024 * 1024) { window.UI.toast(t('app.proof_hint'), 2500); return; }
      const btn = document.getElementById('proof-btn'); btn.disabled = true; btn.textContent = t('app.uploading');
      try {
        await window.API.uploadProof(o.id, file);
        o.has_proof = true; S.lastOrder = o; haptic('medium');
        showDone(orderId);
        window.UI.toast(t('app.proof_sent'), 2500);
      } catch (e) { btn.disabled = false; btn.textContent = t('app.upload_proof'); window.UI.toast(e.message || t('app.offline'), 2500); }
    };
  }

  async function showOrders() {
    setBack(true); setMain(null); window.UI.skeleton();
    try {
      const orders = await window.API.orders();
      window.UI.renderOrders(orders);
      document.getElementById('view').onclick = (ev) => { const el = ev.target.closest('[data-order]'); if (el) go(`#/done/${el.dataset.order}`); };
    } catch (e) { handleError(e, showOrders); }
  }

  // ---- errors & routing ---------------------------------------------------------
  function handleError(e, retry, toastOnly) {
    if (e && e.code === 'shop_paused' && S.shop) { S.shop.is_open = false; window.UI.renderClosed(S.shop); setMain(null); return; }
    const msg = e && e.status === 401 ? t('app.not_in_telegram') : (e && e.code === 'network' ? t('app.offline') : (e && e.message) || t('app.offline'));
    if (toastOnly) { window.UI.toast(msg, 2500); return; }
    window.UI.renderError(msg, !!retry);
    const r = document.getElementById('retry'); if (r && retry) r.onclick = retry;
  }

  function route() {
    updateCartBar();
    if (!S.shop) return;
    if (!S.shop.is_open) { window.UI.renderClosed(S.shop); setMain(null); return; }
    const parts = location.hash.replace(/^#\/?/, '').split('/');
    switch (parts[0]) {
      case 'p': return showDetail(parts[1]);
      case 'cart': return showCart();
      case 'checkout': return showCheckout();
      case 'done': return showDone(parts[1]);
      case 'orders': return showOrders();
      default: return showHome();
    }
  }

  async function switchLang() {
    const next = window.I18N.lang === 'am' ? 'en' : 'am';
    await window.I18N.load(next);
    document.getElementById('btn-lang').textContent = next === 'am' ? 'EN' : 'አማ';
    try { await window.API.saveMe({ lang: next }); } catch (e) { /* offline is fine */ }
    S.products = []; S.categories = []; // price_text is language-dependent
    route();
  }

  async function boot() {
    tgReady();
    const lang = window.I18N.saved() || ((tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code) === 'en' ? 'en' : 'am');
    await window.I18N.load(lang);
    document.getElementById('btn-lang').textContent = lang === 'am' ? 'EN' : 'አማ';
    document.getElementById('btn-lang').onclick = switchLang;
    document.getElementById('btn-orders').onclick = () => go('#/orders');
    document.getElementById('cart-bar').onclick = () => go('#/cart');
    window.Cart.onChange(updateCartBar);
    window.addEventListener('hashchange', route);
    if (!window.API.hasInitData) { window.UI.renderError(t('app.not_in_telegram')); return; }
    window.UI.skeleton();
    try {
      S.shop = await window.API.shop();
      if (S.shop.lang && S.shop.lang !== window.I18N.lang && !window.I18N.saved()) { await window.I18N.load(S.shop.lang); document.getElementById('btn-lang').textContent = S.shop.lang === 'am' ? 'EN' : 'አማ'; }
      document.getElementById('shop-name').textContent = S.shop.name;
      document.getElementById('shop-name').classList.remove('skeleton-text');
      document.getElementById('shop-desc').textContent = S.shop.description || '';
      document.getElementById('btn-orders').hidden = false;
      document.title = S.shop.name;
      route();
    } catch (e) { handleError(e, boot); }
  }

  boot();
})();
