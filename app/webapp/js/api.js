/* Fetch wrapper: adds the signed Telegram initData header and the shop slug to every call. */
window.API = (function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const params = new URLSearchParams(location.search);
  // start_param is set for direct Mini App links; ?shop= is what the bot puts in its "Open shop" button.
  const slug = (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) || params.get('shop') || '';
  const initData = (tg && tg.initData) || '';

  class ApiError extends Error {
    constructor(status, code, message) { super(message || code); this.status = status; this.code = code; }
  }

  async function call(method, path, body, isForm) {
    const url = new URL(path, location.origin);
    if (slug) url.searchParams.set('shop', slug);
    const headers = { 'X-Telegram-Init-Data': initData };
    if (body && !isForm) headers['Content-Type'] = 'application/json';
    let res;
    try {
      res = await fetch(url, { method, headers, body: isForm ? body : (body ? JSON.stringify(body) : undefined) });
    } catch (e) {
      throw new ApiError(0, 'network', 'network');
    }
    if (res.status === 204) return null;
    let data = null;
    try { data = await res.json(); } catch (e) { /* non-JSON error body */ }
    if (!res.ok) {
      const d = (data && data.detail) || {};
      throw new ApiError(res.status, d.code || `http_${res.status}`, d.message || (typeof data?.detail === 'string' ? data.detail : ''));
    }
    return data;
  }

  return {
    ApiError, slug, hasInitData: !!initData,
    shop: () => call('GET', '/api/shop'),
    categories: () => call('GET', '/api/categories'),
    products: (q) => call('GET', '/api/products?' + new URLSearchParams(q).toString()),
    product: (id) => call('GET', `/api/products/${id}`),
    me: () => call('GET', '/api/me'),
    saveMe: (body) => call('PUT', '/api/me', body),
    placeOrder: (body) => call('POST', '/api/orders', body),
    orders: () => call('GET', '/api/orders'),
    order: (id) => call('GET', `/api/orders/${id}`),
    uploadProof: (id, file) => { const fd = new FormData(); fd.append('file', file, file.name || 'proof.jpg'); return call('POST', `/api/orders/${id}/proof`, fd, true); },
  };
})();
