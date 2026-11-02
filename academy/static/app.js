(() => {
  'use strict';

  const TOKEN_KEY = 'va_session_token';
  const POLL_MS = 8000;
  const API_BASE = window.__ACADEMY_API_BASE__ || '';

  const state = {
    token: null,
    user: null,
    catalog: null,
    me: null,
    selectedFamily: null,
    selectedMission: null,
    pendingTools: [],
    refreshTimer: null,
    refreshing: false,
    sessionReady: false,
    completedSignature: null,
  };

  const refs = {
    authScreen: document.querySelector('#auth-screen'),
    workspace: document.querySelector('#workspace'),
    authFeedback: document.querySelector('#auth-feedback'),
    authTabs: Array.from(document.querySelectorAll('[data-auth-tab]')),
    authForms: Array.from(document.querySelectorAll('[data-auth-form]')),
    familyNav: document.querySelector('#family-nav'),
    familyCount: document.querySelector('#family-count'),
    chapterPanel: document.querySelector('#chapter-panel'),
    chaptersToggle: document.querySelector('#chapters-toggle'),
    briefingIndex: document.querySelector('#briefing-index'),
    briefingTitle: document.querySelector('#briefing-title'),
    briefingConcept: document.querySelector('#briefing-concept'),
    guideContent: document.querySelector('#guide-content'),
    guideTitle: document.querySelector('#guide-title'),
    levelCount: document.querySelector('#level-count'),
    missionTitle: document.querySelector('#mission-title'),
    missionState: document.querySelector('#mission-state'),
    missionContent: document.querySelector('#mission-content'),
    evidenceState: document.querySelector('#evidence-state'),
    evidenceCriterion: document.querySelector('#evidence-criterion'),
    evidenceStatus: document.querySelector('#evidence-status'),
    evidenceCommand: document.querySelector('#evidence-command'),
    evidenceRunner: document.querySelector('#evidence-runner'),
    evidenceBody: document.querySelector('#evidence-body'),
    evidenceDetails: document.querySelector('#evidence-details'),
    evidenceMeta: document.querySelector('#evidence-meta'),
    copyEvidenceCommand: document.querySelector('#copy-evidence-command'),
    tutorLog: document.querySelector('#tutor-log'),
    tutorForm: document.querySelector('#tutor-form'),
    tutorMessage: document.querySelector('#tutor-message'),
    toolApproval: document.querySelector('#tool-approval'),
    kaliToggle: document.querySelector('#kali-toggle'),
    kaliFrameWrap: document.querySelector('#kali-frame-wrap'),
    kaliFrame: document.querySelector('#kali-frame'),
    historyList: document.querySelector('#history-list'),
    scoreValue: document.querySelector('#score-value'),
    scoreMaximum: document.querySelector('#score-maximum'),
    progressValue: document.querySelector('#progress-value'),
    sessionStatus: document.querySelector('#session-status'),
    footerUser: document.querySelector('#footer-user'),
    refreshButton: document.querySelector('#refresh-button'),
    logoutButton: document.querySelector('#logout-button'),
    exportButton: document.querySelector('#export-button'),
    toastRegion: document.querySelector('#toast-region'),
  };

  function createElement(tagName, options = {}, children = []) {
    const node = document.createElement(tagName);
    Object.entries(options).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === 'className') node.className = value;
      else if (key === 'text') node.textContent = String(value);
      else if (key === 'htmlFor') node.htmlFor = value;
      else if (key === 'dataset') Object.entries(value).forEach(([dataKey, dataValue]) => { node.dataset[dataKey] = String(dataValue); });
      else if (key === 'disabled') node.disabled = Boolean(value);
      else if (key === 'checked') node.checked = Boolean(value);
      else if (key === 'ariaLabel') node.setAttribute('aria-label', value);
      else if (key.startsWith('aria-')) node.setAttribute(key, value);
      else node.setAttribute(key, value);
    });
    const list = Array.isArray(children) ? children : [children];
    list.forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    });
    return node;
  }

  function replaceContent(node, children) {
    node.replaceChildren();
    const list = Array.isArray(children) ? children : [children];
    list.forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    });
  }

  function setVisible(node, visible) {
    node.classList.toggle('is-hidden', !visible);
  }

  function jsonText(value, fallback = '') {
    if (value === undefined || value === null) return fallback;
    if (typeof value === 'string') return value;
    try {
      return JSON.stringify(value, null, 2);
    } catch (error) {
      return String(value);
    }
  }

  function displayValue(value, fallback = '—') {
    if (value === undefined || value === null || value === '') return fallback;
    return String(value);
  }

  function showToast(message, type = 'info') {
    const toast = createElement('div', { className: `toast toast-${type}`, role: 'status', text: message });
    refs.toastRegion.append(toast);
    window.setTimeout(() => toast.remove(), 4200);
  }

  function setAuthFeedback(message, type = 'error') {
    refs.authFeedback.textContent = message;
    refs.authFeedback.className = `feedback ${message ? `feedback-${type}` : ''}`;
  }

  function showWorkspace(show) {
    setVisible(refs.authScreen, !show);
    setVisible(refs.workspace, show);
  }

  function setSessionStatus(label, online = true) {
    const dot = refs.sessionStatus.querySelector('.status-dot');
    refs.sessionStatus.lastChild.textContent = ` ${label}`;
    if (dot) dot.classList.toggle('is-online', online);
    refs.sessionStatus.classList.toggle('is-warning', !online);
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (!headers.has('Accept')) headers.set('Accept', 'application/json');
    if (state.token) headers.set('Authorization', `Bearer ${state.token}`);
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const contentType = response.headers.get('content-type') || '';
    let payload;
    if (contentType.includes('application/json')) {
      payload = await response.json().catch(() => ({}));
    } else {
      payload = await response.text();
    }
    if (!response.ok) {
      const detail = payload && typeof payload === 'object' ? (payload.message || payload.error || payload.detail) : payload;
      const error = new Error(detail || `La API devolvió HTTP ${response.status}.`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function readToken() {
    try {
      return window.sessionStorage.getItem(TOKEN_KEY);
    } catch (error) {
      return null;
    }
  }

  function saveToken(token) {
    state.token = token;
    try {
      if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
      else window.sessionStorage.removeItem(TOKEN_KEY);
    } catch (error) {
      showToast('No se pudo guardar la sesión en sessionStorage.', 'error');
    }
  }

  function normalizeFamilies(catalog) {
    return catalog && Array.isArray(catalog.families) ? catalog.families : [];
  }

  function allMissions() {
    return state.catalog && Array.isArray(state.catalog.missions) ? state.catalog.missions : [];
  }

  function familyMissions(family) {
    if (!family) return [];
    const missions = allMissions();
    const familyId = normalizeFamilyId(family.id);
    const ids = Array.isArray(family.exercises)
      ? family.exercises.map((item) => (item && typeof item === 'object' ? (item.id || item.mission_id || item.missionId) : item)).filter(Boolean)
      : [];
    return missions.filter((mission) => {
      const missionFamily = normalizeFamilyId(mission.family_id || mission.familyId || mission.family);
      return missionFamily === familyId || ids.some((id) => String(id) === String(mission.id));
    });
  }

  function normalizeFamilyId(value) {
    if (value && typeof value === 'object') value = value.id || value.family_id || value.familyId;
    return value === undefined || value === null ? '' : String(value).trim().toLowerCase().replace(/[\s_-]+/g, '');
  }

  function findMission(missionId) {
    return allMissions().find((mission) => String(mission.id) === String(missionId)) || null;
  }

  function isCompleted(missionId) {
    return Boolean(state.me && Array.isArray(state.me.completed) && state.me.completed.some((id) => String(id) === String(missionId)));
  }

  function setActiveFamilyDetails(familyId) {
    const details = Array.from(refs.familyNav.querySelectorAll('details[data-family-id]'))
      .find((item) => item.dataset.familyId === String(familyId));
    if (details) details.open = true;
  }

  function renderFamilyNav() {
    const families = normalizeFamilies(state.catalog);
    refs.familyCount.textContent = families.length ? String(families.length).padStart(2, '0') : '—';
    replaceContent(refs.familyNav, []);
    if (!families.length) {
      refs.familyNav.append(createElement('p', { className: 'empty-state', text: 'El backend no devolvió familias.' }));
      return;
    }
    families.forEach((family, familyIndex) => {
      const missions = familyMissions(family);
      const levels = Array.isArray(family.levels) ? family.levels : [];
      const summary = createElement('summary', { className: 'family-summary' }, [
        createElement('span', { className: 'family-index', text: String(familyIndex + 1).padStart(2, '0') }),
        createElement('span', { className: 'family-summary-copy' }, [
          createElement('strong', { text: displayValue(family.title, `Familia ${familyIndex + 1}`) }),
          createElement('small', { text: `${missions.length} misión${missions.length === 1 ? '' : 'es'} · ${levels.length} nivel${levels.length === 1 ? '' : 'es'}` }),
        ]),
        createElement('span', { className: 'chevron', text: '›', ariaHidden: 'true' }),
      ]);
      const details = createElement('details', { className: 'family-item', dataset: { familyId: family.id || familyIndex } }, [summary]);
      const body = createElement('div', { className: 'family-body' });
      body.append(createElement('p', { className: 'family-concept', text: displayValue(family.concept, 'Sin concepto publicado.') }));
      if (levels.length) {
        const levelDetails = createElement('details', { className: 'levels-disclosure' });
        levelDetails.append(createElement('summary', { text: `Niveles de referencia (${levels.length})` }));
        const levelList = createElement('div', { className: 'mini-level-list' });
        levels.forEach((level, levelIndex) => levelList.append(renderMiniLevel(level, levelIndex)));
        levelDetails.append(levelList);
        body.append(levelDetails);
      }
      const missionHeading = createElement('p', { className: 'mini-heading', text: 'Misiones' });
      body.append(missionHeading);
      const missionList = createElement('div', { className: 'mission-list' });
      if (!missions.length) {
        missionList.append(createElement('p', { className: 'empty-state small', text: 'No hay misiones asociadas.' }));
      } else {
        missions.forEach((mission, missionIndex) => {
          const done = isCompleted(mission.id);
          const missionButton = createElement('button', {
            type: 'button',
            className: `mission-link ${done ? 'is-complete' : ''}`,
            dataset: { missionId: mission.id },
            ariaLabel: `Abrir misión ${displayValue(mission.title, mission.id)}`,
          }, [
            createElement('span', { className: 'mission-link-index', text: String(missionIndex + 1).padStart(2, '0') }),
            createElement('span', { className: 'mission-link-copy' }, [
              createElement('strong', { text: displayValue(mission.title, `Misión ${mission.id}`) }),
              createElement('small', { text: done ? 'completada según el backend' : `${displayValue(mission.method, 'REQ')} ${displayValue(mission.route, 'ruta local')}` }),
            ]),
            createElement('span', { className: 'mission-mark', text: done ? '✓' : '·', ariaHidden: 'true' }),
          ]);
          missionButton.addEventListener('click', () => selectMission(mission, family));
          missionList.append(missionButton);
        });
      }
      body.append(missionList);
      details.append(body);
      details.addEventListener('toggle', () => {
        if (details.open) selectFamily(family, false);
      });
      refs.familyNav.append(details);
    });
  }

  function renderMiniLevel(level, index) {
    const route = `${displayValue(level.method, 'REQ')} ${displayValue(level.route, 'ruta')}`;
    const article = createElement('article', { className: 'mini-level' }, [
      createElement('div', { className: 'mini-level-heading' }, [
        createElement('span', { className: 'level-code', text: `L${String(index + 1).padStart(2, '0')}` }),
        createElement('code', { text: route }),
      ]),
      createElement('p', { text: displayValue(level.behavior, displayValue(level.notes, 'Nivel documentado por el backend.')) }),
    ]);
    if (level.vulnerable !== undefined) article.append(createElement('span', { className: `vulnerability-flag ${level.vulnerable ? 'is-vulnerable' : 'is-control'}`, text: level.vulnerable ? 'superficie vulnerable' : 'control / mitigado' }));
    return article;
  }

  function selectFamily(family, selectFirstMission = true) {
    if (!family) return;
    state.selectedFamily = family;
    setActiveFamilyDetails(family.id);
    const familyIndex = normalizeFamilies(state.catalog).indexOf(family);
    refs.briefingIndex.textContent = familyIndex >= 0 ? String(familyIndex + 1).padStart(2, '0') : '—';
    refs.briefingTitle.textContent = displayValue(family.title, 'Capítulo sin título');
    refs.briefingConcept.textContent = displayValue(family.concept, 'Este capítulo no tiene concepto publicado.');
    refs.guideTitle.textContent = `Guía / ${displayValue(family.title, 'capítulo')}`;
    renderGuide(family);
    if (selectFirstMission) {
      const missions = familyMissions(family);
      const currentInFamily = state.selectedMission && missions.some((mission) => mission.id === state.selectedMission.id);
      if (!currentInFamily) selectMission(missions[0] || null, family);
    }
  }

  function renderGuide(family) {
    const levels = Array.isArray(family.levels) ? family.levels : [];
    refs.levelCount.textContent = levels.length ? String(levels.length).padStart(2, '0') : '—';
    replaceContent(refs.guideContent, []);
    const intro = createElement('div', { className: 'guide-intro' }, [
      createElement('p', { className: 'lead', text: displayValue(family.concept, 'El backend no publicó una explicación para esta familia.') }),
      createElement('p', { className: 'muted', text: 'Lee la progresión antes de ejecutar una prueba en Kali. Los ejemplos sirven como documentación; esta interfaz no dispara ataques automáticamente.' }),
    ]);
    refs.guideContent.append(intro);
    if (!levels.length) {
      refs.guideContent.append(createElement('p', { className: 'empty-state', text: 'No hay niveles documentados para esta familia.' }));
      return;
    }
    const levelGrid = createElement('div', { className: 'level-grid' });
    levels.forEach((level, index) => {
      const params = Array.isArray(level.parameters) ? level.parameters : [];
      const card = createElement('article', { className: 'level-card' }, [
        createElement('div', { className: 'level-card-top' }, [
          createElement('span', { className: 'level-code', text: `NIVEL ${String(index + 1).padStart(2, '0')}` }),
          createElement('code', { text: `${displayValue(level.method, 'REQ')} ${displayValue(level.route, 'ruta local')}` }),
        ]),
        createElement('p', { className: 'level-behavior', text: displayValue(level.behavior, 'Comportamiento descrito por el backend.') }),
      ]);
      if (level.vulnerable !== undefined) card.append(createElement('span', { className: `vulnerability-flag ${level.vulnerable ? 'is-vulnerable' : 'is-control'}`, text: level.vulnerable ? 'superficie vulnerable' : 'control / mitigado' }));
      if (level.notes) card.append(createElement('p', { className: 'level-notes', text: `Nota: ${level.notes}` }));
      if (params.length) {
        const paramList = createElement('ul', { className: 'parameter-list' });
        params.forEach((param) => paramList.append(createElement('li', { text: typeof param === 'string' ? param : jsonText(param) })));
        card.append(createElement('p', { className: 'criterion-label', text: 'Parámetros documentados' }), paramList);
      }
      levelGrid.append(card);
    });
    refs.guideContent.append(levelGrid);
  }

  function selectMission(mission, family = state.selectedFamily) {
    state.selectedMission = mission || null;
    resetEvidence();
    if (family) selectFamilyWithoutMission(family);
    renderMission();
    refs.tutorMessage.focus({ preventScroll: true });
    if (window.innerWidth < 900) refs.missionTitle.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function selectFamilyWithoutMission(family) {
    if (!family) return;
    state.selectedFamily = family;
    setActiveFamilyDetails(family.id);
    const familyIndex = normalizeFamilies(state.catalog).indexOf(family);
    refs.briefingIndex.textContent = familyIndex >= 0 ? String(familyIndex + 1).padStart(2, '0') : '—';
    refs.briefingTitle.textContent = displayValue(family.title, 'Capítulo sin título');
    refs.briefingConcept.textContent = displayValue(family.concept, 'Este capítulo no tiene concepto publicado.');
    refs.guideTitle.textContent = `Guía / ${displayValue(family.title, 'capítulo')}`;
    renderGuide(family);
  }

  function makeRequestTemplate(mission) {
    const template = {
      method: displayValue(mission.method, 'GET'),
      params: {},
      headers: {},
      body: '',
      content_type: displayValue(mission.content_type, ''),
    };
    return JSON.stringify(template, null, 2);
  }

  function missionCheckText(mission) {
    const fallback = 'El backend no publicó el criterio del verificador.';
    return mission && mission.check !== undefined && mission.check !== null ? jsonText(mission.check, fallback) : fallback;
  }

  function isManualMission(mission) {
    return Boolean(mission && mission.check && typeof mission.check === 'object' && mission.check.kind === 'manual');
  }

  function missionCommand(mission) {
    return mission && mission.command !== undefined && mission.command !== null ? String(mission.command) : '';
  }

  function renderMission() {
    const mission = state.selectedMission;
    if (!mission) {
      refs.missionTitle.textContent = 'Selecciona una misión';
      refs.missionState.textContent = 'SIN SELECCIÓN';
      refs.missionState.className = 'state-badge';
      replaceContent(refs.missionContent, createElement('div', { className: 'mission-empty' }, [createElement('p', { text: 'Selecciona una misión de la lista de capítulos. Aquí aparecerán el criterio verificable, el comando de referencia y el editor de solicitud.' })]));
      resetEvidence();
      return;
    }
    const completed = isCompleted(mission.id);
    refs.missionTitle.textContent = displayValue(mission.title, `Misión ${mission.id}`);
    refs.missionState.textContent = completed ? 'COMPLETADA' : 'ABIERTA';
    refs.missionState.className = `state-badge ${completed ? 'state-success' : ''}`;
    const content = createElement('div', { className: 'mission-content' });
    const top = createElement('div', { className: 'mission-overview' }, [
      createElement('p', { className: 'lead', text: displayValue(mission.description, 'El backend no publicó una descripción para esta misión.') }),
      createElement('div', { className: 'mission-facts' }, [
        createElement('span', { className: 'fact-chip' }, [createElement('small', { text: 'RUTA' }), createElement('code', { text: displayValue(mission.route, 'ruta local') })]),
        createElement('span', { className: 'fact-chip' }, [createElement('small', { text: 'MÉTODO' }), createElement('code', { text: displayValue(mission.method, 'REQ') })]),
        createElement('span', { className: 'fact-chip' }, [createElement('small', { text: 'RECOMPENSA DEFINIDA' }), createElement('strong', { text: isManualMission(mission) ? '0 XP' : (mission.points !== undefined && mission.points !== null ? `${mission.points} XP` : 'por backend') })]),
      ]),
    ]);
    content.append(top);

    const split = createElement('div', { className: 'mission-split' });
    const docs = createElement('div', { className: 'mission-docs' });
    docs.append(createElement('div', { className: 'doc-block' }, [createElement('p', { className: 'criterion-label', text: 'Criterio verificable' }), createElement('p', { className: 'criterion-copy', text: missionCheckText(mission) })]));
    if (mission.explanation) docs.append(createElement('div', { className: 'doc-block' }, [createElement('p', { className: 'criterion-label', text: 'Por qué importa' }), createElement('p', { text: mission.explanation })]));
    if (mission.mitigation) docs.append(createElement('div', { className: 'doc-block mitigation-block' }, [createElement('p', { className: 'criterion-label', text: 'Mitigación' }), createElement('p', { text: mission.mitigation })]));
    if (Array.isArray(mission.steps) && mission.steps.length) docs.append(renderNumberedDoc('Pasos de estudio', mission.steps));
    if (Array.isArray(mission.hints) && mission.hints.length) docs.append(renderNumberedDoc('Pistas', mission.hints));
    docs.append(createElement('p', { className: 'manual-note', text: isManualMission(mission) ? 'Esta misión requiere verificación manual y no es puntuable: 0 XP. El backend no adjudica puntos para este criterio.' : 'La explicación manual sirve para aprender; solo el verificador del laboratorio puede adjudicar XP.' }));
    split.append(docs);

    const editor = createElement('div', { className: 'request-editor' });
    const editorHeading = createElement('div', { className: 'code-caption' }, [createElement('span', { text: 'EDITOR DE SOLICITUD' }), createElement('span', { className: 'editor-safety', text: isManualMission(mission) ? 'MANUAL / NO PUNTUABLE · 0 XP' : 'CONTROL BENIGNO / VACÍO' })]);
    const requestTextarea = createElement('textarea', { className: 'request-textarea', rows: 13, spellcheck: 'false', 'aria-label': 'Solicitud JSON editable' });
    requestTextarea.value = makeRequestTemplate(mission);
    const help = createElement('p', { className: 'editor-help', text: isManualMission(mission) ? 'Esta solicitud puede servir para observar la respuesta, pero esta misión requiere revisión manual y no es puntuable. Usa objetos JSON con parámetros y headers de texto; no se envían valores malformados.' : 'Edita solo la solicitud que deseas enviar: el laboratorio ejecuta únicamente la solicitud del alumno contra el target y evalúa la evidencia devuelta. No es un botón de “completar” y no se rellena con un exploit al seleccionar la misión.' });
    const editorActions = createElement('div', { className: 'editor-actions' });
    const sendButton = createElement('button', { className: 'button button-primary', type: 'button', text: 'Enviar mi prueba al laboratorio' });
    sendButton.addEventListener('click', () => submitAttempt(requestTextarea, sendButton));
    editorActions.append(sendButton);
    editor.append(editorHeading, requestTextarea, help, editorActions);
    split.append(editor);
    content.append(split);

    const commandText = missionCommand(mission);
    const command = createElement('div', { className: 'command-card' }, [
      createElement('div', { className: 'code-caption' }, [createElement('span', { text: 'COMANDO DE REFERENCIA PARA KALI' }), createElement('button', { className: 'text-button', type: 'button', text: 'Copiar comando' })]),
      createElement('pre', { className: 'code-block', text: commandText || 'El catálogo no publicó un comando de referencia.' }),
      createElement('p', { className: 'command-help', text: 'Cópialo para ejecutarlo tú en Kali. La UI solo registra el JSON que envías desde el editor.' }),
    ]);
    const commandCopyButton = command.querySelector('.text-button');
    commandCopyButton.disabled = !commandText;
    commandCopyButton.addEventListener('click', () => copyText(commandText, commandCopyButton));
    content.append(command);
    replaceContent(refs.missionContent, content);
    refs.evidenceCriterion.textContent = missionCheckText(mission);
  }

  function renderNumberedDoc(title, items) {
    const block = createElement('div', { className: 'doc-block' }, [createElement('p', { className: 'criterion-label', text: title })]);
    const list = createElement('ol', { className: 'steps-list' });
    items.forEach((item) => list.append(createElement('li', { text: typeof item === 'string' ? item : jsonText(item) })));
    block.append(list);
    return block;
  }

  function resetEvidence() {
    state.pendingTools = [];
    replaceContent(refs.toolApproval, []);
    refs.toolApproval.classList.add('is-hidden');
    replaceContent(refs.tutorLog, createElement('div', { className: 'tutor-message tutor-system' }, [
      createElement('span', { className: 'message-label', text: 'SISTEMA' }),
      createElement('p', { text: 'Selecciona una misión y formula una pregunta concreta para recibir orientación.' }),
    ]));
    refs.tutorMessage.value = '';
    refs.evidenceState.textContent = 'SIN EVIDENCIA TODAVÍA';
    refs.evidenceState.className = 'state-badge';
    refs.evidenceCriterion.textContent = 'Selecciona una misión para ver qué debe demostrar tu solicitud.';
    refs.evidenceStatus.textContent = '—';
    refs.evidenceCommand.textContent = 'Sin comando de referencia todavía';
    refs.evidenceRunner.textContent = 'Sin evidencia del runner todavía';
    refs.evidenceBody.textContent = 'Sin evidencia todavía';
    refs.evidenceMeta.textContent = '';
    refs.evidenceDetails.classList.add('is-hidden');
    refs.copyEvidenceCommand.disabled = true;
    refs.copyEvidenceCommand.onclick = null;
  }

  function runnerEvidenceRecords(evidence) {
    if (!evidence || typeof evidence !== 'object' || Array.isArray(evidence)) return [];
    const isDirect = ['status', 'headers', 'body', 'exit_code', 'browser_dataset'].some((key) => Object.prototype.hasOwnProperty.call(evidence, key));
    if (isDirect) return [['runner', evidence]];
    return Object.entries(evidence).filter(([, value]) => value && typeof value === 'object' && !Array.isArray(value));
  }

  function primaryRunnerEvidence(evidence) {
    const records = runnerEvidenceRecords(evidence);
    return (records.find(([label]) => label === 'probe') || records.find(([label]) => label === 'attack') || records.find(([label]) => label === 'runner') || records[0] || ['', {}])[1];
  }

  function runnerProperties(evidence) {
    const records = runnerEvidenceRecords(evidence);
    if (records.length === 1 && records[0][0] === 'runner') {
      const value = records[0][1];
      return {
        exit_code: value.exit_code === undefined ? null : value.exit_code,
        browser_dataset: value.browser_dataset === undefined ? null : value.browser_dataset,
      };
    }
    if (!records.length) return evidence;
    return Object.fromEntries(records.map(([label, value]) => [label, {
      exit_code: value.exit_code === undefined ? null : value.exit_code,
      browser_dataset: value.browser_dataset === undefined ? null : value.browser_dataset,
    }]));
  }

  function renderEvidence(result) {
    const evidence = result && result.evidence ? result.evidence : {};
    const primary = primaryRunnerEvidence(evidence);
    const success = Boolean(result && result.success);
    refs.evidenceState.textContent = success ? 'VERIFICACIÓN POSITIVA' : 'EVALUADA / REVISAR';
    refs.evidenceState.className = `state-badge ${success ? 'state-success' : 'state-warning'}`;
    refs.evidenceStatus.textContent = displayValue(primary.status, '—');
    const commandText = missionCommand(state.selectedMission);
    refs.evidenceCommand.textContent = commandText || 'El catálogo no publicó un comando de referencia.';
    refs.evidenceRunner.textContent = jsonText(runnerProperties(evidence), 'Sin evidencia del runner.');
    refs.evidenceBody.textContent = primary.body !== undefined ? jsonText(primary.body, '') : (Object.keys(evidence).length ? jsonText(evidence, '{}') : 'El backend no devolvió body.');
    const meta = {
      message: result && result.message,
      headers: primary.headers,
      score: result && result.score,
    };
    refs.evidenceMeta.textContent = jsonText(meta, 'Sin detalle adicional.');
    refs.evidenceDetails.classList.remove('is-hidden');
    refs.copyEvidenceCommand.disabled = !commandText;
    refs.copyEvidenceCommand.onclick = () => copyText(commandText, refs.copyEvidenceCommand);
  }

  async function submitAttempt(textarea, button) {
    if (!state.selectedMission) {
      showToast('Selecciona una misión antes de enviar una prueba.', 'error');
      return;
    }
    const mission = state.selectedMission;
    const sessionToken = state.token;
    let parsed;
    try {
      parsed = JSON.parse(textarea.value);
    } catch (error) {
      showToast('El editor no contiene JSON válido.', 'error');
      textarea.focus();
      return;
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      showToast('La solicitud debe ser un objeto JSON.', 'error');
      return;
    }
    const isTextMap = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
      && Object.values(value).every((item) => typeof item === 'string');
    if (typeof parsed.method !== 'string' || !parsed.method.trim()) {
      showToast('La solicitud debe incluir un método HTTP de texto.', 'error');
      return;
    }
    if ((parsed.params !== undefined && !isTextMap(parsed.params)) || (parsed.headers !== undefined && !isTextMap(parsed.headers))) {
      showToast('params y headers deben ser objetos con valores de texto; no se envió la solicitud.', 'error');
      return;
    }
    if (parsed.body !== undefined && parsed.body !== null && typeof parsed.body !== 'string') {
      showToast('body debe ser texto o null; no se envió la solicitud.', 'error');
      return;
    }
    if (parsed.content_type !== undefined && parsed.content_type !== null && typeof parsed.content_type !== 'string') {
      showToast('content_type debe ser texto o null; no se envió la solicitud.', 'error');
      return;
    }
    const request = {
      method: parsed.method,
      params: parsed.params === undefined ? {} : parsed.params,
      headers: parsed.headers === undefined ? {} : parsed.headers,
      body: parsed.body === undefined || parsed.body === null ? '' : parsed.body,
      content_type: parsed.content_type === undefined || parsed.content_type === null ? '' : parsed.content_type,
    };
    button.disabled = true;
    button.textContent = 'Enviando solicitud…';
    try {
      const result = await api('/api/attempt', {
        method: 'POST',
        body: JSON.stringify({ mission_id: mission.id, request }),
      });
      if (state.token !== sessionToken || !state.selectedMission || String(state.selectedMission.id) !== String(mission.id)) return;
      renderEvidence(result);
      await refreshProgress(true);
      showToast(result && result.success ? 'El laboratorio verificó evidencia positiva.' : 'La solicitud fue evaluada; revisa la evidencia devuelta.', result && result.success ? 'success' : 'info');
    } catch (error) {
      refs.evidenceState.textContent = 'ERROR DE LABORATORIO';
      refs.evidenceState.className = 'state-badge state-warning';
      refs.evidenceBody.textContent = error.message;
      refs.evidenceDetails.classList.add('is-hidden');
      showToast(`No se pudo enviar la prueba: ${error.message}`, 'error');
    } finally {
      button.disabled = false;
      button.textContent = 'Enviar mi prueba al laboratorio';
    }
  }

  function renderMe(me) {
    state.me = me || {};
    const score = state.me.score;
    const maximum = state.me.maximum;
    refs.scoreValue.textContent = score === undefined || score === null ? '—' : String(score);
    refs.scoreMaximum.textContent = maximum === undefined || maximum === null ? '/ —' : `/ ${maximum}`;
    if (typeof score === 'number' && typeof maximum === 'number' && maximum > 0) {
      refs.progressValue.textContent = `${Math.max(0, Math.min(100, Math.round((score / maximum) * 100)))}%`;
    } else {
      refs.progressValue.textContent = '—%';
    }
    if (state.user && state.user.username) refs.footerUser.textContent = `usuario: ${state.user.username}`;
    renderHistory();
    const completed = Array.isArray(state.me.completed) ? state.me.completed : [];
    const completedSignature = completed.map((id) => String(id)).sort().join('|');
    const completionChanged = completedSignature !== state.completedSignature;
    state.completedSignature = completedSignature;
    if (state.catalog && completionChanged) {
      renderFamilyNav();
      if (state.selectedFamily) setActiveFamilyDetails(state.selectedFamily.id);
      if (state.selectedMission) updateMissionStateBadge();
    }
  }

  function updateMissionStateBadge() {
    if (!state.selectedMission) return;
    const completed = isCompleted(state.selectedMission.id);
    refs.missionState.textContent = completed ? 'COMPLETADA' : 'ABIERTA';
    refs.missionState.className = `state-badge ${completed ? 'state-success' : ''}`;
  }

  function renderHistory() {
    const completed = Array.isArray(state.me && state.me.completed) ? state.me.completed : [];
    const events = Array.isArray(state.me && state.me.events) ? state.me.events : [];
    replaceContent(refs.historyList, []);
    if (!completed.length && !events.length) {
      refs.historyList.append(createElement('p', { className: 'empty-state', text: 'Aún no hay eventos locales.' }));
      return;
    }
    if (completed.length) {
      const completedBlock = createElement('div', { className: 'history-section' }, [createElement('p', { className: 'criterion-label', text: 'Completadas según el backend' })]);
      const completedList = createElement('ul', { className: 'history-items' });
      completed.forEach((missionId) => {
        const mission = findMission(missionId);
        const item = createElement('li', { className: 'history-item history-complete' }, [
          createElement('span', { className: 'history-mark', text: '✓' }),
          createElement('span', { text: displayValue(mission ? mission.title : missionId, `Misión ${missionId}`) }),
        ]);
        completedList.append(item);
      });
      completedBlock.append(completedList);
      refs.historyList.append(completedBlock);
    }
    if (events.length) {
      const eventsBlock = createElement('div', { className: 'history-section' }, [createElement('p', { className: 'criterion-label', text: 'Eventos recientes' })]);
      const eventList = createElement('ul', { className: 'history-items' });
      events.slice(0, 8).forEach((event) => {
        const id = event && (event.mission_id || event.missionId || event.id);
        const mission = findMission(id);
        const status = event && (event.success === true || event.status === 'success') ? 'positivo' : 'registrado';
        const timestamp = event && (event.created_at || event.createdAt || event.timestamp);
        eventList.append(createElement('li', { className: 'history-item' }, [
          createElement('span', { className: `history-dot ${status === 'positivo' ? 'is-positive' : ''}` }),
          createElement('span', { className: 'history-event-copy' }, [
            createElement('strong', { text: displayValue(mission ? mission.title : id, 'Evento de laboratorio') }),
            createElement('small', { text: `${status}${timestamp ? ` · ${timestamp}` : ''}` }),
          ]),
        ]));
      });
      eventsBlock.append(eventList);
      refs.historyList.append(eventsBlock);
    }
  }

  function appendTutorMessage(label, text, type = 'assistant') {
    const message = createElement('div', { className: `tutor-message tutor-${type}` }, [
      createElement('span', { className: 'message-label', text: label }),
      createElement('p', { text: displayValue(text, 'Sin contenido.') }),
    ]);
    refs.tutorLog.append(message);
    message.scrollIntoView({ block: 'nearest' });
  }

  function renderToolApproval(tools) {
    state.pendingTools = Array.isArray(tools) ? tools : [];
    replaceContent(refs.toolApproval, []);
    if (!state.pendingTools.length) {
      refs.toolApproval.classList.add('is-hidden');
      return;
    }
    refs.toolApproval.classList.remove('is-hidden');
    refs.toolApproval.append(createElement('p', { className: 'criterion-label', text: 'PROPUESTA DE HERRAMIENTA — REQUIERE APROBACIÓN' }));
    state.pendingTools.forEach((tool) => {
      const item = createElement('div', { className: 'tool-card' }, [
        createElement('strong', { text: displayValue(tool.tool, 'herramienta sin nombre') }),
        createElement('pre', { className: 'tool-arguments', text: jsonText(tool.arguments, '{}') }),
      ]);
      const approve = createElement('button', { className: 'button button-secondary button-wide', type: 'button', text: 'Aprobar esta herramienta' });
      approve.addEventListener('click', () => approveTool(tool, approve));
      item.append(approve);
      refs.toolApproval.append(item);
    });
  }

  async function submitTutor(event) {
    event.preventDefault();
    const message = refs.tutorMessage.value.trim();
    if (!state.selectedMission) {
      showToast('Selecciona una misión para dar contexto al tutor.', 'error');
      return;
    }
    if (!message) {
      refs.tutorMessage.focus();
      return;
    }
    const mission = state.selectedMission;
    const sessionToken = state.token;
    appendTutorMessage('TÚ', message, 'user');
    refs.tutorMessage.value = '';
    const submitButton = refs.tutorForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
      const result = await api('/api/tutor', {
        method: 'POST',
        body: JSON.stringify({ mission_id: mission.id, message, allow_tools: false }),
      });
      if (state.token !== sessionToken || !state.selectedMission || String(state.selectedMission.id) !== String(mission.id)) return;
      appendTutorMessage('QWEN', result && result.reply ? result.reply : 'El tutor no devolvió una respuesta.', 'assistant');
      renderToolApproval(result && result.pending_tools);
      if (result && result.audit) appendTutorMessage('AUDITORÍA', jsonText(result.audit), 'system');
    } catch (error) {
      appendTutorMessage('QWEN / ERROR', `No se pudo consultar al tutor: ${error.message}`, 'system');
      showToast('El tutor informó un error; no se cambió el progreso.', 'error');
    } finally {
      submitButton.disabled = false;
    }
  }

  async function approveTool(tool, button) {
    const pendingId = tool && (tool.id || tool.pending_id || tool.pendingId);
    if (!pendingId) {
      showToast('La propuesta no incluye pending_id; no se puede aprobar.', 'error');
      return;
    }
    const mission = state.selectedMission;
    const sessionToken = state.token;
    button.disabled = true;
    button.textContent = 'Aprobando…';
    try {
      const result = await api('/api/tutor/approve', {
        method: 'POST',
        body: JSON.stringify({ pending_id: pendingId }),
      });
      if (state.token !== sessionToken || !state.selectedMission || !mission || String(state.selectedMission.id) !== String(mission.id)) return;
      appendTutorMessage('QWEN / HERRAMIENTA', result && result.reply ? result.reply : 'Herramienta aprobada; revisa la respuesta.', 'assistant');
      renderToolApproval(result && result.pending_tools);
      if (result && result.audit) appendTutorMessage('AUDITORÍA', jsonText(result.audit), 'system');
    } catch (error) {
      appendTutorMessage('APROBACIÓN / ERROR', `La herramienta no se ejecutó: ${error.message}`, 'system');
      button.disabled = false;
      button.textContent = 'Aprobar esta herramienta';
    }
  }

  async function copyText(text, button) {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      const original = button.textContent;
      button.textContent = 'Copiado';
      showToast('Texto copiado al portapapeles.', 'success');
      window.setTimeout(() => { button.textContent = original; }, 1600);
    } catch (error) {
      showToast('No se pudo copiar automáticamente; selecciónalo manualmente.', 'error');
    }
  }

  async function refreshProgress(silent = false) {
    if (!state.token || state.refreshing) return;
    state.refreshing = true;
    try {
      const me = await api('/api/me');
      renderMe(me);
      setSessionStatus('sincronizado', true);
    } catch (error) {
      setSessionStatus('sin conexión', false);
      if (!silent) showToast(`No se pudo actualizar el progreso: ${error.message}`, 'error');
      if (error.status === 401) logout(false);
    } finally {
      state.refreshing = false;
    }
  }

  async function refreshStatus() {
    try {
      await api('/api/status');
      setSessionStatus('API local disponible', true);
    } catch (error) {
      setSessionStatus('API no disponible', false);
    }
  }

  function startPolling() {
    stopPolling();
    state.refreshTimer = window.setInterval(() => refreshProgress(true), POLL_MS);
  }

  function stopPolling() {
    if (state.refreshTimer) window.clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }

  async function loadSession() {
    showWorkspace(true);
    setSessionStatus('cargando catálogo', true);
    try {
      const [catalog, me] = await Promise.all([api('/api/catalog'), api('/api/me')]);
      state.catalog = catalog || { families: [], missions: [] };
      state.me = me || {};
      if (!state.user && me && me.user) state.user = me.user;
      renderFamilyNav();
      renderMe(me);
      const families = normalizeFamilies(state.catalog);
      if (families.length) selectFamily(families[0], false);
      setSessionStatus('sincronizado', true);
      state.sessionReady = true;
      startPolling();
    } catch (error) {
      setSessionStatus('error de sesión', false);
      showToast(`No se pudo cargar el laboratorio: ${error.message}`, 'error');
      if (error.status === 401) logout(false);
    }
  }

  async function authenticate(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }
    const formData = new FormData(form);
    const username = String(formData.get('username') || '').trim();
    const password = String(formData.get('password') || '');
    if (password.length < 8) {
      setAuthFeedback('La contraseña debe tener al menos 8 caracteres.', 'error');
      return;
    }
    const mode = form.dataset.authForm;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    setAuthFeedback('Contactando la API local…', 'info');
    try {
      const result = await api(`/api/auth/${mode}`, { method: 'POST', body: JSON.stringify({ username, password }) });
      if (!result || !result.token) throw new Error('La API no devolvió token bearer.');
      saveToken(result.token);
      state.user = result.user || { username };
      setAuthFeedback('Sesión iniciada.', 'success');
      await loadSession();
    } catch (error) {
      saveToken(null);
      setAuthFeedback(`No se pudo ${mode === 'register' ? 'registrar la cuenta' : 'iniciar sesión'}: ${error.message}`, 'error');
    } finally {
      submit.disabled = false;
    }
  }

  function logout(showMessage = true) {
    stopPolling();
    saveToken(null);
    state.user = null;
    state.catalog = null;
    state.me = null;
    state.selectedFamily = null;
    state.selectedMission = null;
    state.pendingTools = [];
    state.sessionReady = false;
    state.completedSignature = null;
    resetEvidence();
    replaceContent(refs.historyList, createElement('p', { className: 'empty-state', text: 'Aún no hay eventos locales.' }));
    refs.scoreValue.textContent = '—';
    refs.scoreMaximum.textContent = '/ —';
    refs.progressValue.textContent = '—%';
    refs.footerUser.textContent = 'sin usuario';
    showWorkspace(false);
    if (showMessage) setAuthFeedback('Sesión cerrada. El token se eliminó de sessionStorage.', 'info');
    refs.authForms.forEach((form) => form.reset());
  }

  async function exportProgress() {
    if (!state.token) return;
    refs.exportButton.disabled = true;
    try {
      const response = await fetch(`${API_BASE}/api/export`, { headers: { Accept: 'application/json', Authorization: `Bearer ${state.token}` } });
      if (!response.ok) throw new Error(`La API devolvió HTTP ${response.status}.`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = createElement('a', { href: url, download: 'vulnerableapp-academy-export.json' });
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      showToast('Exportación JSON descargada.', 'success');
    } catch (error) {
      showToast(`No se pudo descargar la exportación: ${error.message}`, 'error');
    } finally {
      refs.exportButton.disabled = false;
    }
  }

  function setupTabs() {
    refs.authTabs.forEach((tab) => tab.addEventListener('click', () => {
      const target = tab.dataset.authTab;
      refs.authTabs.forEach((item) => {
        const active = item === tab;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      refs.authForms.forEach((form) => setVisible(form, form.dataset.authForm === target));
      setAuthFeedback('');
      const firstInput = document.querySelector(`[data-auth-form="${target}"] input`);
      if (firstInput) firstInput.focus();
    }));
  }

  function setupKaliToggle() {
    refs.kaliToggle.addEventListener('change', () => {
      const visible = refs.kaliToggle.checked;
      setVisible(refs.kaliFrameWrap, visible);
      if (visible && refs.kaliFrame.src === 'about:blank') refs.kaliFrame.src = '/kali/vnc.html?autoconnect=1&resize=scale&path=websockify';
    });
  }

  function setupMobileControls() {
    refs.chaptersToggle.addEventListener('click', () => {
      const visible = refs.chapterPanel.classList.toggle('is-mobile-open');
      refs.chaptersToggle.setAttribute('aria-expanded', visible ? 'true' : 'false');
    });
    document.querySelector('#workspace-focus').addEventListener('click', () => {
      refs.missionTitle.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      refs.chapterPanel.classList.remove('is-mobile-open');
      refs.chaptersToggle.setAttribute('aria-expanded', 'false');
      document.querySelectorAll('details[open]').forEach((details) => { if (details.classList.contains('levels-disclosure')) details.open = false; });
    });
  }

  function setupEvents() {
    setupTabs();
    refs.authForms.forEach((form) => form.addEventListener('submit', authenticate));
    refs.logoutButton.addEventListener('click', () => logout(true));
    refs.refreshButton.addEventListener('click', () => refreshProgress(false));
    refs.exportButton.addEventListener('click', exportProgress);
    refs.tutorForm.addEventListener('submit', submitTutor);
    setupKaliToggle();
    setupMobileControls();
  }

  async function boot() {
    setupEvents();
    await refreshStatus();
    const token = readToken();
    if (token) {
      state.token = token;
      try {
        const me = await api('/api/me');
        state.user = me && me.user ? me.user : null;
        await loadSession();
      } catch (error) {
        saveToken(null);
        showWorkspace(false);
        setAuthFeedback('La sesión guardada ya no es válida; vuelve a iniciar sesión.', 'info');
      }
    }
  }

  boot();
})();
