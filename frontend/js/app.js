// ============================================================
// app.js — ConnectOnion Studio SPA orchestrator
// Views: splash → agent list ⇄ create modal ⇄ detail drawer,
// full-screen onboarding when `co auth` is missing.
// Zero build: vanilla ES modules only.
// ============================================================

import * as api from './api.js';
import { statusSocket, logSocket } from './ws.js';
import { createOnion, playSplash } from './onion.js';
import { copyForClaude, copyText, copyWithFeedback } from './diagnostics.js';

const $ = (sel, root = document) => root.querySelector(sel);

// ---- state ----------------------------------------------------------
const state = {
  agents: [],
  cards: new Map(),          // slug → card element
  busy: new Set(),           // slugs with an action in flight
  drawerSlug: null,
  drawerDetail: null,
  logSock: null,
  statusSock: null,
  onboardingTimer: null,
  onboardingActive: false,
  setup: null,
  search: '',
};

// ---- helpers --------------------------------------------------------
const shortAddr = (addr) =>
  addr && addr.length > 14 ? `${addr.slice(0, 7)}…${addr.slice(-5)}` : (addr || '');
const capitalize = (s) => (s ? s[0].toUpperCase() + s.slice(1) : '');

function toast(message, kind = '') {
  const host = $('#toasts');
  const el = document.createElement('div');
  el.className = `toast glass${kind ? ` ${kind}` : ''}`;
  el.textContent = message;
  host.appendChild(el);
  setTimeout(() => {
    el.classList.add('leaving');
    el.addEventListener('animationend', () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 500); // fallback removal
  }, 3600);
}

// ---- theme -----------------------------------------------------------
// Light-only for now (dark isn't dialed in yet). `data-theme="light"` on <html>
// pins it so the system's dark preference can't leak through.
function initTheme() {
  document.documentElement.dataset.theme = 'light';
}

// ---- agent list -----------------------------------------------------
// row/action icons (Lucide-style, stroke 1.8 to match the rest of the UI)
const ICON = {
  port: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="8" x="2" y="2" rx="2"/><rect width="20" height="8" x="2" y="14" rx="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/></svg>`,
  toolkits: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>`,
  id: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 10a2 2 0 0 0-2 2c0 1.02-.1 2.51-.26 4"/><path d="M14 13.12c0 2.38 0 6.38-1 8.88"/><path d="M17.29 21.02c.12-.6.43-2.3.5-3.02"/><path d="M2 12a10 10 0 0 1 18-6"/><path d="M2 16h.01"/><path d="M21.8 16c.2-2 .131-5.354 0-6"/><path d="M5 19.5C5.5 18 6 15 6 12a6 6 0 0 1 .34-2"/><path d="M8.65 22c.21-.66.45-1.32.57-2"/><path d="M9 6.8a6 6 0 0 1 9 5.2c0 .47 0 1.17-.02 2"/></svg>`,
  model: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>`,
  copy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`,
  qr: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect width="5" height="5" x="3" y="3" rx="1"/><rect width="5" height="5" x="16" y="3" rx="1"/><rect width="5" height="5" x="3" y="16" rx="1"/><path d="M21 16h-3a2 2 0 0 0-2 2v3"/><path d="M21 21v.01"/><path d="M12 7v3a2 2 0 0 1-2 2H7"/><path d="M3 12h.01"/><path d="M12 3h.01"/><path d="M12 16v.01"/><path d="M16 12h1"/><path d="M21 12v.01"/><path d="M12 21v-1"/></svg>`,
  play: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15a1 1 0 0 0 1.5.87l12-7.5a1 1 0 0 0 0-1.74l-12-7.5A1 1 0 0 0 7 4.5Z"/></svg>`,
  stop: `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2.5"/></svg>`,
  access: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>`,
  dots: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"/></svg>`,
  rename: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`,
  pin: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V5a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>`,
  close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>`,
  back: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>`,
};

function agentCard(agent) {
  const card = document.createElement('article');
  card.className = 'agent-card';
  card.dataset.slug = agent.slug;
  card.tabIndex = 0;
  card.setAttribute('role', 'button');
  card.innerHTML = `
    <div class="card-inner">
      <div class="card-front">
        <div class="card-head">
          <span class="pin-flag" aria-hidden="true">${ICON.pin}</span>
          <h3 class="card-name"></h3>
          <div class="card-menu">
            <button class="card-menu-btn" title="More" aria-label="More actions" aria-haspopup="true">${ICON.dots}</button>
            <div class="card-menu-pop" hidden role="menu">
              <button class="menu-item" data-act="rename" role="menuitem">${ICON.rename}<span>Rename</span></button>
              <button class="menu-item" data-act="pin" role="menuitem">${ICON.pin}<span class="pin-label">Pin</span></button>
            </div>
          </div>
        </div>
        <div class="card-sub">
          <span class="card-state">
            <span class="status-dot"></span>
            <span class="status-onion"></span>
            <span class="state-word"></span>
          </span>
          <span class="sub-sep" aria-hidden="true"></span>
          <span class="toolkits-chips"></span>
        </div>
        <div class="card-rows">
          <div class="card-row">
            <span class="row-ico">${ICON.port}</span>
            <span class="row-label">Port</span>
            <span class="row-value mono port-val"></span>
          </div>
          <div class="card-row">
            <span class="row-ico">${ICON.access}</span>
            <span class="row-label">Access</span>
            <span class="row-value access-val"></span>
          </div>
          <div class="card-row">
            <span class="row-ico">${ICON.id}</span>
            <span class="row-label">ID</span>
            <span class="row-value id-val">
              <code class="addr-short"></code>
              <button class="row-copy btn-copy-addr" title="Copy ID" aria-label="Copy ID">${ICON.copy}</button>
            </span>
          </div>
          <div class="card-row">
            <span class="row-ico">${ICON.model}</span>
            <span class="row-label">Model</span>
            <span class="row-value mono model-val"></span>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn btn-outline icon-square btn-qr" title="Show QR" aria-label="Show QR code">${ICON.qr}</button>
          <button class="btn btn-outline btn-detail">Detail</button>
          <button class="btn btn-toggle"></button>
        </div>
      </div>
      <div class="card-back">
        <button class="card-back-close" title="Back" aria-label="Back to details">${ICON.back}</button>
        <img class="card-qr-img" alt="Agent address QR code" draggable="false">
        <div class="card-qr-name"></div>
        <div class="card-qr-addr mono"></div>
      </div>
    </div>`;
  $('.status-onion', card).appendChild(
    createOnion({ size: 22, mode: 'thinking', label: 'starting' }),
  );

  $('.btn-copy-addr', card).addEventListener('click', (e) => {
    e.stopPropagation();
    copyWithFeedback(e.currentTarget, card._agent.address);
  });
  $('.btn-qr', card).addEventListener('click', (e) => {
    e.stopPropagation();
    const img = $('.card-qr-img', card);
    if (!img.getAttribute('src')) img.src = api.qrUrl(card._agent.slug);   // lazy-load the QR
    $('.card-qr-name', card).textContent = card._agent.name;
    $('.card-qr-addr', card).textContent = shortAddr(card._agent.address);
    closeAllCardMenus();
    card.classList.add('flipped');                                          // flip to the QR back
  });
  $('.card-back-close', card).addEventListener('click', (e) => {
    e.stopPropagation();
    card.classList.remove('flipped');
  });
  $('.btn-detail', card).addEventListener('click', (e) => {
    e.stopPropagation();
    openDrawer(card._agent.slug);
  });
  $('.btn-toggle', card).addEventListener('click', (e) => {
    e.stopPropagation();
    const a = card._agent;
    doAction(a.slug, a.state === 'online' ? 'stop' : 'start');
  });

  // three-dots menu (Rename / Pin)
  const menuPop = $('.card-menu-pop', card);
  $('.card-menu-btn', card).addEventListener('click', (e) => {
    e.stopPropagation();
    const willOpen = menuPop.hidden;
    closeAllCardMenus();
    menuPop.hidden = !willOpen;
    card.classList.toggle('menu-open', willOpen);
  });
  menuPop.addEventListener('click', (e) => e.stopPropagation());
  $('.menu-item[data-act="rename"]', card).addEventListener('click', (e) => {
    e.stopPropagation();
    closeAllCardMenus();
    startRename(card);
  });
  $('.menu-item[data-act="pin"]', card).addEventListener('click', (e) => {
    e.stopPropagation();
    closeAllCardMenus();
    togglePin(card._agent.slug);
  });

  card.addEventListener('click', (e) => {
    if (card.classList.contains('flipped')) {              // showing the QR → any click flips back
      card.classList.remove('flipped');
      return;
    }
    if (e.target.closest('button')) return;
    if ($('.card-name', card).isContentEditable) return;   // don't open the drawer mid-rename
    openDrawer(card._agent.slug);
  });
  card.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('button')
        && !$('.card-name', card).isContentEditable) {
      e.preventDefault();
      openDrawer(card._agent.slug);
    }
  });

  if (chipFitObserver) chipFitObserver.observe($('.toolkits-chips', card));
  updateCard(card, agent);
  return card;
}

