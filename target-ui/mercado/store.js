(() => {
  'use strict';

  const PRODUCTS = [
    { id: 'mochila-andina', name: 'Mochila Andina', category: 'trekking', categoryLabel: 'Trekking', price: 39990, image: 'assets/mochila.jpg', description: 'Espalda ventilada, bolsillos de mapa y una jornada completa sin cargar de más.' },
    { id: 'termo-austral', name: 'Termo Austral', category: 'campamento', categoryLabel: 'Campamento', price: 18990, image: 'assets/termo.jpg', description: 'Acero de doble pared para café de madrugada y agua para el regreso.' },
    { id: 'parlante-pacifico', name: 'Parlante Pacífico', category: 'audio', categoryLabel: 'Audio de ruta', price: 24990, image: 'assets/parlante.jpg', description: 'Sonido compacto para el refugio, con una historia de producto bien simple.' }
  ];
  const PRICE = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });
  const STANDARD_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];
  const LAB_METHODS = new Set(['GET', 'POST', 'PUT']);
  const MAX_RESPONSE = 12000;
  const VIEW_HASHES = { home: '#inicio', catalog: '#catalogo', orders: '#pedidos', account: '#cuenta', support: '#soporte', challenges: '#retos', admin: '#administracion' };
  const state = {
    catalog: { families: [], missions: [] },
    contexts: { families: {} },
    selectedFamily: 'all',
    selectedMission: null,
    challengeQuery: '',
    productQuery: '',
    category: 'all',
    cart: new Map(),
    currentView: 'home',
    toastTimer: null,
    cartReturnFocus: null
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const text = (value, fallback = '') => value === null || value === undefined ? fallback : String(value);
  const safeJson = (value, fallback = '') => {
    if (value === null || value === undefined || value === '') return fallback;
    try { return JSON.stringify(value, null, 2); } catch (_) { return text(value, fallback); }
  };
  const familyContext = (id) => state.contexts.families[id] || { title: id || 'Área sin nombre', area: 'Taller', summary: 'Contexto local del catálogo.', ctaMission: '' };
  const familyId = (mission) => text(mission && (mission.family || mission.family_id || mission.familyId));
  const formatPrice = (value) => PRICE.format(Number(value) || 0);
  const escapeHtml = (value) => text(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));

  function showToast(message) {
    const node = $('#toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('is-visible');
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => node.classList.remove('is-visible'), 4200);
  }

  function normalizeMethod(raw) {
    const value = text(raw, 'GET').trim().toUpperCase();
    const match = value.match(/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b/);
    return match ? match[1] : 'GET';
  }

  function normalizeCatalogRoute(raw) {
    if (typeof raw !== 'string') return null;
    let route = raw.trim();
    if (!route || route.length > 512 || route.includes('://') || route.includes('\\') || route.includes('..') || route.includes('//')) return null;
    if (route.startsWith('/VulnerableApp/')) route = route.slice('/VulnerableApp/'.length);
    else if (route === '/VulnerableApp') route = '';
    route = route.replace(/^\/+/, '');
    if (!route || !/^[A-Za-z0-9._~-]+(?:\/[A-Za-z0-9._~-]+)*$/.test(route)) return null;
    return route;
  }

  function missionRoute(mission) {
    const route = normalizeCatalogRoute(mission && mission.route);
    if (!route || !state.catalog.missions.some((item) => item && item.id === mission.id && normalizeCatalogRoute(item.route) === route)) return null;
    return route;
  }

  function missionById(id) {
    return state.catalog.missions.find((mission) => mission && String(mission.id) === String(id)) || null;
  }

  function setView(view) {
    const allowed = new Set(['home', 'catalog', 'orders', 'account', 'support', 'challenges', 'admin']);
    state.currentView = allowed.has(view) ? view : 'home';
    $$('[data-page]').forEach((section) => {
      const active = section.dataset.page === state.currentView;
      section.hidden = !active;
      section.classList.toggle('is-active', active);
    });
    $$('[data-view]').forEach((link) => {
      const active = link.dataset.view === state.currentView && link.tagName === 'A';
      link.classList.toggle('is-active', active);
      if (link.tagName === 'A') {
        if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
      }
    });
    if (state.currentView === 'catalog') renderProducts();
    if (state.currentView === 'challenges') renderChallengeArea();
    if (state.currentView === 'admin') renderAdminArea();
    updateAcademyLinks();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function setViewHash(view) {
    const next = VIEW_HASHES[view] || VIEW_HASHES.home;
    if (window.location.hash !== next) window.history.replaceState(null, '', next);
  }

  function bindNavigation() {
    $$('[data-view]').forEach((element) => {
      element.addEventListener('click', (event) => {
        const view = element.dataset.view;
        if (!view) return;
        event.preventDefault();
        if (element.dataset.mission) {
          selectMission(element.dataset.mission, true);
        } else {
          setView(view);
          setViewHash(view);
        }
      });
    });
    $('#global-search').addEventListener('submit', (event) => {
      event.preventDefault();
      const value = $('#global-search-input').value.trim();
      if (!value) { setView('catalog'); setViewHash('catalog'); return; }
      state.productQuery = value;
      state.challengeQuery = value;
      const productHit = PRODUCTS.some((product) => `${product.name} ${product.categoryLabel} ${product.description}`.toLocaleLowerCase('es-CL').includes(value.toLocaleLowerCase('es-CL')));
      if (productHit) { setView('catalog'); setViewHash('catalog'); renderProducts(); }
      else { setView('challenges'); setViewHash('challenges'); renderChallengeArea(); }
    });
  }

  function renderProductCard(product) {
    return `<article class="product-card">
      <div class="product-media"><img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)}"><span class="product-badge">${escapeHtml(product.categoryLabel)}</span></div>
      <div class="product-info"><h3>${escapeHtml(product.name)}</h3><p>${escapeHtml(product.description)}</p><div class="product-footer"><strong class="product-price">${formatPrice(product.price)}</strong><button class="button button-primary add-product" type="button" data-product="${escapeHtml(product.id)}">Agregar a bolsa</button></div></div>
    </article>`;
  }

  function filteredProducts() {
    const query = state.productQuery.toLocaleLowerCase('es-CL');
    return PRODUCTS.filter((product) => {
      const categoryMatch = state.category === 'all' || product.category === state.category;
      const queryMatch = !query || `${product.name} ${product.categoryLabel} ${product.description}`.toLocaleLowerCase('es-CL').includes(query);
      return categoryMatch && queryMatch;
    });
  }

  function renderProducts() {
    const products = filteredProducts();
    const html = products.length ? products.map(renderProductCard).join('') : '<p class="empty-copy">No encontramos productos con ese filtro. Prueba otra palabra.</p>';
    const catalog = $('#catalog-products');
    const featured = $('#featured-products');
    if (catalog) catalog.innerHTML = html;
    if (featured) featured.innerHTML = PRODUCTS.map(renderProductCard).join('');
    const count = $('#catalog-result-count');
    if (count) count.textContent = `${products.length} producto${products.length === 1 ? '' : 's'} visibles`;
    $$('.category-tab').forEach((button) => button.classList.toggle('is-active', button.dataset.category === state.category));
    $$('.add-product').forEach((button) => button.addEventListener('click', () => addToCart(button.dataset.product)));
  }

  function renderAdminArea() {
    const missions = Array.isArray(state.catalog.missions) ? state.catalog.missions : [];
    const families = familyIds();
    const points = missions.reduce((total, mission) => total + (Number(mission.points) || 0), 0);
    const missionCount = $('#admin-mission-count');
    const familyCount = $('#admin-family-count');
    const pointsTotal = $('#admin-points-total');
    const status = $('#admin-catalog-status');
    if (missionCount) missionCount.textContent = String(missions.length);
    if (familyCount) familyCount.textContent = String(families.length);
    if (pointsTotal) pointsTotal.textContent = points ? `${points.toLocaleString('es-CL')} XP` : '—';
    if (status) status.textContent = missions.length === 189 && new Set(missions.map((mission) => mission.id)).size === 189 ? '189 misiones verificadas' : 'Catálogo incompleto';
  }

  function addToCart(productId) {
    const product = PRODUCTS.find((item) => item.id === productId);
    if (!product) return;
    const current = state.cart.get(productId) || 0;
    state.cart.set(productId, current + 1);
    renderCart();
    showToast(`${product.name} fue agregado a tu bolsa local.`);
  }

  function updateQuantity(productId, delta) {
    const current = state.cart.get(productId) || 0;
    const next = current + delta;
    if (next <= 0) state.cart.delete(productId); else state.cart.set(productId, next);
    renderCart();
  }

  function removeFromCart(productId) {
    state.cart.delete(productId);
    renderCart();
  }

  function renderCart() {
    const items = Array.from(state.cart.entries()).map(([id, quantity]) => ({ product: PRODUCTS.find((item) => item.id === id), quantity })).filter((item) => item.product);
    const count = items.reduce((total, item) => total + item.quantity, 0);
    const total = items.reduce((sum, item) => sum + item.product.price * item.quantity, 0);
    $('#cart-count').textContent = String(count);
    $('#cart-total').textContent = formatPrice(total);
    $('#cart-items').innerHTML = items.length ? items.map(({ product, quantity }) => `<div class="cart-line"><img src="${escapeHtml(product.image)}" alt=""><div><h3>${escapeHtml(product.name)}</h3><p>${formatPrice(product.price)} · selección local</p><div class="cart-quantity"><button type="button" aria-label="Disminuir ${escapeHtml(product.name)}" data-cart-minus="${escapeHtml(product.id)}">−</button><span>${quantity}</span><button type="button" aria-label="Aumentar ${escapeHtml(product.name)}" data-cart-plus="${escapeHtml(product.id)}">+</button></div><button class="cart-remove" type="button" data-cart-remove="${escapeHtml(product.id)}">Quitar</button></div><strong class="cart-line-price">${formatPrice(product.price * quantity)}</strong></div>`).join('') : '<p class="empty-copy">Todavía no has elegido equipo.</p>';
    $$('[data-cart-minus]').forEach((button) => button.addEventListener('click', () => updateQuantity(button.dataset.cartMinus, -1)));
    $$('[data-cart-plus]').forEach((button) => button.addEventListener('click', () => updateQuantity(button.dataset.cartPlus, 1)));
    $$('[data-cart-remove]').forEach((button) => button.addEventListener('click', () => removeFromCart(button.dataset.cartRemove)));
  }

  function toggleCart(open) {
    const panel = $('#cart-panel');
    const scrim = $('#cart-scrim');
    const shouldOpen = typeof open === 'boolean' ? open : !panel.classList.contains('is-open');
    if (shouldOpen && !panel.classList.contains('is-open')) state.cartReturnFocus = document.activeElement;
    panel.classList.toggle('is-open', shouldOpen);
    panel.setAttribute('aria-hidden', String(!shouldOpen));
    panel.toggleAttribute('inert', !shouldOpen);
    panel.inert = !shouldOpen;
    $('#cart-toggle').setAttribute('aria-expanded', String(shouldOpen));
    scrim.hidden = !shouldOpen;
    document.body.classList.toggle('drawer-open', shouldOpen);
    if (shouldOpen) {
      setTimeout(() => $('#cart-close')?.focus(), 0);
    } else if (state.cartReturnFocus && typeof state.cartReturnFocus.focus === 'function') {
      setTimeout(() => state.cartReturnFocus?.focus(), 0);
    }
  }

  function handleCartKeydown(event) {
    const panel = $('#cart-panel');
    if (!panel.classList.contains('is-open')) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      toggleCart(false);
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = $$('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled])', panel).filter((node) => node.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function bindCart() {
    $('#cart-toggle').addEventListener('click', () => toggleCart());
    $('#cart-close').addEventListener('click', () => toggleCart(false));
    $('#cart-scrim').addEventListener('click', () => toggleCart(false));
    document.addEventListener('keydown', handleCartKeydown);
    $('#cart-review').addEventListener('click', () => { toggleCart(false); setView('orders'); setViewHash('orders'); showToast('Revisión simulada: no se creó una orden ni se inició un pago.'); });
  }

  function loadContexts() {
    return fetch('contexts.json', { headers: { Accept: 'application/json' } }).then((response) => {
      if (!response.ok) throw new Error('No se pudo cargar el mapa de áreas.');
      return response.json();
    }).then((data) => { state.contexts = data && data.families ? data : state.contexts; }).catch(() => {
      showToast('El mapa de áreas no cargó; se mostrarán los nombres técnicos del catálogo.');
    });
  }

  function loadCatalog() {
    return fetch('catalog.json', { headers: { Accept: 'application/json' } }).then((response) => {
      if (!response.ok) throw new Error(`Catálogo HTTP ${response.status}`);
      return response.json();
    }).then((data) => {
      if (!data || !Array.isArray(data.families) || !Array.isArray(data.missions)) throw new Error('Formato de catálogo inválido.');
      const ids = new Set(data.missions.map((mission) => mission && mission.id).filter(Boolean));
      if (data.missions.length !== 189 || ids.size !== 189) throw new Error('El catálogo no contiene exactamente las 189 misiones únicas de Academy.');
      state.catalog = data;
    }).catch((error) => {
      state.catalog = { families: [], missions: [] };
      $('#family-list').innerHTML = `<p class="empty-copy">No se pudo leer catalog.json. ${escapeHtml(error.message)}</p>`;
      $('#mission-list').innerHTML = '<p class="empty-copy">El padre del entorno debe copiar el catálogo local junto a esta tienda.</p>';
      showToast('Catálogo local no disponible todavía.');
    });
  }

  function familyIds() {
    const fromCatalog = state.catalog.families.map((family) => text(family && (family.id || family.family || family.name))).filter(Boolean);
    const fromMissions = state.catalog.missions.map(familyId).filter(Boolean);
    return Array.from(new Set([...fromCatalog, ...fromMissions]));
  }

  function familyMissions(id) {
    return state.catalog.missions.filter((mission) => id === 'all' || familyId(mission) === id);
  }

  function challengeMatches(mission) {
    const query = state.challengeQuery.trim().toLocaleLowerCase('es-CL');
    if (!query) return true;
    const context = familyContext(familyId(mission));
    const haystack = [mission.title, mission.id, mission.route, familyId(mission), context.title, context.area, context.summary].map((part) => text(part)).join(' ').toLocaleLowerCase('es-CL');
    return haystack.includes(query);
  }

  function renderFamilyFilter() {
    const select = $('#family-filter');
    const selected = state.selectedFamily;
    select.innerHTML = '<option value="all">Todas las familias</option>' + familyIds().map((id) => `<option value="${escapeHtml(id)}">${escapeHtml(familyContext(id).title)}</option>`).join('');
    select.value = familyIds().includes(selected) ? selected : 'all';
  }

  function renderFamilyList() {
    const ids = familyIds();
    $('#family-count').textContent = String(ids.length);
    $('#family-list').innerHTML = ids.length ? ids.map((id, index) => {
      const context = familyContext(id);
      const count = familyMissions(id).length;
      return `<button class="family-item ${state.selectedFamily === id ? 'is-active' : ''}" type="button" data-family="${escapeHtml(id)}"><span class="family-index">${String(index + 1).padStart(2, '0')}</span><span class="family-copy"><strong>${escapeHtml(context.title)}</strong><small>${escapeHtml(context.area)} · ${count} misión${count === 1 ? '' : 'es'}</small></span><span class="family-arrow" aria-hidden="true">→</span></button>`;
    }).join('') : '<p class="empty-copy">Sin familias disponibles.</p>';
    $$('[data-family]').forEach((button) => button.addEventListener('click', () => { state.selectedFamily = button.dataset.family; renderChallengeArea(); }));
  }

  function renderMissionSelect(missions) {
    const select = $('#mission-select');
    select.innerHTML = '<option value="">Selecciona una misión</option>' + missions.map((mission) => `<option value="${escapeHtml(mission.id)}">${escapeHtml(mission.title || mission.id)}</option>`).join('');
    select.value = state.selectedMission && state.catalog.missions.some((mission) => mission.id === state.selectedMission.id) ? state.selectedMission.id : '';
    if (!missions.some((mission) => state.selectedMission && mission.id === state.selectedMission.id)) select.value = '';
  }

  function renderMissionList() {
    const base = familyMissions(state.selectedFamily).filter(challengeMatches);
    const context = state.selectedFamily === 'all' ? null : familyContext(state.selectedFamily);
    $('#mission-list-title').textContent = context ? context.title : (state.challengeQuery ? 'Resultados del catálogo' : 'Todas las misiones');
    $('#mission-count').textContent = String(base.length);
    $('#mission-list').innerHTML = base.length ? base.map((mission, index) => `<button class="mission-row ${state.selectedMission && state.selectedMission.id === mission.id ? 'is-selected' : ''}" type="button" data-mission-row="${escapeHtml(mission.id)}"><span class="mission-number">${String(index + 1).padStart(2, '0')}</span><span class="mission-row-copy"><strong>${escapeHtml(mission.title || mission.id)}</strong><small>${escapeHtml(normalizeMethod(mission.method))} · ${escapeHtml(mission.route || 'ruta no publicada')}</small></span><span class="mission-row-arrow" aria-hidden="true">→</span></button>`).join('') : '<p class="empty-copy">No hay coincidencias. Prueba por área, título o una palabra más amplia.</p>';
    $$('[data-mission-row]').forEach((button) => button.addEventListener('click', () => selectMission(button.dataset.missionRow, true)));
  }

  function setMissionHash(id) {
    if (!id) return;
    const next = `#mission=${encodeURIComponent(id)}`;
    if (window.location.hash !== next) window.history.replaceState(null, '', next);
    updateAcademyLinks();
  }

  function academyUrl(missionId) {
    const host = window.location.hostname.toLowerCase();
    const base = host === 'target' ? 'http://gateway:8080/' : `${window.location.protocol}//${host || 'localhost'}:8080/`;
    return missionId ? `${base}#mission=${encodeURIComponent(missionId)}` : base;
  }

  function updateAcademyLinks() {
    const missionId = state.selectedMission && state.selectedMission.id;
    $$('[data-academy-link]').forEach((link) => { link.href = academyUrl(missionId); });
  }

  function selectMission(id, focus) {
    const mission = typeof id === 'object' ? id : missionById(id);
    if (!mission) return;
    state.selectedMission = mission;
    state.selectedFamily = familyId(mission) || 'all';
    setView('challenges');
    setMissionHash(mission.id);
    renderChallengeArea();
    if (focus) setTimeout(() => $('#mission-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30);
  }

  function renderChallengeArea() {
    renderFamilyFilter();
    renderFamilyList();
    const visible = familyMissions(state.selectedFamily).filter(challengeMatches);
    renderMissionSelect(visible);
    renderMissionList();
    renderMissionDetail();
  }

  function parseHashMission() {
    try {
      return new URLSearchParams(window.location.hash.replace(/^#/, '')).get('mission') || '';
    } catch (_) {
      return '';
    }
  }

  function viewFromHash() {
    const entry = Object.entries(VIEW_HASHES).find(([, hash]) => hash === window.location.hash);
    return entry ? entry[0] : '';
  }

  function inputRow(kind, key = '', value = '') {
    const keyAttr = escapeHtml(key);
    const valueAttr = escapeHtml(value);
    const placeholder = kind === 'header' ? 'X-Cabecera' : 'parámetro';
    return `<div class="param-row" data-row-kind="${kind}"><input class="editor-input mono row-key" aria-label="Nombre de ${kind === 'header' ? 'cabecera' : 'parámetro'}" placeholder="${placeholder}" value="${keyAttr}"><input class="editor-input mono row-value" aria-label="Valor de ${kind === 'header' ? 'cabecera' : 'parámetro'}" placeholder="valor benigno" value="${valueAttr}"><button class="remove-row" type="button" aria-label="Quitar fila">×</button></div>`;
  }

  function defaultsForMission(mission) {
    if (familyId(mission) === 'ssrf') return [['fileurl', 'not-a-url']];
    if (familyId(mission) === 'commandInjection' && ['commandInjection-01', 'commandInjection-02'].includes(String(mission.id))) {
      return Object.entries(mission.params || {}).map(([key, value]) => [key, text(value)]);
    }
    return [];
  }

  function editorValues() {
    const params = {};
    $$('#param-rows .param-row').forEach((row) => { const key = $('.row-key', row).value.trim(); if (key) params[key] = $('.row-value', row).value; });
    const headers = {};
    $$('#header-rows .param-row').forEach((row) => { const key = $('.row-key', row).value.trim(); if (key) headers[key] = $('.row-value', row).value; });
    return { method: $('#request-method').value, params, headers, body: $('#request-body').value, content_type: $('#request-content-type').value.trim() };
  }

  function renderMissionDetail() {
    const mission = state.selectedMission;
    const detail = $('#mission-detail');
    if (!mission) {
      detail.innerHTML = '<div class="empty-detail"><span aria-hidden="true">⌁</span><h2>Tu mesa de práctica está lista</h2><p>Selecciona un nivel para ver la ruta exacta, el criterio de verificación y el editor de solicitud.</p></div>';
      return;
    }
    const family = familyId(mission);
    const context = familyContext(family);
    const route = missionRoute(mission);
    const method = normalizeMethod(mission.method);
    const rawMethod = text(mission.method, method);
    const check = mission.check === undefined ? 'El catálogo no publicó un check.' : safeJson(mission.check, text(mission.check));
    const tool = text(mission.tool, 'http_request');
    const multipart = text(mission.content_type).toLowerCase().includes('multipart') || Boolean(mission.params && mission.params.file);
    const browserContext = tool === 'browser_probe' || ['xss', 'clickjacking'].includes(family) || /csrf/i.test(text(mission.title));
    const safeDiagnostic = mission.id === 'commandInjection-02' && family === 'commandInjection';
    const warning = safeDiagnostic ? '<strong>Diagnóstico benigno listo.</strong> El valor proviene del catálogo y termina en <code>printf VA_LAB_OK</code>; no lee archivos, no abre conexiones y no agrega otra orden. Abrir esta ficha, editarla o copiar el comando no ejecuta nada.' : multipart ? '<strong>Requiere multipart/form-data.</strong> No se construye FormData aquí: usa la experiencia original o el flujo de Kali, que conserva el campo de archivo y sus límites.' : browserContext ? '<strong>Requiere contexto de navegador.</strong> Este panel no ejecuta HTML, JavaScript, iframes ni CSRF; abre el endpoint real o la experiencia original para observar el contexto correcto.' : '<strong>Control antes de probar.</strong> La solicitud se envía solo al endpoint catalogado en este mismo origen. Edita datos benignos y confirma explícitamente.';
    const parameterHelp = safeDiagnostic ? 'Valor benigno del catálogo cargado como diagnóstico; enviar requiere la casilla de confirmación.' : family === 'ssrf' ? 'Plantilla inicial segura: <code>fileurl=not-a-url</code>.' : 'Plantilla inicial vacía.';
    detail.innerHTML = `<div class="mission-detail-head"><p class="eyebrow">${escapeHtml(context.area)} · ${escapeHtml(context.title)}</p><h2>${escapeHtml(mission.title || mission.id)}</h2><p>${escapeHtml(context.summary)}</p><div class="mission-facts"><span class="fact-chip"><b>Ruta</b><code>${escapeHtml(text(mission.route, 'no publicada'))}</code></span><span class="fact-chip"><b>Método catálogo</b><code>${escapeHtml(rawMethod)}</code></span><span class="fact-chip"><b>Misión</b><code>${escapeHtml(mission.id)}</code></span></div></div><div class="mission-docs"><div class="doc-block"><p class="doc-label">Criterio del catálogo</p><p><code>${escapeHtml(check)}</code></p></div><div class="doc-block"><p class="doc-label">Lectura recomendada</p><p>${escapeHtml(text(mission.explanation, 'Lee la ficha técnica de Academy y compara controles positivos y negativos.'))}</p></div><div class="doc-block wide"><p class="doc-label">Límite pedagógico</p><p>El botón de esta tienda no concede XP, no guarda tokens y no convierte un HTTP 200 en éxito. Academy y el runner de Kali son la fuente para validar la misión.</p></div></div><div class="practice-editor"><div class="practice-title"><div><h3>Editor de solicitud</h3><p>Endpoint same-origin: <code>${escapeHtml(route ? `/VulnerableApp/${route}` : 'ruta rechazada')}</code></p></div><span class="status-pill">${escapeHtml(tool === 'browser_probe' ? 'Navegador / manual' : 'HTTP local')}</span></div><div class="editor-warning">${warning}</div><form id="practice-form" class="editor-form" novalidate><div class="editor-grid"><section class="editor-section"><h4>Solicitud</h4><div class="field-group"><label class="editor-label" for="request-method">Método editable</label><select id="request-method" class="editor-select"></select><p class="editor-help">Valor original: <code>${escapeHtml(rawMethod)}</code></p></div><div class="field-group"><label class="editor-label" for="request-content-type">content_type</label><input id="request-content-type" class="editor-input mono" type="text" autocomplete="off" placeholder="vacío si no aplica"><p class="editor-help">No se rellena con el catálogo para mantener un control benigno.</p></div><div class="field-group"><label class="editor-label" for="request-body">body</label><textarea id="request-body" class="editor-textarea mono" rows="5" placeholder="vacío por defecto"></textarea></div></section><section class="editor-section"><h4>params</h4><div id="param-rows" class="rows-editor"></div><button class="add-row" type="button" data-add-row="param">+ Agregar parámetro</button><p class="editor-help">${parameterHelp}</p></section></div><section class="editor-section"><h4>headers</h4><div id="header-rows" class="rows-editor"></div><button class="add-row" type="button" data-add-row="header">+ Agregar cabecera</button><p class="editor-help">No se copia ninguna sesión ni token. La cabecera <code>Host</code> está bloqueada para no reemplazar el origen.</p></section><label class="control-check"><input id="confirm-practice" type="checkbox"><span>Confirmo que revisaré el método, la ruta y los datos antes de enviar esta práctica. Entiendo que es una simulación de laboratorio sin pagos ni XP y que una respuesta HTTP 200 no prueba éxito.</span></label><div class="editor-actions"><button class="button button-primary" id="send-request" type="submit" ${route && !multipart && !browserContext ? '' : 'disabled'}>Enviar control al target</button><button class="button copy-button" id="copy-curl" type="button" ${route ? '' : 'disabled'}>Copiar curl</button><button class="button copy-button" id="copy-lab" type="button" ${route && LAB_METHODS.has(method) ? '' : 'disabled'}>Copiar lab request</button></div><div class="endpoint-links"><a class="text-link" id="endpoint-link" href="${route ? `/VulnerableApp/${escapeHtml(route)}` : '#'}" target="_blank" rel="noopener">Abrir endpoint real ↗</a><a class="text-link" href="/VulnerableApp/original/" target="_blank" rel="noopener">Abrir experiencia original ↗</a><a class="text-link" id="mission-academy-link" data-academy-link href="${escapeHtml(academyUrl(mission.id))}">Volver a Academy ↗</a></div><div id="response-panel" class="response-panel" hidden></div></form></div>`;
    const methodSelect = $('#request-method');
    methodSelect.innerHTML = STANDARD_METHODS.map((candidate) => `<option value="${candidate}" ${candidate === method ? 'selected' : ''}>${candidate}</option>`).join('');
    const params = defaultsForMission(mission);
    $('#param-rows').innerHTML = params.map(([key, value]) => inputRow('param', key, value)).join('');
    $('#header-rows').innerHTML = '';
    $$('.remove-row').forEach((button) => button.addEventListener('click', () => button.closest('.param-row').remove()));
    $$('[data-add-row]').forEach((button) => button.addEventListener('click', () => {
      const target = button.dataset.addRow === 'header' ? $('#header-rows') : $('#param-rows');
      target.insertAdjacentHTML('beforeend', inputRow(button.dataset.addRow));
      $('.remove-row:last-child', target).addEventListener('click', (event) => event.currentTarget.closest('.param-row').remove());
    }));
    $('#practice-form').addEventListener('submit', (event) => sendPractice(event, mission, route, multipart, browserContext));
    $('#copy-curl').addEventListener('click', () => copyCommand('curl', mission, route));
    $('#copy-lab').addEventListener('click', () => copyCommand('lab', mission, route));
  }

  function parseHeaders(rawHeaders) {
    const headers = {};
    const errors = [];
    Object.entries(rawHeaders).forEach(([key, value]) => {
      const name = key.trim();
      if (!name) return;
      if (!/^[A-Za-z0-9!#$%&'*+.^_`|~-]+$/.test(name)) errors.push(`Cabecera inválida: ${name}`);
      if (/^(host|:authority)$/i.test(name)) errors.push('No se permite reemplazar el host del target.');
      if (/^[\x00-\x1f\x7f]/.test(value) || /[\x00-\x1f\x7f]/.test(name)) errors.push(`Caracteres de control en ${name}.`);
      headers[name] = value;
    });
    return { headers, errors };
  }

  function validateEditor(mission, route, values) {
    const errors = [];
    if (!route || !missionRoute(mission)) errors.push('La ruta no coincide con una misión del catálogo local.');
    if (!STANDARD_METHODS.includes(values.method)) errors.push('Método no permitido.');
    Object.keys(values.params).forEach((key) => { if (!/^[A-Za-z0-9_.~-]+$/.test(key)) errors.push(`Parámetro inválido: ${key}`); });
    const headerResult = parseHeaders(values.headers);
    errors.push(...headerResult.errors);
    if (values.body.length > 16384) errors.push('El body supera el límite local de 16 KiB.');
    if (values.content_type.length > 180) errors.push('content_type demasiado largo.');
    return { errors, headers: headerResult.headers };
  }

  function buildTargetUrl(route, params) {
    if (!route) return null;
    const url = new URL(`/VulnerableApp/${route}`, window.location.origin);
    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
    return url;
  }

  async function sendPractice(event, mission, route, multipart, browserContext) {
    event.preventDefault();
    if (!$('#confirm-practice').checked) { showToast('Marca la confirmación explícita antes de probar.'); return; }
    if (multipart || browserContext) { showToast('Esta misión necesita el endpoint original o Kali para conservar su contexto real.'); return; }
    const values = editorValues();
    const validation = validateEditor(mission, route, values);
    if (validation.errors.length) { showToast(validation.errors.join(' ')); return; }
    const target = buildTargetUrl(route, values.params);
    const options = { method: values.method, headers: validation.headers, credentials: 'same-origin' };
    if (values.content_type && !Object.keys(options.headers).some((key) => key.toLowerCase() === 'content-type')) options.headers['Content-Type'] = values.content_type;
    if (!['GET', 'HEAD'].includes(values.method) && values.body) options.body = values.body;
    const button = $('#send-request');
    button.disabled = true;
    button.textContent = 'Probando…';
    renderResponse({ loading: true });
    try {
      const response = await fetch(target.href, options);
      const raw = await response.text();
      renderResponse({ status: response.status, statusText: response.statusText, body: raw.slice(0, MAX_RESPONSE), truncated: raw.length > MAX_RESPONSE, headers: Array.from(response.headers.entries()) });
    } catch (error) {
      renderResponse({ error: `No se pudo completar la solicitud same-origin: ${error.message}` });
    } finally {
      button.disabled = false;
      button.textContent = 'Enviar control al target';
    }
  }

  function renderResponse(result) {
    const panel = $('#response-panel');
    if (!panel) return;
    panel.hidden = false;
    if (result.loading) { panel.innerHTML = '<div class="response-head"><h4>Respuesta del target</h4><span class="response-meta">en curso…</span></div>'; return; }
    if (result.error) { panel.innerHTML = `<div class="response-head"><h4>Respuesta del target</h4><span class="response-meta">error local</span></div><pre class="response-body">${escapeHtml(result.error)}</pre><p class="response-note">Revisa que el target esté disponible y que la ruta pertenezca al catálogo.</p>`; return; }
    const headers = result.headers && result.headers.length ? `\n\nCabeceras visibles:\n${result.headers.map(([key, value]) => `${key}: ${value}`).join('\n')}` : '';
    panel.innerHTML = `<div class="response-head"><h4>Respuesta del target</h4><span class="response-meta">HTTP ${escapeHtml(result.status)} ${escapeHtml(result.statusText)}</span></div><pre class="response-body">${escapeHtml(result.body || '(body vacío)')}${escapeHtml(headers)}</pre>${result.truncated ? '<p class="response-note">Body recortado a 12.000 caracteres para esta vista.</p>' : ''}<p class="response-note">HTTP 200 no es sinónimo de éxito: lee el JSON, el criterio de la misión y los controles en Academy.</p>`;
  }

  function shellQuote(value) {
    return `'${text(value).replace(/'/g, "'\\''")}'`;
  }

  function commandData(mission, route) {
    const values = editorValues();
    const validation = validateEditor(mission, route, values);
    return { values, validation, url: buildTargetUrl(route, values.params) };
  }

  function buildCurl(mission, route) {
    const { values, validation, url } = commandData(mission, route);
    if (!url || validation.errors.length) return { error: validation.errors.join(' ') || 'Ruta inválida.' };
    const pieces = ['curl', '-i', '-sS', '--request', values.method, shellQuote(url.href)];
    Object.entries(validation.headers).forEach(([key, value]) => pieces.push('--header', shellQuote(`${key}: ${value}`)));
    if (values.content_type && !Object.keys(validation.headers).some((key) => key.toLowerCase() === 'content-type')) pieces.push('--header', shellQuote(`Content-Type: ${values.content_type}`));
    if (!['GET', 'HEAD'].includes(values.method) && values.body) pieces.push('--data', shellQuote(values.body));
    return { command: pieces.join(' ') };
  }

  function buildLab(mission, route) {
    const { values, validation } = commandData(mission, route);
    if (validation.errors.length) return { error: validation.errors.join(' ') };
    if (!LAB_METHODS.has(values.method)) return { error: `kali/lab.py solo acepta GET, POST y PUT; no se inventa un flag para ${values.method}.` };
    const pieces = ['lab', 'request', shellQuote(mission.id), '--method', values.method];
    Object.entries(values.params).forEach(([key, value]) => pieces.push('--param', shellQuote(`${key}=${value}`)));
    Object.entries(validation.headers).forEach(([key, value]) => pieces.push('--header', shellQuote(`${key}=${value}`)));
    if (values.body) pieces.push('--body', shellQuote(values.body));
    if (values.content_type) pieces.push('--content-type', shellQuote(values.content_type));
    return { command: pieces.join(' ') };
  }

  async function copyCommand(type, mission, route) {
    const result = type === 'curl' ? buildCurl(mission, route) : buildLab(mission, route);
    if (result.error) { showToast(result.error); return; }
    try {
      await navigator.clipboard.writeText(result.command);
      showToast(`${type === 'curl' ? 'curl' : 'lab request'} copiado. No se ejecutó ni se envió.`);
    } catch (_) {
      window.prompt('Copia el comando; no se ejecutará desde la tienda:', result.command);
    }
  }

  function bindChallengeControls() {
    $('#challenge-search').addEventListener('input', (event) => { state.challengeQuery = event.target.value; renderChallengeArea(); });
    $('#family-filter').addEventListener('change', (event) => { state.selectedFamily = event.target.value; renderChallengeArea(); });
    $('#mission-select').addEventListener('change', (event) => { if (event.target.value) selectMission(event.target.value, true); });
    window.addEventListener('hashchange', () => {
      const id = parseHashMission();
      if (id && missionById(id)) selectMission(id, false);
      else {
        const view = viewFromHash();
        if (view) setView(view);
      }
    });
  }

  async function boot() {
    bindNavigation();
    bindCart();
    renderProducts();
    renderCart();
    bindChallengeControls();
    await Promise.all([loadContexts(), loadCatalog()]);
    renderChallengeArea();
    renderAdminArea();
    updateAcademyLinks();
    const missionId = parseHashMission();
    if (missionId && missionById(missionId)) selectMission(missionId, false);
    else if (viewFromHash()) setView(viewFromHash());
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
