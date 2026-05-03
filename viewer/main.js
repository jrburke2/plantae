// plant_sim viewer entry point.
//
// URL params:
//   ?species=<species_id>     (default: echinacea_purpurea)
//   &seed=<int>               (default: 42)
//
// On slider change, fetches:
//   /render/scene.obj?species=...&seed=...&t=<doy>
//   /render/scene.materials.json?species=...&seed=...&t=<doy>
// and applies materials from /materials/library.json via material_loader.js.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';

import {
  loadLibrary,
  applyMaterialsToObject,
} from './material_loader.js';

// === URL params ===

const params = new URLSearchParams(window.location.search);
const SPECIES = params.get('species') || 'echinacea_purpurea';
// Seed is a string. Server accepts canonical, display, or integer forms.
let SEED = params.get('seed') || '42';
document.getElementById('title').textContent = `plant_sim viewer — ${SPECIES}`;

// === Three.js scene ===

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a1a);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.01, 100);
// Camera positioned for typical Echinacea (~1.2m mature). Step 8 will tune for Andropogon (~2m).
camera.position.set(1.5, 1.4, 2.5);
camera.lookAt(0, 0.7, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.7, 0);
controls.update();

// Lighting
scene.add(new THREE.AmbientLight(0x606060, 1.4));
const dir = new THREE.DirectionalLight(0xffffff, 1.6);
dir.position.set(1.5, 3.0, 1.0);
scene.add(dir);

// Ground plane (in meters; canonical internal unit)
const ground = new THREE.Mesh(
  new THREE.CircleGeometry(1.5, 48),
  new THREE.MeshStandardMaterial({ color: 0x3a2e25, roughness: 0.9 })
);
ground.rotation.x = -Math.PI / 2;
scene.add(ground);

// === Loading + slider state ===

const objLoader = new OBJLoader();
let library = null;
let currentMesh = null;
let currentT = parseInt(document.getElementById('slider').value, 10);
let inFlight = false;
let pendingT = null;

const sliderEl = document.getElementById('slider');
const tDisplayEl = document.getElementById('t-display');
const statusEl = document.getElementById('status');

function setStatus(msg) {
  statusEl.textContent = msg;
}

// Cache loaded OBJ Object3Ds per t. Materials are reapplied each frame for
// color-curve evaluation (cheap; a fresh THREE.MeshStandardMaterial per mesh).
const meshCache = new Map();

async function loadFrame(t) {
  setStatus(`loading t=${t}...`);
  const objUrl = `/render/scene.obj?species=${SPECIES}&seed=${encodeURIComponent(SEED)}&t=${t}`;
  const sidecarUrl = `/render/scene.materials.json?species=${SPECIES}&seed=${encodeURIComponent(SEED)}&t=${t}`;

  // Fetch sidecar in parallel with OBJ.
  const sidecarPromise = fetch(sidecarUrl).then(r => {
    if (!r.ok) throw new Error(`sidecar ${r.status}`);
    return r.json();
  });

  let obj;
  if (meshCache.has(t)) {
    obj = meshCache.get(t);
  } else {
    obj = await new Promise((resolve, reject) => {
      objLoader.load(objUrl, resolve, undefined, reject);
    });
    meshCache.set(t, obj);
  }

  const sidecar = await sidecarPromise;
  applyMaterialsToObject(obj, sidecar, library, t);

  if (currentMesh) scene.remove(currentMesh);
  scene.add(obj);
  currentMesh = obj;
  setStatus(`frame t=${t} loaded (${sidecar.meta.scene_shape_count} shapes)`);

  // Sync the seed display from the sidecar's normalized form. The first
  // load establishes the canonical seed even if the URL had it in a
  // legacy/integer form.
  if (sidecar.meta.seed_display) {
    setSeedDisplay(sidecar.meta.seed_display);
    SEED = sidecar.meta.seed;  // canonical form for subsequent fetches
  }

  setTemplateTag(sidecar.meta.template_archetype, sidecar.meta.template_version);
}

function setTemplateTag(archetype, version) {
  const el = document.getElementById('template-tag');
  if (!el) return;
  el.textContent = (archetype && version) ? `(${archetype} v${version})` : '';
}

// === Seed UI ===

function setSeedDisplay(displayString) {
  document.getElementById('seed-display').textContent = displayString;
}

function flashSeedMessage(text) {
  const el = document.getElementById('seed-flash');
  el.textContent = text;
  el.classList.add('visible');
  clearTimeout(flashSeedMessage._t);
  flashSeedMessage._t = setTimeout(() => el.classList.remove('visible'), 1200);
}

function updateUrlSeed(canonicalSeed) {
  const url = new URL(window.location.href);
  url.searchParams.set('seed', canonicalSeed);
  window.history.replaceState({}, '', url);
}

document.getElementById('seed-copy').addEventListener('click', async () => {
  const text = document.getElementById('seed-display').textContent;
  try {
    await navigator.clipboard.writeText(text);
    flashSeedMessage('copied');
  } catch (err) {
    flashSeedMessage('copy failed');
  }
});

document.getElementById('seed-new').addEventListener('click', async () => {
  const resp = await fetch('/seed/random');
  const { canonical, display } = await resp.json();
  SEED = canonical;
  setSeedDisplay(display);
  updateUrlSeed(canonical);
  // Drop the mesh cache and force a reload at the current t.
  meshCache.clear();
  updateForT(currentT);
});

async function loadSeedFromInput() {
  const raw = document.getElementById('seed-input').value.trim();
  if (!raw) return;
  try {
    const resp = await fetch(`/seed/normalize?seed=${encodeURIComponent(raw)}`);
    if (!resp.ok) {
      const err = await resp.json();
      flashSeedMessage(`bad seed: ${err.detail || 'unknown'}`);
      return;
    }
    const { canonical, display } = await resp.json();
    SEED = canonical;
    setSeedDisplay(display);
    updateUrlSeed(canonical);
    document.getElementById('seed-input').value = '';
    meshCache.clear();
    updateForT(currentT);
  } catch (err) {
    flashSeedMessage('parse failed');
  }
}

document.getElementById('seed-load').addEventListener('click', loadSeedFromInput);
document.getElementById('seed-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') loadSeedFromInput();
});

async function updateForT(t) {
  if (inFlight) {
    pendingT = t;
    return;
  }
  inFlight = true;
  try {
    await loadFrame(t);
  } catch (err) {
    setStatus(`failed t=${t}: ${err.message || err}`);
    console.error(err);
  } finally {
    inFlight = false;
    if (pendingT !== null && pendingT !== t) {
      const next = pendingT;
      pendingT = null;
      updateForT(next);
    } else {
      pendingT = null;
    }
  }
}

sliderEl.addEventListener('input', (e) => {
  const t = parseInt(e.target.value, 10);
  currentT = t;
  tDisplayEl.textContent = `T_RENDER = ${t} (DOY)`;
  updateForT(t);
});

// === Boot ===

(async () => {
  setStatus('loading material library...');
  library = await loadLibrary('/materials/library.json');
  setStatus(`library loaded (${library.size} materials)`);
  await updateForT(currentT);
})().catch(err => {
  setStatus(`boot failed: ${err.message || err}`);
  console.error(err);
});

// === Render loop ===

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