function updateCard(card, agent) {
  card._agent = agent;
  card.dataset.state = agent.state;
  const nameEl = $('.card-name', card);
  if (!nameEl.isContentEditable) nameEl.textContent = agent.name;   // don't clobber an in-progress rename
  nameEl.title = agent.name;
  $('.state-word', card).textContent = capitalize(agent.state);
  $('.port-val', card).textContent = agent.port;
  $('.access-val', card).textContent = capitalize(agent.trust || 'open');
  $('.addr-short', card).textContent = shortAddr(agent.address);
  const modelEl = $('.model-val', card);
  modelEl.textContent = agent.model;
  modelEl.title = agent.model;

  // Toolkits → violet chips. Only (re)build when they actually change, so the
  // periodic /ws/status refresh doesn't rebuild the DOM and flicker the card.
  const tkKey = (agent.toolkits || []).join('');
  if (card._tkKey !== tkKey) {
    card._tkKey = tkKey;
    fitChips(card);
  }

  // Start / Stop toggle — likewise, only rewrite when the visual state changes.
  const busy = state.busy.has(agent.slug);
  const toggleKey = `${agent.state}:${busy}`;
  if (card._toggleKey !== toggleKey) {
    card._toggleKey = toggleKey;
    const toggle = $('.btn-toggle', card);
    toggle.classList.remove('btn-primary', 'btn-danger-solid');
    if (agent.state === 'starting' || agent.state === 'creating') {
      toggle.innerHTML = '<span>Starting…</span>';
      toggle.disabled = true;
    } else if (agent.state === 'online') {
      toggle.innerHTML = `${ICON.stop}<span>Stop</span>`;
      toggle.classList.add('btn-danger-solid');
      toggle.disabled = busy;
    } else {
      toggle.innerHTML = `${ICON.play}<span>Start</span>`;
      toggle.classList.add('btn-primary');
      toggle.disabled = busy;
    }
  }
}

// Render toolkit chips into the sub-row. `more` appends a trailing "…" chip.
function renderChips(wrap, list, more, fullTitle) {
  wrap.textContent = '';
  for (const name of list) {
    const chip = document.createElement('span');
    chip.className = 'tk-chip';
    chip.textContent = name;
    wrap.appendChild(chip);
  }
  if (more) {
    const m = document.createElement('span');
    m.className = 'tk-chip tk-chip-more';
    m.textContent = '…';
    m.title = fullTitle;
    wrap.appendChild(m);
  }
}
// Priority: user-added toolkits first, the default "utility" last. Show up to 3;
// 4+ → three chips + a "…". If even that overflows the row, drop chips (keep "…").
function fitChips(card) {
  const wrap = $('.toolkits-chips', card);
  if (!wrap) return;
  const full = (card._agent && card._agent.toolkits) || [];
  const ordered = [...full.filter((t) => t !== 'utility'), ...full.filter((t) => t === 'utility')];
  const title = full.join(', ');
  let n = Math.min(3, ordered.length);
  renderChips(wrap, ordered.slice(0, n), ordered.length > n, title);
  if (!card.isConnected) return;                          // no layout yet — observer re-fits
  while (n > 0 && wrap.scrollWidth > wrap.clientWidth + 1) {
    n -= 1;
    renderChips(wrap, ordered.slice(0, n), true, title);
  }
}
const chipFitObserver = typeof ResizeObserver !== 'undefined'
  ? new ResizeObserver((entries) => {
      for (const e of entries) {
        const card = e.target.closest('.agent-card');
        if (card) fitChips(card);
      }
    })
  : null;
// belt-and-suspenders re-fit (reveal + window resize) — infrequent, so no flicker
function refitChips() {
  for (const [, card] of state.cards) fitChips(card);
}

