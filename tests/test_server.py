"""Server tests for Step 7.

Uses FastAPI's TestClient (no actual port bind). Exercises:
- /health returns ok
- /render/scene.obj returns OBJ text with `o SHAPE_<id>` group lines
- /render/scene.materials.json returns valid sidecar JSON
- A second request for the same (species, seed, t) hits the disk cache
- Invalid species_id, seed, or t are rejected with 4xx
- Static mounts: /materials/library.json and /viewer/index.html serve
- Root redirects to the viewer
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from plant_sim.server.app import app, reset_cache


@pytest.fixture
def client():
    reset_cache()
    return TestClient(app)


# ---- Health + root ----

def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_root_redirects_to_viewer(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "/viewer/" in resp.headers["location"]


# ---- /render/scene.obj ----

def test_render_obj_returns_obj_text(client):
    resp = client.get("/render/scene.obj?species=echinacea_purpurea&seed=42&t=250")
    assert resp.status_code == 200
    body = resp.text
    # OBJ must have at least one stable shape group line
    assert "o SHAPE_" in body
    # Should NOT contain the per-process address-suffixed names
    assert "SHAPEID_" not in body


def test_render_obj_pre_flush_is_empty(client):
    resp = client.get("/render/scene.obj?species=echinacea_purpurea&seed=42&t=50")
    assert resp.status_code == 200
    body = resp.text
    assert "o SHAPE_" not in body  # No shapes pre-flush


# ---- /render/scene.materials.json ----

def test_render_sidecar_returns_json(client):
    from plant_sim.schema.seed import Seed
    resp = client.get("/render/scene.materials.json?species=echinacea_purpurea&seed=42&t=250")
    assert resp.status_code == 200
    body = resp.json()
    assert "shapes" in body
    assert "meta" in body
    assert body["meta"]["t_render"] == 250.0
    assert body["meta"]["species"] == "echinacea_purpurea"
    # Seed comes back in canonical (8-char base32) and display forms
    assert body["meta"]["seed"] == Seed(42).canonical()
    assert body["meta"]["seed_display"] == Seed(42).display()
    assert all("name" in e and "material_id" in e for e in body["shapes"])


def test_random_seed_endpoint(client):
    resp = client.get("/seed/random")
    assert resp.status_code == 200
    body = resp.json()
    assert "canonical" in body and "display" in body
    assert len(body["canonical"]) == 8
    assert "-" in body["display"]


def test_normalize_seed_endpoint(client):
    """Viewer's 'paste seed' input round-trips arbitrary user input."""
    resp = client.get("/seed/normalize?seed=xqf2-d6s1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["canonical"] == "XQF2D6S1"
    assert body["display"] == "XQF2-D6S1"


def test_normalize_rejects_garbage(client):
    # Wrong length after stripping separators
    resp = client.get("/seed/normalize?seed=ABC")
    assert resp.status_code == 400
    # 'U' isn't in Crockford base32
    resp = client.get("/seed/normalize?seed=ABCDEFGU")
    assert resp.status_code == 400


def test_string_seed_in_render_url(client):
    """End-to-end: a Crockford string seed in the URL renders cleanly."""
    resp = client.get(
        "/render/scene.materials.json?species=echinacea_purpurea&seed=XQF2-D6S1&t=200"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["seed"] == "XQF2D6S1"
    assert body["meta"]["seed_display"] == "XQF2-D6S1"


def test_render_sidecar_count_matches_obj_groups(client):
    obj_resp = client.get("/render/scene.obj?species=echinacea_purpurea&seed=42&t=250")
    json_resp = client.get("/render/scene.materials.json?species=echinacea_purpurea&seed=42&t=250")
    obj_groups = [l for l in obj_resp.text.splitlines() if l.startswith("o ")]
    sidecar = json_resp.json()
    assert len(obj_groups) == len(sidecar["shapes"])


# ---- Caching: lstring is reused across different t values ----

def test_lstring_cache_persists_across_t(client):
    # Two requests with same (species, seed) but different t: derive only happens once
    client.get("/render/scene.obj?species=echinacea_purpurea&seed=42&t=180")
    client.get("/render/scene.obj?species=echinacea_purpurea&seed=42&t=220")
    health = client.get("/health").json()
    # cache_size counts (species, seed) keys; should be 1 even though we hit two t values
    assert health["cache_size"] == 1


# ---- Validation ----

def test_unknown_species_404(client):
    resp = client.get("/render/scene.obj?species=nonexistent_species&seed=42&t=200")
    assert resp.status_code == 404


def test_invalid_t_rejected(client):
    resp = client.get("/render/scene.obj?species=echinacea_purpurea&seed=42&t=999")
    assert resp.status_code == 400


def test_negative_seed_rejected(client):
    resp = client.get("/render/scene.obj?species=echinacea_purpurea&seed=-1&t=200")
    assert resp.status_code == 400


def test_invalid_species_id_chars_rejected(client):
    resp = client.get("/render/scene.obj?species=../../etc/passwd&seed=42&t=200")
    assert resp.status_code == 400


# ---- Static mounts ----

def test_materials_library_served(client):
    resp = client.get("/materials/library.json")
    assert resp.status_code == 200
    body = resp.json()
    assert "leaf_mature_green" in body


def test_viewer_index_html_served(client):
    resp = client.get("/viewer/index.html")
    assert resp.status_code == 200
    assert "plant_sim viewer" in resp.text.lower()


def test_viewer_main_js_served(client):
    resp = client.get("/viewer/main.js")
    assert resp.status_code == 200
    assert "OrbitControls" in resp.text
    assert "applyMaterialsToObject" in resp.text


def test_viewer_material_loader_served(client):
    resp = client.get("/viewer/material_loader.js")
    assert resp.status_code == 200
    assert "evaluateColorCurve" in resp.text
