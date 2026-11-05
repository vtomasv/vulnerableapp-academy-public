(() => {
  'use strict';

  const PRODUCTS = [
    { id: 'mochila-andina', name: 'Mochila Andina', category: 'trekking', categoryLabel: 'Trekking', price: 39990, image: 'assets/mochila.jpg', description: 'Espalda ventilada, bolsillos de mapa y una jornada completa sin cargar de más.' },
    { id: 'termo-austral', name: 'Termo Austral', category: 'campamento', categoryLabel: 'Campamento', price: 18990, image: 'assets/termo.jpg', description: 'Acero de doble pared para café de madrugada y agua para el regreso.' },
    { id: 'parlante-pacifico', name: 'Parlante Pacífico', category: 'audio', categoryLabel: 'Audio de ruta', price: 24990, image: 'assets/parlante.jpg', description: 'Sonido compacto para el refugio, con una historia de producto bien simple.' }
  ];
  const PRICE = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });
  const LAB_METHODS = new Set(['GET', 'POST', 'PUT']);
  const TOKEN_KEY = 'va_session_token';
  const VIEW_HASHES = { home: '#inicio', catalog: '#catalogo', orders: '#pedidos', account: '#cuenta', support: '#soporte', challenges: '#retos' };
  const state = {
    token: null,
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

  function missionMethods(mission) {
    const methods = text(mission.method).toUpperCase().match(/\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b/g) || [];
    return [...new Set(methods)];
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
    const allowed = new Set(['home', 'catalog', 'orders', 'account', 'support', 'challenges']);
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
    if (state.currentView === 'account' && state.token) refreshProgress();
    window.scrollTo({ top: 0 });
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
        if (element.dataset.mission && missionById(element.dataset.mission)) {
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
      $('#challenge-search').value = value;
      state.selectedFamily = 'all';
      const productHit = PRODUCTS.some((product) => `${product.name} ${product.categoryLabel} ${product.description}`.toLocaleLowerCase('es-CL').includes(value.toLocaleLowerCase('es-CL')));
      const view = productHit ? 'catalog' : 'challenges';
      setView(view);
      setViewHash(view);
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
    return fetch('/contexts.json', { headers: { Accept: 'application/json' } }).then((response) => {
      if (!response.ok) throw new Error('No se pudo cargar el mapa de áreas.');
      return response.json();
    }).then((data) => { state.contexts = data && data.families ? data : state.contexts; }).catch(() => {
      showToast('El mapa de áreas no cargó; se mostrarán los nombres técnicos del catálogo.');
    });
  }

  function loadCatalog() {
    return fetch('/api/catalog', { headers: { Accept: 'application/json' } }).then((response) => {
      if (!response.ok) throw new Error(`Catálogo HTTP ${response.status}`);
      return response.json();
    }).then((data) => {
      if (!data || !Array.isArray(data.families) || !Array.isArray(data.missions)) throw new Error('Formato de catálogo inválido.');
      const ids = new Set(data.missions.map((mission) => mission && mission.id).filter(Boolean));
      if (!ids.size || ids.size !== data.missions.length) throw new Error('El catálogo contiene IDs inválidos o duplicados.');
      state.catalog = data;
    }).catch((error) => {
      state.catalog = { families: [], missions: [] };
      showToast(`No se pudo cargar el catálogo. ${error.message} Recarga la página para reintentar.`);
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
    select.value = missions.some((mission) => mission === state.selectedMission) ? state.selectedMission.id : '';
  }

  function renderMissionList(base) {
    const context = state.selectedFamily === 'all' ? null : familyContext(state.selectedFamily);
    $('#mission-list-title').textContent = context ? context.title : (state.challengeQuery ? 'Resultados del catálogo' : 'Todas las misiones');
    $('#mission-count').textContent = String(base.length);
    $('#mission-list').innerHTML = base.length ? base.map((mission, index) => `<button class="mission-row ${state.selectedMission && state.selectedMission.id === mission.id ? 'is-selected' : ''}" type="button" data-mission-row="${escapeHtml(mission.id)}"><span class="mission-number">${String(index + 1).padStart(2, '0')}</span><span class="mission-row-copy"><strong>${escapeHtml(mission.title || mission.id)}</strong><small>${escapeHtml(missionMethods(mission).join(' / '))} · ${escapeHtml(mission.route || 'ruta no publicada')}</small></span><span class="mission-row-arrow" aria-hidden="true">→</span></button>`).join('') : '<p class="empty-copy">No hay coincidencias. Prueba por área, título o una palabra más amplia.</p>';
    $$('[data-mission-row]').forEach((button) => button.addEventListener('click', () => selectMission(button.dataset.missionRow, true)));
  }

  function setMissionHash(id) {
    if (!id) return;
    const next = `#mission=${encodeURIComponent(id)}`;
    if (window.location.hash !== next) window.history.replaceState(null, '', next);
    $('#lab-resume').href = next;
    $('#lab-resume').dataset.mission = id;
  }

  function selectMission(id, focus) {
    const mission = typeof id === 'object' ? id : missionById(id);
    if (!mission) return;
    const changed = mission !== state.selectedMission;
    state.selectedMission = mission;
    state.selectedFamily = familyId(mission) || 'all';
    setView('challenges');
    setMissionHash(mission.id);
    if (changed) renderMissionDetail();
    if (focus) {
      const detail = $('#mission-detail');
      detail.focus({ preventScroll: true });
      detail.scrollIntoView({ block: 'start' });
    }
  }

  function renderChallengeArea() {
    renderFamilyFilter();
    renderFamilyList();
    const visible = familyMissions(state.selectedFamily).filter(challengeMatches);
    renderMissionSelect(visible);
    renderMissionList(visible);
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

  function editorValues() {
    const params = Object.fromEntries($$('#param-rows .param-row')
      .map((row) => [$('.row-key', row).value.trim(), $('.row-value', row).value]).filter(([key]) => key));
    const headers = Object.fromEntries($$('#header-rows .param-row')
      .map((row) => [$('.row-key', row).value.trim(), $('.row-value', row).value]).filter(([key]) => key));
    return {
      method: $('#request-method').value, params, headers,
      body: $('#request-body').value || null,
      content_type: $('#request-content-type').value.trim() || null
    };
  }

  function fillEditor(request) {
    const method = $('#request-method');
    if (Array.from(method.options).some((option) => option.value === request.method)) method.value = request.method;
    $('#request-body').value = request.body || '';
    $('#request-content-type').value = request.content_type || '';
    for (const [kind, fields] of [['param', request.params], ['header', request.headers]]) {
      $(`#${kind}-rows`).innerHTML = Object.entries(fields || {})
        .filter(([, value]) => typeof value === 'string')
        .map(([key, value]) => inputRow(kind, key, value)).join('');
    }
    $('#confirm-practice').checked = false;
  }

  function renderMissionDetail() {
    const mission = state.selectedMission;
    const detail = $('#mission-detail');
    const context = familyContext(familyId(mission));
    const route = missionRoute(mission);
    const methods = missionMethods(mission);
    const multipart = text(mission.content_type).toLowerCase().includes('multipart') || Boolean(mission.params?.file);
    const browserProbe = mission.tool === 'browser_probe';
    const guided = !route || !methods.length || multipart ||
      (!browserProbe && (familyId(mission) === 'clickjacking' || /csrf/i.test(text(mission.title))));
    const example = Object.values(mission.params || {}).every((value) => typeof value === 'string');
    const steps = (mission.steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join('');
    const hints = (mission.hints || []).map((hint) => `<li>${escapeHtml(hint)}</li>`).join('');
    detail.innerHTML = `
      <div class="mission-detail-head">
        <p class="eyebrow">${escapeHtml(context.area)} · ${escapeHtml(context.title)}</p>
        <h2>${escapeHtml(mission.title || mission.id)}</h2>
        <p>${escapeHtml(context.summary)}</p>
        <div class="mission-facts">
          <span class="fact-chip"><b>Ruta</b><code>${escapeHtml(mission.route)}</code></span>
          <span class="fact-chip"><b>Método</b><code>${escapeHtml(mission.method)}</code></span>
          <span class="fact-chip"><b>Misión</b><code>${escapeHtml(mission.id)}</code></span>
          <span class="fact-chip">${mission.points ? `${Number(mission.points)} XP` : 'Práctica guiada'}</span>
        </div>
      </div>
      <div class="mission-docs">
        <div class="doc-block"><p class="doc-label">Hipótesis</p><p>${escapeHtml(mission.explanation)}</p></div>
        <div class="doc-block"><p class="doc-label">Evidencia esperada</p><p>${escapeHtml(mission.expected)}</p></div>
        <details class="doc-block wide"><summary>Pasos para practicar a mano en Kali</summary><ol class="mission-steps">${steps}</ol></details>
        <details class="doc-block wide"><summary>Pistas y mitigación</summary><ul>${hints}</ul><p>${escapeHtml(mission.mitigation)}</p></details>
      </div>
      <div class="practice-editor">
        <div class="practice-title"><div><h3>Práctica del reto</h3><p>Trabaja con el servicio interno <code>target:9090</code>.</p></div></div>
        <div class="editor-warning">${guided ? 'Sigue los pasos de esta ficha en la terminal o Firefox de Kali. Esta práctica requiere un flujo específico.' : browserProbe ? 'El runner usa Chromium de Kali para verificar la evidencia en el DOM.' : 'Prueba primero un control y compara su respuesta con la del ejemplo.'}</div>
        ${guided ? '' : `
        <form id="practice-form" class="editor-form">
          <div class="editor-actions">
            ${mission.baseline ? '<button class="button button-secondary" id="load-baseline" type="button">Cargar control</button>' : ''}
            ${example ? '<button class="button button-secondary" id="load-example" type="button">Cargar ejemplo</button>' : ''}
          </div>
          <div class="editor-grid">
            <section class="editor-section">
              <h4>Solicitud</h4>
              <div class="field-group"><label for="request-method">Método HTTP</label><select id="request-method" class="editor-select">${methods.map((method) => `<option>${method}</option>`).join('')}</select></div>
              <div class="field-group" ${browserProbe ? 'hidden' : ''}><label for="request-content-type">Content-Type</label><input id="request-content-type" class="editor-input mono" type="text" maxlength="256"></div>
              <div class="field-group" ${browserProbe ? 'hidden' : ''}><label for="request-body">Cuerpo</label><textarea id="request-body" class="editor-textarea mono" rows="4"></textarea></div>
            </section>
            <section class="editor-section"><h4>Parámetros</h4><div id="param-rows" class="rows-editor"></div><button class="add-row" type="button" data-add-row="param">+ Agregar parámetro</button></section>
          </div>
          <section class="editor-section" ${browserProbe ? 'hidden' : ''}><h4>Cabeceras</h4><div id="header-rows" class="rows-editor"></div><button class="add-row" type="button" data-add-row="header">+ Agregar cabecera</button></section>
          <label class="control-check"><input id="confirm-practice" type="checkbox"><span>Revisé el método y los datos. Quiero ejecutar esta solicitud en el laboratorio.</span></label>
          <div class="editor-actions">
            <button class="button button-primary" id="send-request" type="submit">Enviar y verificar</button>
            <button class="button copy-button" id="copy-curl" type="button">Copiar curl</button>
            <button class="button copy-button" id="copy-lab" type="button">Copiar lab request</button>
          </div>
          <div id="response-panel" class="response-panel" role="status" hidden></div>
        </form>`}
        <details class="harness-guide">
          <summary>Practicar con el harness</summary>
          <ol>
            <li>Abre Kali. En su terminal, ejecuta <code>lab login</code> con tu cuenta del taller.</li>
            <li>Abre <strong>Harness del taller</strong> en el escritorio de Kali. Pide al agente que consulte <code>lab_missions</code> para <code>${escapeHtml(mission.id)}</code> y explique el control.</li>
            <li>Revisa los argumentos de cada llamada y usa <strong>Allow once</strong> para aprobarla. <code>lab_submit</code> registra la evidencia cuando el reto tiene verificación automática.</li>
          </ol>
          <a class="button button-secondary" href="/kali/vnc.html?autoconnect=1&amp;resize=scale&amp;path=websockify" target="_blank" rel="noopener">Abrir Kali ↗</a>
        </details>
      </div>`;
    if (guided) return;
    const initial = mission.baseline || { params: Object.fromEntries(Object.keys(mission.params || {}).map((key) => [key, ''])) };
    fillEditor(initial);
    $('#load-baseline')?.addEventListener('click', () => fillEditor(mission.baseline));
    $('#load-example')?.addEventListener('click', () => fillEditor(mission));
    $('#practice-form').addEventListener('click', (event) => {
      const kind = event.target.dataset.addRow;
      if (kind) $(`#${kind}-rows`).insertAdjacentHTML('beforeend', inputRow(kind));
      if (event.target.matches('.remove-row')) event.target.closest('.param-row').remove();
    });
    $('#practice-form').addEventListener('submit', (event) => sendPractice(event, mission, route));
    $('#copy-curl').addEventListener('click', () => copyCommand('curl', mission, route));
    $('#copy-lab').addEventListener('click', () => copyCommand('lab', mission, route));
  }

  function parseHeaders(rawHeaders) {
    const headers = Object.create(null);
    const errors = [];
    Object.entries(rawHeaders).forEach(([key, value]) => {
      const name = key.trim();
      if (!name) return;
      if (!/^[A-Za-z0-9!#$%&'*+.^_`|~-]+$/.test(name)) errors.push(`Cabecera inválida: ${name}`);
      if (/^(host|:authority)$/i.test(name)) errors.push('No se permite reemplazar el host del target.');
      if (/[\x00-\x1f\x7f]/.test(value) || /[\x00-\x1f\x7f]/.test(name)) errors.push(`Caracteres de control en ${name}.`);
      headers[name] = value;
    });
    return { headers, errors };
  }

  function validateEditor(mission, route, values) {
    const errors = [];
    if (!route || !missionRoute(mission)) errors.push('La ruta no coincide con una misión del catálogo local.');
    if (!missionMethods(mission).includes(values.method)) errors.push('Método no permitido.');
    Object.keys(values.params).forEach((key) => { if (!/^[A-Za-z0-9_.~-]+$/.test(key)) errors.push(`Parámetro inválido: ${key}`); });
    const headerResult = parseHeaders(values.headers);
    errors.push(...headerResult.errors);
    if (new TextEncoder().encode(values.body || '').length > 16384) errors.push('El body supera el límite local de 16 KiB.');
    return { errors, headers: headerResult.headers };
  }

  function buildTargetUrl(route, params) {
    if (!route) return null;
    const url = new URL(`/VulnerableApp/${route}`, 'http://target:9090');
    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
    return url;
  }

  async function api(path, payload, token = state.token) {
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (payload) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, { method: payload ? 'POST' : 'GET', headers, body: payload ? JSON.stringify(payload) : undefined });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 && token && token === state.token) setSession(null);
      const error = new Error(typeof data.detail === 'string' ? data.detail : `La solicitud falló (HTTP ${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function setSession(token) {
    state.token = token;
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch (_) {
      // El navegador puede bloquear el almacenamiento en esta pestaña.
    }
    $('#lab-auth').hidden = Boolean(token);
    $('#lab-progress').hidden = !token;
    $('#lab-session-link').textContent = token ? 'Mi progreso' : 'Ingresar al taller';
    $('#lab-score').textContent = '';
    $('#lab-auth-feedback').textContent = '';
    if (!token && $('#response-panel')) {
      $('#response-panel').replaceChildren();
      $('#response-panel').hidden = true;
    }
  }

  async function refreshProgress() {
    const token = state.token;
    if (!token) return;
    try {
      const progress = await api('/api/me', null, token);
      if (token !== state.token) return;
      $('#lab-score').textContent = `${progress.user.username} · ${progress.score} / ${progress.maximum} XP · ${progress.completed.length} retos completados`;
      $('#lab-auth-feedback').textContent = '';
    } catch (error) {
      $('#lab-auth-feedback').textContent = error.message;
    }
  }

  function bindSession() {
    let token = null;
    try { token = sessionStorage.getItem(TOKEN_KEY); } catch (_) {}
    setSession(token);
    $('#lab-auth').addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const action = event.submitter?.value === 'register' ? 'register' : 'login';
      const buttons = $$('button', form);
      const fields = $$('input', form);
      fields.forEach((field) => field.removeAttribute('aria-invalid'));
      $('#lab-auth-feedback').textContent = 'Verificando la cuenta…';
      buttons.forEach((button) => { button.disabled = true; });
      try {
        const credentials = Object.fromEntries(new FormData(form));
        const data = await api(`/api/auth/${action}`, credentials, null);
        form.reset();
        setSession(data.token);
        $('#lab-resume').focus();
        await refreshProgress();
      } catch (error) {
        if ([400, 401, 409, 422].includes(error.status)) fields.forEach((field) => field.setAttribute('aria-invalid', 'true'));
        $('#lab-auth-feedback').textContent = error.message;
      } finally {
        buttons.forEach((button) => { button.disabled = false; });
      }
    });
    $('#lab-refresh').addEventListener('click', refreshProgress);
    $('#lab-logout').addEventListener('click', () => {
      setSession(null);
      $('#lab-username').focus();
    });
  }

  function evidenceMarkup(evidence) {
    const status = evidence.status ? `<p class="response-note">HTTP ${Number(evidence.status)}</p>` : '';
    let body = evidence.browser_dataset ? safeJson(evidence.browser_dataset) : evidence.body;
    if (typeof body === 'string') {
      try {
        const parsed = JSON.parse(body);
        if (parsed && typeof parsed.content === 'string' && Object.prototype.hasOwnProperty.call(parsed, 'isValid')) {
          body = parsed.content;
        }
      } catch (_) {
        // Keep non-JSON responses unchanged.
      }
    }
    const headers = Object.entries(evidence.headers || {}).map(([name, value]) => `${name}: ${value}`).join('\n');
    return `${status}<pre class="response-body">${escapeHtml(body ?? evidence.error ?? '(respuesta sin cuerpo)')}</pre>
      ${headers ? `<details><summary>Cabeceras de respuesta</summary><pre class="response-body">${escapeHtml(headers)}</pre></details>` : ''}`;
  }

  async function sendPractice(event, mission, route) {
    event.preventDefault();
    const form = event.currentTarget;
    const confirmation = $('#confirm-practice', form);
    if (!confirmation.checked) {
      showToast('Confirma la solicitud antes de enviarla.');
      confirmation.focus();
      return;
    }
    const token = state.token;
    if (!token) {
      setView('account');
      setViewHash('account');
      $('#lab-auth-feedback').textContent = 'Inicia sesión o crea una cuenta y luego vuelve al reto.';
      $('#lab-username').focus();
      return;
    }
    const request = editorValues();
    const { errors, headers } = validateEditor(mission, route, request);
    if (errors.length) { showToast(errors.join(' ')); return; }
    const button = $('#send-request', form);
    const panel = $('#response-panel', form);
    button.disabled = true;
    confirmation.checked = false;
    panel.hidden = false;
    panel.textContent = 'Ejecutando la solicitud…';
    try {
      const result = await api('/api/attempt', { mission_id: mission.id, request: { ...request, headers } }, token);
      if (token !== state.token) return;
      const evidence = result.evidence || {};
      panel.innerHTML = `
        <div class="response-head"><h4>${result.success ? 'Evidencia verificada' : 'Resultado de la prueba'}</h4><span class="response-meta">+${Number(result.awarded)} XP · Total ${Number(result.score)} XP</span></div>
        <p class="response-note">${escapeHtml(result.message)}</p>
        ${evidenceMarkup(evidence)}
        ${evidence.baseline ? `<details><summary>Respuesta del control</summary>${evidenceMarkup(evidence.baseline)}</details>` : ''}
        ${evidence.probe && evidence.attack ? `<details><summary>Respuesta de la solicitud inicial</summary>${evidenceMarkup(evidence.attack)}</details>` : ''}`;
    } catch (error) {
      panel.hidden = false;
      panel.textContent = error.message;
    } finally {
      button.disabled = false;
    }
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
    bindSession();
    renderProducts();
    renderCart();
    bindChallengeControls();
    await Promise.all([loadContexts(), loadCatalog()]);
    renderChallengeArea();
    const missionId = parseHashMission();
    if (missionId && missionById(missionId)) selectMission(missionId, false);
    else if (viewFromHash()) setView(viewFromHash());
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