// ---- pin (frontend-only, localStorage) + card menus + inline rename --
const PINNED_KEY = 'co-studio-pinned';
function getPinned() {
  try { return new Set(JSON.parse(localStorage.getItem(PINNED_KEY) || '[]')); }
  catch { return new Set(); }
}
function togglePin(slug) {
  const pinned = getPinned();
  pinned.has(slug) ? pinned.delete(slug) : pinned.add(slug);
  try { localStorage.setItem(PINNED_KEY, JSON.stringify([...pinned])); } catch { /* ignore */ }
  renderAgents();
}
function closeAllCardMenus() {
  document.querySelectorAll('.card-menu-pop:not([hidden])').forEach((p) => { p.hidden = true; });
  document.querySelectorAll('.agent-card.menu-open').forEach((c) => c.classList.remove('menu-open'));
}
async function commitRename(card, raw) {
  const agent = card._agent;
  const nameEl = $('.card-name', card);
  nameEl.contentEditable = 'false';
  nameEl.classList.remove('editing');
  const name = (raw || '').trim();
  if (!name || name === agent.name) { nameEl.textContent = agent.name; return; }
  try {
    const updated = await api.renameAgent(agent.slug, name);
    card._agent = { ...agent, ...updated };
    updateCard(card, card._agent);
    toast(`Renamed to “${name}”`);
  } catch (err) {
    nameEl.textContent = agent.name;
    toast(`Rename failed: ${err.message}`, 'danger');
  }
}
function startRename(card) {
  const nameEl = $('.card-name', card);
  if (nameEl.isContentEditable) return;
  nameEl.contentEditable = 'true';
  nameEl.classList.add('editing');
  nameEl.focus();
  const range = document.createRange();
  range.selectNodeContents(nameEl);
  const sel = window.getSelection();
  sel.removeAllRanges(); sel.addRange(range);

  let done = false;
  const finish = (commit) => {
    if (done) return;
    done = true;
    nameEl.removeEventListener('keydown', onKey);
    nameEl.removeEventListener('blur', onBlur);
    if (commit) {
      commitRename(card, nameEl.textContent);        // sets contentEditable='false', persists
    } else {
      nameEl.contentEditable = 'false';
      nameEl.classList.remove('editing');
      nameEl.textContent = card._agent.name;         // cancel → restore
    }
  };
  const onKey = (e) => {
    e.stopPropagation();
    if (e.key === 'Enter') { e.preventDefault(); finish(true); }
    else if (e.key === 'Escape') { e.preventDefault(); finish(false); }
  };
  const onBlur = () => finish(true);                 // click away = commit
  nameEl.addEventListener('keydown', onKey);
  nameEl.addEventListener('blur', onBlur);
}

let firstrunBuilt = false;
function renderAgents() {
  const grid = $('#agent-grid');

  // No agents → the first-run screen covers the shell; adding the first agent
  // reveals the shell, deleting the last one crossfades back here.
  if (!state.agents.length) {
    grid.textContent = '';
    state.cards.clear();
    if (!firstrunBuilt) {
      $('#firstrun-onion').appendChild(
        createOnion({ size: 148, mode: 'hero', label: 'ConnectOnion' }),
      );
      firstrunBuilt = true;
    }
    $('#app').classList.add('is-firstrun');
    return;
  }
  $('#app').classList.remove('is-firstrun');

  const pinned = getPinned();
  // pinned first; stable sort keeps created order within each group
  const ordered = [...state.agents].sort(
    (a, b) => (pinned.has(a.slug) ? 0 : 1) - (pinned.has(b.slug) ? 0 : 1),
  );

  const seen = new Set();
  for (const agent of ordered) {
    seen.add(agent.slug);
    let card = state.cards.get(agent.slug);
    if (!card) {
      card = agentCard(agent);
      state.cards.set(agent.slug, card);
    } else {
      updateCard(card, agent);
    }
    const isPinned = pinned.has(agent.slug);
    card.classList.toggle('is-pinned', isPinned);
    const pinLabel = $('.pin-label', card);
    if (pinLabel) pinLabel.textContent = isPinned ? 'Unpin' : 'Pin';
  }
  for (const [slug, card] of state.cards) {
    if (!seen.has(slug)) {
      if (chipFitObserver) chipFitObserver.unobserve($('.toolkits-chips', card));
      card.remove();
      state.cards.delete(slug);
    }
  }

  // Reconcile DOM order to the sorted list, but ONLY when it actually changed —
  // re-appending every card on each /ws/status tick is what made the grid jitter.
  const desired = ordered.map((a) => state.cards.get(a.slug)).filter(Boolean);
  const current = [...grid.children];
  const orderChanged = desired.length !== current.length
    || desired.some((c, i) => c !== current[i]);
  if (orderChanged) for (const card of desired) grid.appendChild(card);

  applySearch();
}

function applySearch() {
  const q = (state.search || '').toLowerCase();
  for (const [, card] of state.cards) {
    const a = card._agent || {};
    const match = !q
      || (a.name || '').toLowerCase().includes(q)
      || (a.address || '').toLowerCase().includes(q);
    card.hidden = !match;
  }
}

function initSearch() {
  const input = $('#agent-search');
  if (!input) return;
  input.addEventListener('input', (e) => {
    state.search = e.target.value.trim();
    applySearch();
  });
}

function updateFleetHeader() {
  const total = state.agents.length;
  const online = state.agents.filter((a) => a.state === 'online').length;
  const cnt = $('#nav-agents-count');
  if (cnt) {                                    // sidebar badge = ONLINE count, in green (hidden at 0)
    cnt.textContent = online || '';
    cnt.classList.add('nav-count-online');
  }
  const fleet = $('#fleet');
  if (fleet) fleet.textContent = total ? `${online} online · ${total} total` : '';
}

function renderSideHealth(setup) {
  const fwEl = $('#side-fw');
  const dot = $('#side-dot');
  if (!fwEl) return;
  const fw = (setup?.doctor || []).find((c) => c.check === 'import connectonion');
  if (setup?.framework_ok && fw?.ok) {
    fwEl.textContent = `connectonion ${String(fw.detail).replace('version ', '')}`;
    dot?.classList.remove('bad');
  } else {
    fwEl.textContent = 'framework needs setup';
    dot?.classList.add('bad');
  }
}

// ---- settings sheet (rises from the bottom of the current card) ----
function setSettingsNav(on) {
  const settingsNav = $('#open-settings');
  const agentsNav = $('.nav-item[data-view="agents"]');
  if (settingsNav) {
    settingsNav.classList.toggle('is-active', on);
    settingsNav.setAttribute('aria-current', on ? 'page' : 'false');
  }
  if (agentsNav) {
    agentsNav.classList.toggle('is-active', !on);
    agentsNav.setAttribute('aria-current', on ? 'false' : 'page');
  }
}
function openSettingsModal({ inset = false } = {}) {
  renderSettings(state.setup);
  const app = $('#app');
  app.classList.toggle('is-settings-inset', inset);   // main-interface: content-pane only
  app.classList.add('is-settings');
  if (inset) setSettingsNav(true);                     // reflect it in the sidebar
}
function closeSettingsModal() {
  const app = $('#app');
  const wasInset = app.classList.contains('is-settings-inset');
  app.classList.remove('is-settings');
  if (wasInset) setSettingsNav(false);                 // Agents becomes active again
  if (app.classList.contains('is-firstrun')) {   // bring "No agents yet" back to life
    const fr = $('#firstrun');
    fr.classList.remove('is-returning');
    void fr.offsetWidth;
    fr.classList.add('is-returning');
  }
}

