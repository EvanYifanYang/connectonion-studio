// ============================================================
// diagnostics.js — the "Copy for Claude" one-click capture.
// Fetches /api/agents/{slug}/diagnostics (markdown bundle) and
// puts it on the clipboard, with button-state feedback.
// ============================================================

import { fetchDiagnostics } from './api.js';

/** Clipboard write with a legacy fallback. Returns true on success. */
export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch { /* fall through to legacy path */ }
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  } catch {
    return false;
  }
}

function flash(btn, message, revertMs = 2200) {
  if (btn.dataset.originalHtml === undefined) {
    btn.dataset.originalHtml = btn.innerHTML;
  }
  btn.textContent = message;
  clearTimeout(btn._flashTimer);
  btn._flashTimer = setTimeout(() => {
    btn.innerHTML = btn.dataset.originalHtml;
    delete btn.dataset.originalHtml;
    btn.disabled = false;
  }, revertMs);
}

/**
 * Fetch the markdown diagnostics bundle for `slug` and copy it to the
 * clipboard. `btn` gets progress / success / failure feedback.
 * Returns true if the bundle landed on the clipboard.
 */
export async function copyForClaude(slug, btn) {
  if (btn.disabled) return false;
  if (btn.dataset.originalHtml === undefined) {
    btn.dataset.originalHtml = btn.innerHTML;
  }
  btn.disabled = true;
  btn.textContent = 'Capturing…';
  let bundle;
  try {
    bundle = await fetchDiagnostics(slug);
  } catch (err) {
    flash(btn, 'Capture failed — is the backend up?');
    return false;
  }
  const ok = await copyText(bundle);
  flash(btn, ok ? 'Copied — paste into Claude' : 'Clipboard blocked — copy manually');
  return ok;
}

/** Small helper for the many "copy this value" icon buttons. */
export async function copyWithFeedback(btn, text, glyphDone = '✓', glyphFail = '✕') {
  const ok = await copyText(text);
  const original = btn.dataset.glyph ?? btn.innerHTML;
  btn.dataset.glyph = original;
  btn.classList.add('copied');
  btn.innerHTML = ok ? glyphDone : glyphFail;
  clearTimeout(btn._copyTimer);
  btn._copyTimer = setTimeout(() => {
    btn.innerHTML = btn.dataset.glyph;
    btn.classList.remove('copied');
  }, 1400);
  return ok;
}
