// Material loader for the plant_sim viewer.
//
// Loads materials/library.json + the per-render OBJ sidecar JSON
// (output/<lpy_stem>_t<doy>.materials.json) and applies materials to the
// loaded OBJ mesh.
//
// API:
//   const library = await loadLibrary('materials/library.json');
//   const sidecar = await loadSidecar('output/echinacea_purpurea_seed_42_t250.materials.json');
//   applyMaterialsToObject(obj, sidecar, library, t_render);
//
// Color curves are evaluated at the current t_render (fractional DOY).
// Re-call applyMaterialsToObject() on slider scrub to update colors.

import * as THREE from 'three';

const SIDE_MAP = {
  FrontSide: THREE.FrontSide,
  BackSide: THREE.BackSide,
  DoubleSide: THREE.DoubleSide,
};

const DEFAULT_FALLBACK_COLOR = 0x888888;

// === Loading ===

export async function loadLibrary(jsonPath) {
  const resp = await fetch(jsonPath);
  if (!resp.ok) {
    throw new Error(`Failed to load material library at ${jsonPath}: HTTP ${resp.status}`);
  }
  const json = await resp.json();
  // Library JSON is {id: entry}; return as a Map for fast lookup.
  return new Map(Object.entries(json));
}

export async function loadSidecar(jsonPath) {
  const resp = await fetch(jsonPath);
  if (!resp.ok) {
    throw new Error(`Failed to load sidecar at ${jsonPath}: HTTP ${resp.status}`);
  }
  return await resp.json();
}

// === Material construction ===

export function materialForId(id, library, t_render) {
  const entry = library.get(id);
  if (!entry) {
    return defaultMaterial(`unknown material_id ${id}`);
  }
  return buildMaterial(entry, t_render);
}

function buildMaterial(entry, t_render) {
  const colorHex = entry.color_curve
    ? evaluateColorCurve(entry.color_curve, t_render)
    : entry.color;

  const params = {
    color: new THREE.Color(colorHex),
    roughness: entry.roughness ?? 0.7,
    metalness: entry.metalness ?? 0.0,
    side: SIDE_MAP[entry.side] ?? THREE.DoubleSide,
  };

  if (entry.type === 'MeshStandardMaterial' || entry.type === undefined) {
    return new THREE.MeshStandardMaterial(params);
  }
  // Unknown type -> fall back. Don't throw; viewer keeps running.
  console.warn(`Unknown material type ${entry.type}; falling back to MeshStandardMaterial`);
  return new THREE.MeshStandardMaterial(params);
}

function defaultMaterial(reason) {
  console.warn(`Falling back to default material: ${reason}`);
  return new THREE.MeshStandardMaterial({
    color: DEFAULT_FALLBACK_COLOR,
    roughness: 0.7,
    metalness: 0.0,
    side: THREE.DoubleSide,
  });
}

// === Color-curve evaluation (linear interpolation by DOY) ===

export function evaluateColorCurve(keyframes, t_render) {
  // Clamp at endpoints
  if (t_render <= keyframes[0].doy) return keyframes[0].color;
  const last = keyframes[keyframes.length - 1];
  if (t_render >= last.doy) return last.color;

  // Find the bracketing pair
  for (let i = 0; i < keyframes.length - 1; i++) {
    const a = keyframes[i];
    const b = keyframes[i + 1];
    if (t_render >= a.doy && t_render <= b.doy) {
      const t = (t_render - a.doy) / (b.doy - a.doy);
      return lerpHex(a.color, b.color, t);
    }
  }
  return keyframes[0].color; // unreachable
}

function lerpHex(hexA, hexB, t) {
  const ca = new THREE.Color(hexA);
  const cb = new THREE.Color(hexB);
  const r = ca.r + (cb.r - ca.r) * t;
  const g = ca.g + (cb.g - ca.g) * t;
  const b = ca.b + (cb.b - ca.b) * t;
  return '#' + new THREE.Color(r, g, b).getHexString();
}

// === OBJ-mesh material application ===

/**
 * Walk a loaded OBJ Object3D and apply materials based on the sidecar.
 *
 * @param {THREE.Object3D} obj          loaded by THREE.OBJLoader
 * @param {{shapes: {name, material_id}[]}} sidecar  output/foo.materials.json
 * @param {Map<string, object>} library  loaded by loadLibrary()
 * @param {number} t_render              fractional day-of-year, drives color curves
 */
export function applyMaterialsToObject(obj, sidecar, library, t_render) {
  // Build a mesh-name -> material_id map from the sidecar.
  const nameToMatId = new Map();
  for (const entry of sidecar.shapes) {
    nameToMatId.set(entry.name, entry.material_id);
  }

  obj.traverse((child) => {
    if (!child.isMesh) return;
    const matId = nameToMatId.get(child.name);
    if (matId === undefined) {
      child.material = defaultMaterial(`mesh ${child.name} not in sidecar`);
      return;
    }
    child.material = materialForId(matId, library, t_render);
  });
}