function initNav() {
  const app = $('#app');
  app.appendChild($('#settings-view'));         // relocate the sheet inside the card
  $('#settings-view').hidden = false;           // CSS visibility/transform drives it now

  // sidebar → Settings: toggle the content-pane settings (sidebar stays put)
  const toggleInset = () => {
    if (app.classList.contains('is-settings')) closeSettingsModal();
    else openSettingsModal({ inset: true });
  };
  $('#open-settings').addEventListener('click', toggleInset);
  $('#open-settings').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleInset(); }
  });
  // sidebar → Agents: step back out of settings to the list
  const agentsNav = $('.nav-item[data-view="agents"]');
  if (agentsNav) agentsNav.addEventListener('click', () => {
    if (app.classList.contains('is-settings')) closeSettingsModal();
  });

  // first-run gear → full-card settings (keeps its own top-right close gear)
  $('#firstrun-settings').addEventListener('click', () => openSettingsModal({ inset: false }));
  $('#settings-close').addEventListener('click', closeSettingsModal);
}

function renderSettings(setup) {
  const fw = (setup?.doctor || []).find((c) => c.check === 'import connectonion');
  const fwEl = $('#set-fw');
  if (fwEl) fwEl.textContent = fw?.ok ? `connectonion ${String(fw.detail).replace('version ', '')}` : 'not found';
  const auth = $('#set-auth');
  if (auth) { auth.innerHTML = setup?.co_auth_ok ? 'authenticated <span class="ok-check">✓</span>' : 'run `co auth`'; auth.className = `v ${setup?.co_auth_ok ? 'ok' : 'bad'}`; }
  const key = $('#set-key');
  if (key) { key.innerHTML = setup?.key_ok ? 'present <span class="ok-check">✓</span>' : 'missing'; key.className = `v ${setup?.key_ok ? 'ok' : 'bad'}`; }
  const ver = $('#set-ver');
  if (ver) ver.textContent = setup?.studio_version ? `v${setup.studio_version}` : '—';
  const store = $('#set-storage');
  if (store) store.textContent = setup?.agents_dir || '—';
  resetStorageEdit();
}

// ---- storage location (change + migrate) ----------------------------
function resetStorageEdit() {
  $('#storage-view').hidden = false;
  $('#storage-edit').hidden = true;
  $('#storage-error').hidden = true;
  $('#storage-save').disabled = false;
  $('#storage-save').textContent = 'Move here';
}

function initStorage() {
  $('#storage-change').addEventListener('click', async () => {
    const btn = $('#storage-change');
    btn.disabled = true;
    try {
      const { path } = await api.pickFolder();   // native macOS folder chooser
      $('#storage-input').value = path;
      $('#storage-error').hidden = true;
      $('#storage-view').hidden = true;
      $('#storage-edit').hidden = false;
    } catch (e) {
      if (e.status !== 409) toast(e.message, 'danger');   // 409 = dialog cancelled → ignore
    } finally {
      btn.disabled = false;
    }
  });
  $('#storage-cancel').addEventListener('click', resetStorageEdit);
  $('#storage-save').addEventListener('click', async () => {
    const path = $('#storage-input').value.trim();
    const err = $('#storage-error');
    err.hidden = true;
    if (!path) { err.textContent = 'Enter a folder path.'; err.hidden = false; return; }
    const save = $('#storage-save');
    save.disabled = true; save.textContent = 'Moving…';
    try {
      const res = await api.setStorage(path);
      state.setup = { ...(state.setup || {}), agents_dir: res.agents_dir };
      $('#set-storage').textContent = res.agents_dir;
      resetStorageEdit();
      const n = res.moved;
      toast(n ? `Moved ${n} agent${n > 1 ? 's' : ''} — restart them to bring them back online.`
              : `Storage location updated.`);
      await refreshAgents();
    } catch (e) {
      err.textContent = e.message; err.hidden = false;
      save.disabled = false; save.textContent = 'Move here';
    }
  });
}

function setAgents(list) {
  const prev = new Map(state.agents.map((a) => [a.slug, a.state]));
  state.agents = list;
  renderAgents();
  updateFleetHeader();

  // keep an open drawer in sync; refetch detail when the state flips
  if (state.drawerSlug) {
    const summary = list.find((a) => a.slug === state.drawerSlug);
    if (summary) {
      if (prev.get(summary.slug) !== summary.state || !state.drawerDetail) {
        refreshDrawerDetail();
      }
    }
  }
}

async function refreshAgents() {
  try {
    setAgents(await api.listAgents());
    setConnBanner(false);
  } catch (err) {
    setConnBanner(true);
  }
}

// ---- actions --------------------------------------------------------
const ACTIONS = { start: api.startAgent, stop: api.stopAgent, restart: api.restartAgent };

async function doAction(slug, action) {
  if (state.busy.has(slug)) return;
  state.busy.add(slug);
  const card = state.cards.get(slug);
  if (card) updateCard(card, card._agent);
  syncDrawerButtons();
  try {
    await ACTIONS[action](slug);
  } catch (err) {
    toast(`${action} failed: ${err.message}`, 'danger');
  } finally {
    state.busy.delete(slug);
    await refreshAgents();
    syncDrawerButtons();
  }
}

// ---- connection / doctor banners ------------------------------------
function setConnBanner(broken) {
  $('#conn-banner').hidden = !broken;
}

function renderDoctorBanner(setup) {
  const banner = $('#doctor-banner');
  const failing = (setup?.doctor || []).filter((c) => !c.ok);
  if (!setup || !failing.length) {
    banner.hidden = true;
    return;
  }
  banner.innerHTML = '';
  banner.append('Doctor: ');
  failing.forEach((c, i) => {
    const b = document.createElement('b');
    b.textContent = c.check;
    banner.appendChild(b);
    if (i < failing.length - 1) banner.append(', ');
  });
  banner.append(' failed — the framework may have drifted. Details in an agent’s "Copy for Claude" bundle.');
  banner.hidden = false;
}

// ---- create wizard (Name → Model → Toolkits) ------------------------
const WIZARD_STEPS = 4;
let wizardStep = 0;

function stepHeight(n) {
  const step = $(`.wizard-step[data-step="${n}"]`);
  return step ? step.offsetHeight : 0;
}

