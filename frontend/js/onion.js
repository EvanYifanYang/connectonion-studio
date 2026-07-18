// ============================================================
// onion.js — the 8-layer onion brand component + splash player
// Layer 1 = outer black peel (bottom), layer 8 = core (top).
// Animation classes live in css/onion.css:
//   assemble | hero | thinking   (put on the .onion element)
//   splash                       (put on a CONTAINER holding
//                                 an .onion and a .wordmark)
// ============================================================

const LAYERS = [
  'onion_1_black',
  'onion_2_purple',
  'onion_3_white',
  'onion_4_purple',
  'onion_5_white',
  'onion_6_purple',
  'onion_7_white',
  'onion_8_core',
];

export const WORDMARK_TEXT = 'ConnectOnion'; // 12 letters, waved in left→right

const layerSrc = (name) => `/assets/onion/${name}.png`;

export function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Build an onion element.
 * @param {{size?:number, mode?:''|'assemble'|'hero'|'thinking', label?:string}} opts
 */
export function createOnion({ size = 96, mode = '', label = '' } = {}) {
  const el = document.createElement('div');
  el.className = mode ? `onion ${mode}` : 'onion';
  el.style.setProperty('--onion-size', `${size}px`);
  el.setAttribute('role', 'img');
  el.setAttribute('aria-label', label || 'ConnectOnion mark');
  LAYERS.forEach((name, i) => {
    const img = document.createElement('img');
    img.src = layerSrc(name);
    img.alt = '';
    img.className = `l${i + 1}`;
    img.style.setProperty('--i', i);
    img.decoding = 'async';
    img.draggable = false;
    el.appendChild(img);
  });
  return el;
}

/** Swap animation mode ('' clears). Restarts the animation cleanly. */
export function setOnionMode(onion, mode) {
  onion.classList.remove('assemble', 'hero', 'thinking');
  if (mode) {
    void onion.offsetWidth; // reflow → restart animations
    onion.classList.add(mode);
  }
}

/** Fill `el` with one <span> per letter, --li set for the wave delay.
 *  Everything after the first space is marked `.wm-sub` (the "Studio" suffix). */
export function buildWordmark(el, text = WORDMARK_TEXT) {
  el.textContent = '';
  let sub = false;
  [...text].forEach((ch, i) => {
    if (ch === ' ') sub = true;
    const span = document.createElement('span');
    span.textContent = ch === ' ' ? ' ' : ch;
    if (sub) span.classList.add('wm-sub');
    span.style.setProperty('--li', i);
    el.appendChild(span);
  });
}

/** Decode all 8 layers up-front so the splash never pops in half-loaded. */
export function preloadOnion(timeoutMs = 900) {
  const all = Promise.allSettled(
    LAYERS.map((name) => {
      const img = new Image();
      img.src = layerSrc(name);
      return img.decode();
    }),
  );
  const timeout = new Promise((resolve) => setTimeout(resolve, timeoutMs));
  return Promise.race([all, timeout]);
}

/**
 * Play the full splash inside `overlayEl` (the fixed full-screen div).
 * Rebuilds the stage each call, so it can be replayed (e.g. after `co auth`).
 * Resolves when the disassemble finishes; overlay hiding is the caller's job.
 */
export async function playSplash(overlayEl) {
  const stage = overlayEl.querySelector('.splash-stage') || overlayEl;
  stage.classList.remove('splash');
  stage.textContent = '';

  const onion = createOnion({ size: 132, label: 'ConnectOnion Studio' });
  const wordmark = document.createElement('div');
  wordmark.className = 'wordmark wordmark-hero';
  buildWordmark(wordmark, 'ConnectOnion Studio');
  stage.append(onion, wordmark);

  overlayEl.hidden = false;
  await preloadOnion();   // the splash wordmark uses a non-lazy font (css), so no font wait needed

  void stage.offsetWidth; // reflow before starting the choreography
  stage.classList.add('splash');

  // assemble ~1.23s → hold ~0.55s → disassemble ends ~2.62s (see onion.css)
  const total = reducedMotion() ? 1900 : 2750;
  await new Promise((resolve) => setTimeout(resolve, total));
  // NB: leave the `.splash` class on — the disassemble ends at opacity 0 with
  // `forwards`, so the onion stays hidden. Removing it here would snap the onion
  // back to its fully-assembled base state and flash it before the overlay fades.
}
