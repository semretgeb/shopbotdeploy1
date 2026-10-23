/* Small DOM helpers + screen renderers. Each render* returns nothing and fills #view. */
window.UI = (function () {
  const t = (k, v) => window.I18N.t(k, v);
  const price = (s) => window.I18N.price(s);
  const view = () => document.getElementById('view');
  const PLACEHOLDER = 'img/placeholder.svg';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function h(html) { const tpl = document.createElement('template'); tpl.innerHTML = html.trim(); return tpl.content; }
  function set(html) { const v = view(); v.innerHTML = ''; v.append(h(html)); v.scrollTop = 0; window.scrollTo(0, 0); }
  function toast(msg, ms) {
    const el = document.getElementById('toast');
    el.textContent = msg; el.hidden = false;
    clearTimeout(el._t); el._t = setTimeout(() => { el.hidden = true; }, ms || 1600);
  }
  function skeleton() { set(document.getElementById('tpl-skeleton').innerHTML); }

  function img(src, cls) {
    return `<img src="${esc(src || PLACEHOLDER)}" loading="lazy" decoding="async" alt="" ${cls ? `class="${cls}"` : ''} onerror="this.onerror=null;this.src='${PLACEHOLDER}'">`;
  }

  // ---- storefront -----------------------------------------------------------
  function productCard(p) {
    const oos = !p.in_stock;
    const badge = oos ? `<span class="badge">${esc(t('app.out_of_stock'))}</span>`
      : (p.stock != null && p.stock <= 5 ? `<span class="badge">${esc(t('app.left_n', { n: p.stock }))}</span>` : '');
    return `<div class="card ${oos ? 'oos' : ''}" data-id="${p.id}" role="button" tabindex="0">
      <div class="ph">${img(p.thumb_url)}</div>${badge}
      <div class="body"><div class="name">${esc(p.name)}</div><div class="price">${esc(price(p.price_santim))}</div></div>
      ${oos ? '' : `<button class="add" data-add="${p.id}" aria-label="${esc(t('app.add_to_cart'))}">+</button>`}
    </div>`;
  }

  function renderHome(state) {
    const chips = [`<button class="chip ${state.category == null ? 'active' : ''}" data-cat="">${esc(t('app.all'))}</button>`]
      .concat(state.categories.map((c) => `<button class="chip ${state.category === c.id ? 'active' : ''}" data-cat="${c.id}">${esc(c.name)} <span class="muted">${c.count}</span></button>`))
      .join('');
    set(`
      <input class="search" id="search" type="search" placeholder="${esc(t('app.search'))}" value="${esc(state.query || '')}" autocomplete="off">
      <div class="chips">${chips}</div>
      <div class="grid" id="grid">${state.products.map(productCard).join('')}</div>
      ${state.products.length === 0 && !state.loading ? `<div class="empty"><span class="big">🧺</span>${esc(t('app.no_products'))}</div>` : ''}
      ${state.hasMore ? `<button class="btn secondary" id="more" style="margin-top:12px">${esc(t('app.load_more'))}</button>` : ''}
    `);
  }

  function appendProducts(products) {
    const grid = document.getElementById('grid');
    if (grid) grid.append(h(products.map(productCard).join('')));
  }

  function renderDetail(p, qty) {
    const oos = !p.in_stock;
    set(`
      <div class="detail-ph">${img(p.image_url)}</div>
      <div class="section">
        <h1 class="detail-name">${esc(p.name)}</h1>
        <div class="detail-price">${esc(price(p.price_santim))}</div>
        <div class="muted">${oos ? esc(t('app.out_of_stock')) : (p.stock != null ? esc(t('app.left_n', { n: p.stock })) : '')}</div>
        ${p.description ? `<p class="detail-desc">${esc(p.description)}</p>` : ''}
      </div>
      ${oos ? '' : `<div class="section row"><span>${esc(t('app.qty'))}</span>
        <div class="stepper"><button data-step="-1" aria-label="-">−</button><span id="qty">${qty}</span><button data-step="1" aria-label="+">+</button></div></div>
      <button class="btn" id="add-btn">${esc(t('app.add_to_cart'))} · <span id="add-total">${esc(price(p.price_santim * qty))}</span></button>`}
    `);
  }

  // ---- cart / checkout ------------------------------------------------------
  function cartLine(i) {
    return `<div class="line" data-id="${i.id}">
      ${img(i.thumb_url)}
      <div><div class="lname">${esc(i.name)}</div><div class="lprice">${esc(price(i.price_santim))} × ${i.qty} = <b>${esc(price(i.price_santim * i.qty))}</b></div>
        <button class="remove" data-remove="${i.id}">${esc(t('app.remove'))}</button></div>
      <div class="stepper"><button data-step="-1" data-id="${i.id}">−</button><span>${i.qty}</span><button data-step="1" data-id="${i.id}">+</button></div>
    </div>`;
  }

  function renderCart(items, total, shop) {
    if (items.length === 0) {
      set(`<div class="empty"><span class="big">🧺</span>${esc(t('app.cart_empty'))}<br><br><button class="btn small" id="browse">${esc(t('app.browse'))}</button></div>`);
      return;
    }
    set(`
      <div class="section">${items.map(cartLine).join('')}
        <div class="total-row"><span>${esc(t('app.subtotal'))}</span><span>${esc(price(total))}</span></div></div>
      ${shop.delivery_info ? `<div class="section muted">${esc(t('app.delivery_note', { delivery: shop.delivery_info }))}</div>` : ''}
      <button class="btn" id="checkout">${esc(t('app.checkout'))}</button>
    `);
  }

  function field(id, label, value, type, required) {
    const tag = type === 'textarea' ? `<textarea id="${id}" ${required ? 'required' : ''}>${esc(value || '')}</textarea>`
      : `<input id="${id}" type="${type || 'text'}" value="${esc(value || '')}" ${required ? 'required' : ''} ${type === 'tel' ? 'inputmode="tel" autocomplete="tel"' : ''}>`;
    return `<div class="field" id="f-${id}"><label for="${id}">${esc(label)}</label>${tag}<div class="err"></div></div>`;
  }

  function renderCheckout(items, total, me, shop) {
    set(`
      <form id="checkout-form" novalidate>
        <div class="section"><h2>${esc(t('app.your_details'))}</h2>
          ${field('full_name', t('app.full_name'), me.full_name, 'text', true)}
          ${field('phone', t('app.phone'), me.phone, 'tel', true)}
          ${field('address', t('app.address'), me.address, 'textarea', true)}
          ${field('note', t('app.note'), '', 'textarea', false)}
        </div>
        <div class="section"><h2>${esc(t('app.payment'))}</h2>
          <label class="radio"><input type="radio" name="pm" value="cod" checked> ${esc(t('app.pay_cod'))}</label>
          ${shop.payment_info ? `<label class="radio"><input type="radio" name="pm" value="transfer"> ${esc(t('app.pay_transfer'))}</label>` : ''}
        </div>
        <div class="section"><h2>${esc(t('app.summary'))}</h2>
          ${items.map((i) => `<div class="row"><span>${esc(i.name)} × ${i.qty}</span><span>${esc(price(i.price_santim * i.qty))}</span></div>`).join('')}
          <div class="total-row"><span>${esc(t('app.total'))}</span><span>${esc(price(total))}</span></div>
          ${shop.delivery_info ? `<div class="muted" style="margin-top:6px">${esc(t('app.delivery_note', { delivery: shop.delivery_info }))}</div>` : ''}
        </div>
        <button class="btn" id="place" type="submit">${esc(t('app.place_order'))} · ${esc(price(total))}</button>
      </form>
    `);
  }

  function setFieldError(id, msg) {
    const f = document.getElementById('f-' + id);
    if (!f) return;
    f.classList.toggle('invalid', !!msg);
    f.querySelector('.err').textContent = msg || '';
  }

  // ---- after the order ------------------------------------------------------
  function statusBadge(s) { return `<span class="status ${esc(s)}">${esc(t('order.status_' + s))}</span>`; }

  function renderConfirmation(o, shop) {
    const transfer = o.payment_method === 'transfer';
    set(`
      <div class="big-check">✅</div>
      <h1 class="center" style="margin:0 0 4px">${esc(t('app.order_received'))}</h1>
      <p class="center muted" style="margin:0 0 14px">${esc(t('app.order_code', { code: o.code }))} · ${statusBadge(o.status)}</p>
      ${transfer ? `<div class="section">
          <h2>${esc(t('app.payment'))}</h2>
          <div>${esc(t('app.transfer_to'))}</div>
          <div class="copybox" id="payinfo">${esc(o.payment_info || shop.payment_info || '')}</div>
          <div class="row"><span>${esc(t('app.amount'))}</span><b>${esc(o.total_text)}</b></div>
          <div style="margin-top:12px">
            ${o.has_proof ? `<div class="muted">${esc(t('app.proof_sent'))}</div>` : `
            <input type="file" id="proof" accept="image/*" hidden>
            <button class="btn" id="proof-btn" type="button">${esc(t('app.upload_proof'))}</button>
            <div class="muted center" style="margin-top:6px">${esc(t('app.proof_hint'))}</div>
            <button class="btn ghost" id="later" type="button">${esc(t('app.upload_later'))}</button>`}
          </div>
        </div>` : `<div class="section center muted">${esc(t('app.shop_will_confirm'))}</div>`}
      <div class="section"><h2>${esc(t('app.summary'))}</h2>
        ${o.items.map((i) => `<div class="row"><span>${esc(i.name)} × ${i.qty}</span><span>${esc(i.line_total_text)}</span></div>`).join('')}
        <div class="total-row"><span>${esc(t('app.total'))}</span><span>${esc(o.total_text)}</span></div></div>
      <button class="btn" id="track">${esc(t('app.track_in_chat'))}</button>
      <button class="btn secondary" id="continue">${esc(t('app.continue_shopping'))}</button>
    `);
  }

  function renderOrders(orders) {
    if (orders.length === 0) { set(`<div class="empty"><span class="big">🧾</span>${esc(t('app.no_orders'))}</div>`); return; }
    set(orders.map((o) => `
      <div class="section" data-order="${o.id}" role="button">
        <div class="row"><b>${esc(t('app.order_code', { code: o.code }))}</b>${statusBadge(o.status)}</div>
        <div class="muted" style="margin-top:6px">${o.items.map((i) => `${esc(i.name)} × ${i.qty}`).join(', ')}</div>
        <div class="row" style="margin-top:6px"><span class="muted">${new Date(o.created_at).toLocaleDateString()}</span><b>${esc(o.total_text)}</b></div>
      </div>`).join(''));
  }

  function renderClosed(shop) {
    set(`<div class="empty"><span class="big">⏸</span><b>${esc(t('app.closed_title'))}</b><br>${esc(t('app.closed_text', { shop: shop.name }))}
      ${shop.phone ? `<br><br><a class="btn small" href="tel:${esc(shop.phone)}">${esc(t('app.contact'))}</a>` : ''}</div>`);
  }

  function renderError(msg, retry) {
    set(`<div class="empty"><span class="big">😕</span><b>${esc(t('app.error_title'))}</b><br>${esc(msg || t('app.offline'))}
      ${retry ? `<br><br><button class="btn small" id="retry">${esc(t('app.retry'))}</button>` : ''}</div>`);
  }

  return { esc, set, toast, skeleton, renderHome, appendProducts, renderDetail, renderCart, renderCheckout, setFieldError,
    renderConfirmation, renderOrders, renderClosed, renderError };
})();