const CREATE_VIEW_PAD = 64;   // #create-view top+bottom padding (32px each)
// the stage is `overflow: clip`; heights come out fractional (font metrics) and
// offsetHeight rounds down, so snapping the stage to the exact step height shaves
// the last input's bottom border. A few px of bleed keeps the clip edge below it.
const STAGE_BLEED = 4;

function paintWizard(animateHeight = true) {
  const stage = $('.wizard-stage');
  const app = $('#app');
  document.querySelectorAll('.wizard-step').forEach((s, i) => s.classList.toggle('is-active', i === wizardStep));

  const targetStage = stepHeight(wizardStep) + STAGE_BLEED;

  // size the whole card to wrap the wizard: measure the inner with the stage snapped
  // to its target, then restore so the stage's own transition animates from current
  let targetCardH = 0;
  if (app.classList.contains('is-creating')) {
    const inner = $('.wizard-inner');
    const savedTrans = stage.style.transition, savedH = stage.style.height;
    stage.style.transition = 'none';
    stage.style.height = `${targetStage}px`;
    targetCardH = inner.offsetHeight + CREATE_VIEW_PAD;
    stage.style.height = savedH;
    stage.offsetHeight;
    stage.style.transition = savedTrans;
  }

  if (!animateHeight) { stage.style.transition = 'none'; }
  stage.style.height = `${targetStage}px`;
  if (!animateHeight) { stage.offsetHeight; stage.style.transition = ''; }  // commit, then restore

  if (targetCardH) app.style.height = `${targetCardH}px`;   // card follows the content (CSS-animated)

  document.querySelectorAll('.wdot').forEach((d, i) => d.classList.toggle('is-active', i === wizardStep));
  $('#wizard-back').textContent = wizardStep === 0 ? 'Cancel' : 'Back';
  const last = wizardStep === WIZARD_STEPS - 1;
  $('#wizard-next').hidden = last;
  $('#create-submit').hidden = !last;
}

function goWizard(n) {
  wizardStep = Math.max(0, Math.min(WIZARD_STEPS - 1, n));
  paintWizard(true);
  const focusable = $(`.wizard-step[data-step="${wizardStep}"]`)?.querySelector('input, select');
  if (focusable) setTimeout(() => focusable.focus(), 80);
}

// mirrors the backend slug rule (creator.slugify): lowercase, non-alphanumeric → '-'
const slugify = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

function nameStatus(raw) {
  const name = (raw || '').trim();
  if (!name) return { kind: 'empty' };
  const slug = slugify(name);
  if (!slug) return { kind: 'bad', msg: 'Use letters or numbers in the name.' };
  if (state.agents.some((a) => a.slug === slug)) return { kind: 'bad', msg: 'An agent with that name already exists.' };
  return { kind: 'ok' };
}

function updateNameStatus() {
  const el = $('#f-name-status');
  const wrap = el?.closest('.input-wrap');
  if (!el || !wrap) return;
  const s = nameStatus($('#f-name').value);
  if (s.kind === 'ok') {
    el.textContent = '✓'; el.className = 'input-status ok'; el.hidden = false; el.removeAttribute('title'); wrap.classList.add('has-status');
  } else if (s.kind === 'bad') {
    el.textContent = '✕'; el.className = 'input-status bad'; el.hidden = false; el.title = s.msg; wrap.classList.add('has-status');
  } else {
    el.hidden = true; wrap.classList.remove('has-status');
  }
}

function validateStep(n) {
  const errEl = $('#create-error');
  errEl.hidden = true;
  if (n === 0) {
    const s = nameStatus($('#f-name').value);
    if (s.kind !== 'ok') {
      errEl.textContent = s.kind === 'empty' ? 'Give the agent a name.' : s.msg;
      errEl.hidden = false; return false;
    }
  }
  if (n === 1) {
    let model = $('#f-model').value;
    if (model === '__custom') model = $('#f-model-custom').value.trim();
    if (!model) { errEl.textContent = 'Pick or type a model.'; errEl.hidden = false; return false; }
  }
  return true;
}

let wizardStacked = false;
function openCreateModal(stacked = false) {
  // From Settings → first crossfade back to the agents view, THEN open the wizard,
  // so it's a smooth Settings → Agents → New Agent sequence (never an overlap).
  if ($('#app').classList.contains('is-settings')) {
    closeSettingsModal();
    setTimeout(() => openCreateModal(stacked), 300);
    return;
  }
  $('#create-form').reset();
  $('#f-model-custom-wrap').hidden = true;
  $('#create-error').hidden = true;
  $('#create-submit').disabled = false;
  if (createBtnHTML) $('#create-submit').innerHTML = createBtnHTML;
  wizardStep = 0;
  wizardStacked = stacked;
  $('#create-view').classList.toggle('stacked', stacked);
  updateNameStatus();                        // clear the ✓/✕ from any prior run
  wizardFullH = $('#app').offsetHeight;      // remember the full card height to grow back to
  $('#app').classList.add('is-creating');   // slide the wizard in over the card
  if (stacked) {                             // main-interface entry: all four steps in one scrollable form
    $('#app').style.height = '';             // full card (no per-step sizing); the form scrolls inside
    $('#wizard-back').textContent = 'Cancel';
    $('#wizard-next').hidden = true;
    $('#create-submit').hidden = false;
  } else {
    paintWizard(false);                      // first-run entry: the compact step-by-step wizard
  }
  $('#f-name').focus();
}

let wizardFullH = 0;
function closeCreateModal() {
  const app = $('#app');
  app.classList.remove('is-creating');
  $('#create-view').classList.remove('stacked');
  if (wizardFullH) {                          // animate the card back to full size, then release it
    app.style.height = `${wizardFullH}px`;
    setTimeout(() => { app.style.height = ''; }, 500);
  }
  if ($('#app').classList.contains('is-firstrun')) {   // returning to first-run → replay its entrance
    const fr = $('#firstrun');
    fr.classList.remove('is-returning');
    void fr.offsetWidth;                                // restart the animation
    fr.classList.add('is-returning');
  }
}

let createBtnHTML = '';   // the CTA's default markup (sparkle icon + "Create Now")
function initCreateModal() {
  $('#app').appendChild($('#create-view'));  // relocate the wizard inside the card
  $('#create-view').hidden = false;          // CSS opacity/visibility drives it from here
  createBtnHTML = $('#create-submit').innerHTML;
  $('#btn-new-agent').addEventListener('click', () => openCreateModal(true));        // main interface → stacked form
  $('#btn-new-agent-first').addEventListener('click', () => openCreateModal(false)); // first-run → step-by-step
  $('#wizard-back').addEventListener('click', () => {
    if (wizardStacked || wizardStep === 0) closeCreateModal();
    else goWizard(wizardStep - 1);
  });
  $('#wizard-next').addEventListener('click', () => {
    if (validateStep(wizardStep)) goWizard(wizardStep + 1);
  });
  $('#f-model').addEventListener('change', (e) => {
    const custom = e.target.value === '__custom';
    $('#f-model-custom-wrap').hidden = !custom;
    if (!wizardStacked) paintWizard(true);   // wizard: re-fit the step height (stacked just flows)
    if (custom) $('#f-model-custom').focus();
  });
  // live name check: clear the error and re-flag ✓/✕ as they type
  $('#f-name').addEventListener('input', () => {
    $('#create-error').hidden = true;
    updateNameStatus();
  });
  // Enter in a text field advances the wizard (stacked form: don't submit early)
  const advanceOnEnter = (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (wizardStacked) return;
    if (validateStep(wizardStep)) goWizard(wizardStep + 1);
  };
  $('#f-name').addEventListener('keydown', advanceOnEnter);
  $('#f-model-custom').addEventListener('keydown', advanceOnEnter);

  $('#create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    // step-by-step wizard: Enter on an intermediate control (e.g. the Model
    // <select>, an Access radio) fires an implicit submit — treat it as "Next"
    // until the final step, so it never creates the agent early.
    if (!wizardStacked && wizardStep < WIZARD_STEPS - 1) {
      if (validateStep(wizardStep)) goWizard(wizardStep + 1);
      return;
    }
    const errEl = $('#create-error');
    errEl.hidden = true;

    const name = $('#f-name').value.trim();
    let model = $('#f-model').value;
    if (model === '__custom') model = $('#f-model-custom').value.trim();
    const optional = [...document.querySelectorAll('#create-form input[name="toolkit"]:checked')].map((cb) => cb.value);
    const toolkits = ['utility', ...optional];   // Utility is always included
    const trust = document.querySelector('#create-form input[name="trust"]:checked')?.value || 'open';

    if (!name) { errEl.textContent = 'Give the agent a name.'; errEl.hidden = false; if (!wizardStacked) goWizard(0); return; }
    if (!model) { errEl.textContent = 'Pick or type a model.'; errEl.hidden = false; if (!wizardStacked) goWizard(1); return; }

    const submit = $('#create-submit');
    submit.disabled = true;
    submit.textContent = 'Creating…';
    try {
      const detail = await api.createAgent({ name, model, toolkits, trust });
      closeCreateModal();
      await refreshAgents();
      toast(`${detail.name} created — QR ready. Press Start to bring it online.`);
    } catch (err) {
      errEl.textContent = err.message;
      errEl.hidden = false;
      submit.disabled = false;
      submit.innerHTML = createBtnHTML;
    }
  });
}

// ---- QR modal -------------------------------------------------------
function openQrModal(agent) {
  $('#qr-img').src = api.qrUrl(agent.slug);
  $('#qr-name').textContent = agent.name;
  $('#qr-addr').textContent = agent.address;
  $('#modal-qr').hidden = false;
}

function initQrModal() {
  $('#qr-close').addEventListener('click', () => { $('#modal-qr').hidden = true; });
  $('#modal-qr').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.hidden = true;
  });
}

// ---- detail drawer --------------------------------------------------
function infoRow(label, valueNode) {
  const row = document.createElement('div');
  row.className = 'info-row';
  const k = document.createElement('span');
  k.className = 'k';
  k.textContent = label;
  const v = document.createElement('span');
  v.className = 'v';
  if (typeof valueNode === 'string') v.textContent = valueNode;
  else v.appendChild(valueNode);
  row.append(k, v);
  return row;
}

function copyableValue(text) {
  const wrap = document.createElement('span');
  wrap.style.display = 'inline-flex';
  wrap.style.alignItems = 'center';
  wrap.style.gap = '4px';
  wrap.style.minWidth = '0';
  const code = document.createElement('code');
  code.textContent = text;
  const btn = document.createElement('button');
  btn.className = 'icon-btn';
  btn.title = 'Copy';
  btn.setAttribute('aria-label', 'Copy');
  btn.innerHTML = '⧉';
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    copyWithFeedback(btn, text);
  });
  wrap.append(code, btn);
  return wrap;
}

function renderDrawerFields(detail) {
  $('#d-name').textContent = detail.name;
  const badge = $('#d-state');
  badge.textContent = detail.state;
  badge.dataset.state = detail.state;

  $('#d-qr').src = api.qrUrl(detail.slug);
  $('#d-addr').textContent = detail.address;

  const info = $('#d-info');
  info.textContent = '';
  info.appendChild(infoRow('Model', detail.model));
  info.appendChild(infoRow('Port', String(detail.port)));
  info.appendChild(infoRow('Toolkits', (detail.toolkits || []).join(', ') || '—'));
  info.appendChild(infoRow(
    'Relay',
    detail.relay_ok === true ? 'connected' : detail.relay_ok === false ? 'not connected' : '—',
  ));
  info.appendChild(infoRow(
    'Endpoints',
    detail.endpoints_announced == null ? '—' : `${detail.endpoints_announced} announced`,
  ));
  if (detail.script_path) info.appendChild(infoRow('Script', copyableValue(detail.script_path)));
  if (detail.co_dir) info.appendChild(infoRow('co_dir', copyableValue(detail.co_dir)));
  info.appendChild(infoRow('Created', detail.created_at || '—'));

  const errBox = $('#d-last-error');
  if (detail.last_error) {
    errBox.textContent = detail.last_error;
    errBox.hidden = false;
  } else {
    errBox.hidden = true;
  }

  syncDrawerButtons();
}

function syncDrawerButtons() {
  const detail = state.drawerDetail;
  if (!detail || $('#drawer').hidden) return;
  const summary = state.agents.find((a) => a.slug === detail.slug);
  const stateNow = summary ? summary.state : detail.state;
  const busy = state.busy.has(detail.slug);

  const toggle = $('#d-toggle');
  toggle.classList.remove('btn-primary', 'btn-danger-solid');   // Start=violet, Stop=red, both solid
  if (stateNow === 'starting' || stateNow === 'creating') {
    toggle.textContent = 'Starting…';
    toggle.disabled = true;
  } else if (stateNow === 'online') {
    toggle.textContent = 'Stop';
    toggle.classList.add('btn-danger-solid');
    toggle.disabled = busy;
  } else {
    toggle.textContent = 'Start';
    toggle.classList.add('btn-primary');
    toggle.disabled = busy;
  }
  $('#d-restart').disabled = busy || stateNow === 'creating';

  const badge = $('#d-state');
  badge.textContent = stateNow;
  badge.dataset.state = stateNow;
}

// -- live logs --
const ERROR_LINE_RE = /\b(error|traceback|exception|failed|failure|fatal|critical|panic|unhandled)\b|\bERR\b|\[error\]|429/i;
let inTraceback = false;

function appendLogLine({ source, line }) {
  const pane = $('#d-log-pane');
  const placeholder = pane.querySelector('.log-empty');
  if (placeholder) placeholder.remove();

  if (/^Traceback \(most recent call last\)/.test(line)) inTraceback = true;
  else if (inTraceback && line && !/^\s/.test(line) && !ERROR_LINE_RE.test(line)) {
    // final "SomethingError: …" line of a traceback keeps the flag for one line
    inTraceback = /^[A-Za-z_.]+(Error|Exception|Warning)\b/.test(line);
  }
  const isError = ERROR_LINE_RE.test(line) || inTraceback;

  const el = document.createElement('div');
  el.className = 'log-line'
    + (isError ? ' log-error' : '')
    + (source === 'logger' ? ' log-logger' : '');
  el.textContent = line;

  const stick = pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 12;
  pane.appendChild(el);
  while (pane.childElementCount > 1000) pane.firstElementChild.remove();
  if (stick) pane.scrollTop = pane.scrollHeight;
}

function resetLogPane(message = 'waiting for log lines…') {
  const pane = $('#d-log-pane');
  pane.textContent = '';
  inTraceback = false;
  const empty = document.createElement('div');
  empty.className = 'log-empty';
  empty.textContent = message;
  pane.appendChild(empty);
}

async function refreshDrawerDetail() {
  if (!state.drawerSlug) return;
  try {
    const detail = await api.getAgent(state.drawerSlug);
    if (detail.slug !== state.drawerSlug) return; // drawer moved on
    state.drawerDetail = detail;
    renderDrawerFields(detail);
  } catch { /* summary keeps the badge fresh; detail refresh is best-effort */ }
}

async function openDrawer(slug, prefetched = null) {
  closeDrawerSocket();
  state.drawerSlug = slug;
  state.drawerDetail = null;

  const drawer = $('#drawer');
  const backdrop = $('#drawer-backdrop');
  drawer.hidden = false;
  backdrop.hidden = false;
  requestAnimationFrame(() => {
    drawer.classList.add('open');
    backdrop.classList.add('open');
  });

  $('#d-name').textContent = '…';
  resetLogPane('connecting…');

  const detail = prefetched || await api.getAgent(slug).catch((err) => {
    toast(`Load failed: ${err.message}`, 'danger');
    return null;
  });
  if (!detail || state.drawerSlug !== slug) return;
  state.drawerDetail = detail;
  renderDrawerFields(detail);

  resetLogPane();
  const conn = $('#d-log-conn');
  state.logSock = logSocket(
    slug,
    appendLogLine,
    (live) => {
      conn.textContent = live ? 'live' : 'reconnecting…';
      conn.classList.toggle('live', live);
    },
  );
}

function closeDrawerSocket() {
  if (state.logSock) {
    state.logSock.close();
    state.logSock = null;
  }
}

function closeDrawer() {
  closeDrawerSocket();
  state.drawerSlug = null;
  state.drawerDetail = null;
  const drawer = $('#drawer');
  const backdrop = $('#drawer-backdrop');
  drawer.classList.remove('open');
  backdrop.classList.remove('open');
  setTimeout(() => {
    drawer.hidden = true;
    backdrop.hidden = true;
  }, 300);
  resetDeleteButton();
}

function resetDeleteButton() {
  const btn = $('#d-delete');
  btn.textContent = 'Delete';
  btn.classList.remove('btn-danger-solid');
  btn.classList.add('btn-danger-ghost');
  clearTimeout(btn._confirmTimer);
  delete btn.dataset.confirming;
}

function initDrawer() {
  $('#d-close').addEventListener('click', closeDrawer);
  $('#drawer-backdrop').addEventListener('click', closeDrawer);

  $('#d-copy-addr').addEventListener('click', (e) => {
    if (state.drawerDetail) copyWithFeedback(e.currentTarget, state.drawerDetail.address);
  });

  $('#d-copy-claude').addEventListener('click', (e) => {
    if (state.drawerSlug) copyForClaude(state.drawerSlug, e.currentTarget);
  });

  $('#d-toggle').addEventListener('click', () => {
    if (!state.drawerDetail) return;
    const summary = state.agents.find((a) => a.slug === state.drawerSlug);
    const stateNow = summary ? summary.state : state.drawerDetail.state;
    doAction(state.drawerSlug, stateNow === 'online' ? 'stop' : 'start');
  });
  $('#d-restart').addEventListener('click', () => {
    if (state.drawerSlug) doAction(state.drawerSlug, 'restart');
  });

  // two-step delete: moves to ~/.co-studio/trash, never a hard delete
  $('#d-delete').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    if (!state.drawerSlug) return;
    if (!btn.dataset.confirming) {
      btn.dataset.confirming = '1';
      btn.textContent = 'Delete permanently?';
      btn.classList.remove('btn-danger-ghost');
      btn.classList.add('btn-danger-solid');
      btn._confirmTimer = setTimeout(resetDeleteButton, 4000);
      return;
    }
    clearTimeout(btn._confirmTimer);
    const slug = state.drawerSlug;
    const name = state.drawerDetail?.name || slug;
    btn.disabled = true;
    try {
      await api.deleteAgent(slug);
      closeDrawer();
      await refreshAgents();
      toast(`${name} deleted`);
    } catch (err) {
      toast(`Delete failed: ${err.message}`, 'danger');
      resetDeleteButton();
    } finally {
      btn.disabled = false;
    }
  });
}

// ---- onboarding -----------------------------------------------------
function renderDoctorList(setup) {
  const list = $('#onboarding-doctor');
  list.textContent = '';
  const rows = [
    { check: 'co auth (managed key)', ok: !!setup?.co_auth_ok },
    { check: 'model key in ~/.co/keys.env', ok: !!setup?.key_ok },
    { check: 'connectonion framework', ok: !!setup?.framework_ok },
    ...(setup?.doctor || []).map((c) => ({ check: c.check, ok: c.ok, detail: c.detail })),
  ];
  for (const row of rows) {
    const li = document.createElement('li');
    li.className = row.ok ? 'ok' : 'fail';
    const mark = document.createElement('span');
    mark.className = 'mark';
    mark.textContent = row.ok ? '✓' : '✗';
    const label = document.createElement('span');
    label.textContent = row.check;
    li.append(mark, label);
    if (row.detail && !row.ok) {
      const detail = document.createElement('span');
      detail.className = 'detail';
      detail.textContent = ` — ${row.detail}`;
      li.appendChild(detail);
    }
    list.appendChild(li);
  }
}

function stopOnboardingPoll() {
  clearInterval(state.onboardingTimer);
  state.onboardingTimer = null;
}

function showOnboarding(setup) {
  state.onboardingActive = true;
  $('#app').hidden = true;
  const section = $('#onboarding');
  if (!section.dataset.built) {
    $('#onboarding-onion').appendChild(
      createOnion({ size: 120, mode: 'hero', label: 'ConnectOnion' }),
    );
    $('#onboarding-wait-onion').appendChild(
      createOnion({ size: 26, mode: 'thinking', label: 'waiting' }),
    );
    $('#onboarding-copy').addEventListener('click', (e) => {
      copyWithFeedback(e.currentTarget, 'co auth');
    });
    section.dataset.built = '1';
  }
  renderDoctorList(setup);
  section.hidden = false;

  stopOnboardingPoll();
  state.onboardingTimer = setInterval(async () => {
    let s;
    try {
      s = await api.setupStatus();
    } catch {
      return; // backend blip — keep polling
    }
    state.setup = s;
    renderDoctorList(s);
    if (s.co_auth_ok) {
      stopOnboardingPoll();
      state.onboardingActive = false;
      section.hidden = true;
      renderDoctorBanner(s);
      await playSplash($('#splash'));   // success → replay the splash
      refreshAgents();
      revealApp();                      // then crossfade splash → shell
    }
  }, 2000);
}

// ---- viewport gate (too small → onion + resize prompt) --------------
const MIN_W = 1160;   // the card is a fixed 1120×760 now; gate the app until the window can hold it
const MIN_H = 800;
const GATE_PHRASES = [
  'ConnectOnion Studio needs a little more room.',
  'Resize your window larger to continue.',
];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let gateBuilt = false;
let gateTyping = false;
let gateToken = 0;

async function runGateTyper() {
  const token = ++gateToken;
  const el = $('#gate-type');
  if (!el) return;
  let i = 0;
  while (token === gateToken) {
    const phrase = GATE_PHRASES[i % GATE_PHRASES.length];
    for (let c = 1; c <= phrase.length; c++) {          // type in
      if (token !== gateToken) return;
      el.textContent = phrase.slice(0, c);
      await wait(46);
    }
    await wait(1500);                                    // hold
    for (let c = phrase.length - 1; c >= 0; c--) {       // backspace out (fast)
      if (token !== gateToken) return;
      el.textContent = phrase.slice(0, c);
      await wait(20);
    }
    await wait(360);
    i++;
  }
}
function stopGateTyper() {
  gateToken++;   // leave the last frame in place so it fades out with the gate
}

function checkViewport() {
  const small = window.innerWidth < MIN_W || window.innerHeight < MIN_H;
  if (small && !gateBuilt) {
    $('#gate-onion').appendChild(createOnion({ size: 104, mode: 'assemble', label: 'ConnectOnion' }));
    gateBuilt = true;
  }
  $('#viewport-gate').classList.toggle('is-shown', small);
  document.body.classList.toggle('gated', small);
  if (small && !gateTyping) { gateTyping = true; runGateTyper(); }
  else if (!small && gateTyping) { gateTyping = false; stopGateTyper(); }
}

// Crossfade the main shell in as the welcome splash dissolves out — the same
// fade + slight rise the shell uses when the window grows past the gate.
function revealApp() {
  const app = $('#app');
  const splash = $('#splash');
  app.classList.add('is-entering');   // start faded + slightly shrunk
  app.hidden = false;
  void app.offsetWidth;               // commit the start state before transitioning
  app.classList.remove('is-entering');
  document.body.classList.add('glow-in');  // let the violet glow bloom in slowly
  splash.classList.add('is-leaving'); // dissolve the splash out over the top
  const finish = () => { splash.hidden = true; splash.classList.remove('is-leaving'); };
  splash.addEventListener('transitionend', finish, { once: true });
  setTimeout(finish, 700);            // fallback if transitionend never fires
  // enable the first-run ⇄ shell crossfade only after this first reveal settles,
  // so create/delete animate but the initial load doesn't
  setTimeout(() => document.body.classList.add('shell-ready'), 550);
  setTimeout(refitChips, 80);         // cards now have layout → truncate overflowing chips
}

// ---- boot -----------------------------------------------------------
async function boot() {
  checkViewport();
  // enable the shell/gate crossfade only after the initial state is committed,
  // so first load snaps to the right view instead of animating into it. (setTimeout
  // rather than rAF: rAF is fully paused in a background tab, timers still fire.)
  setTimeout(() => document.body.classList.add('anim-ready'), 60);
  window.addEventListener('resize', checkViewport);
  window.addEventListener('resize', refitChips);   // re-fit toolkit chips when columns reflow
  initTheme();
  initNav();
  initStorage();
  initSearch();
  initCreateModal();
  initQrModal();
  initDrawer();

  $('#app').appendChild($('#toasts'));   // toasts live inside the card, centered at its bottom
  $('#brand-onion').appendChild(createOnion({ size: 42, label: 'ConnectOnion' }));

  document.addEventListener('click', closeAllCardMenus);   // outside-click closes any open card menu
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    closeAllCardMenus();
    if ($('#app').classList.contains('is-settings')) closeSettingsModal();
    else if (!$('#modal-qr').hidden) $('#modal-qr').hidden = true;
    else if ($('#app').classList.contains('is-creating')) closeCreateModal();
    else if (!$('#drawer').hidden) closeDrawer();
  });

  const splashDone = playSplash($('#splash'));
  const setupPromise = api.setupStatus().catch(() => null);
  const agentsPromise = api.listAgents().catch(() => null);

  const [setup, agents] = await Promise.all([setupPromise, agentsPromise]);
  await splashDone;

  state.setup = setup;
  renderSideHealth(setup);
  if (setup && !setup.co_auth_ok) {
    $('#splash').hidden = true;   // splash → onboarding card (its own path)
    showOnboarding(setup);
  } else {
    // populate the shell before it fades in, then crossfade splash → shell
    renderDoctorBanner(setup);
    if (agents) {
      setAgents(agents);
    } else {
      setConnBanner(true);
      renderAgents(); // empty grid → hero empty state
    }
    revealApp();
  }

  state.statusSock = statusSocket(
    (list) => {
      if (!state.onboardingActive) setAgents(list);
    },
    async (connected) => {
      if (!connected) {
        setConnBanner(true);
        return;
      }
      setConnBanner(false);
      // on (re)connect, re-verify setup + agents once
      try {
        const s = await api.setupStatus();
        state.setup = s;
        if (!s.co_auth_ok && !state.onboardingActive) {
          showOnboarding(s);
        } else if (!state.onboardingActive) {
          renderDoctorBanner(s);
          refreshAgents();
        }
      } catch { /* banner already handles it */ }
    },
  );
}

boot();
