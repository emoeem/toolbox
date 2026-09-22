"""CPU SDF raymarch renderer used when no suitable native 3D texture filter is available."""
from __future__ import annotations

import numpy as np
from PIL import Image

RAYMARCH_DEFAULTS = {
    "steps": 96,
    "max_distance": 6.0,
    "surface_threshold": 0.0025,
    "light_direction": (0.55, 0.7, 0.45),
    "ambient": 0.22,
    "diffuse": 0.72,
    "specular": 0.28,
    "color_a": (75, 105, 210),
    "color_b": (225, 105, 155),
    "fresnel": 0.35,
    "background": (10, 12, 22),
    "gradient": 0.32,
    "seed": 42,
}


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-8)


def _hash3(p, seed):
    q = p * np.array([127.1, 311.7, 74.7], dtype=np.float32) + float(seed) * 0.1237
    return np.mod(np.sin(q) * 43758.5453, 1.0)


def _sdf(p, seed):
    # A stable, inexpensive union of a sphere and a torus with subtle seeded deformation.
    r = np.linalg.norm(p, axis=-1)
    sphere = r - 0.92
    qx = np.sqrt(p[..., 0] ** 2 + p[..., 2] ** 2) - 0.72
    torus = np.sqrt(qx * qx + p[..., 1] ** 2) - 0.18
    wobble = (_hash3(p, seed)[..., 0] - 0.5) * 0.035
    return np.minimum(sphere, torus + wobble)


def _normal(p, seed, eps=0.0015):
    e = np.array([eps, 0, 0], dtype=np.float32)
    x = _sdf(p + e, seed) - _sdf(p - e, seed)
    e = np.array([0, eps, 0], dtype=np.float32)
    y = _sdf(p + e, seed) - _sdf(p - e, seed)
    e = np.array([0, 0, eps], dtype=np.float32)
    z = _sdf(p + e, seed) - _sdf(p - e, seed)
    n = np.stack((x, y, z), axis=-1)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)


def render_raymarch(width=256, height=256, params=None):
    """Render an RGB PIL image at 256x256 by default using CPU SDF sphere tracing."""
    p = dict(RAYMARCH_DEFAULTS)
    if params:
        p.update(params)
    width, height = max(16, int(width)), max(16, int(height))
    steps = int(np.clip(p["steps"], 8, 256))
    max_distance = float(np.clip(p["max_distance"], 1.0, 20.0))
    threshold = float(np.clip(p["surface_threshold"], 0.0002, 0.05))
    seed = int(p["seed"])

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    aspect = width / height
    x = (2.0 * (xx + 0.5) / width - 1.0) * aspect
    y = 1.0 - 2.0 * (yy + 0.5) / height
    ro = np.zeros((height, width, 3), dtype=np.float32)
    ro[..., 2] = -3.15
    rd = np.stack((x, y, np.full_like(x, 1.65)), axis=-1)
    rd /= np.linalg.norm(rd, axis=-1, keepdims=True)

    t = np.zeros((height, width), dtype=np.float32)
    hit = np.zeros((height, width), dtype=bool)
    pos = ro.copy()
    for _ in range(steps):
        active = (~hit) & (t < max_distance)
        if not np.any(active):
            break
        d = _sdf(pos, seed)
        newly = active & (np.abs(d) < threshold)
        hit |= newly
        advance = np.maximum(d, threshold * 0.35)
        t += np.where(active & ~newly, advance, 0.0)
        pos = ro + rd * t[..., None]

    bg = np.asarray(p["background"], dtype=np.float32) / 255.0
    grad = float(np.clip(p["gradient"], 0.0, 1.0))
    horizon = np.clip(rd[..., 1] * 0.5 + 0.5, 0, 1)[..., None]
    bg2 = np.clip(bg * (0.55 + 0.45 * horizon) + grad * horizon * 0.18, 0, 1)
    out = np.broadcast_to(bg2, (height, width, 3)).copy()
    if np.any(hit):
        hp = pos[hit]
        n = _normal(hp, seed)
        l = _unit(p["light_direction"])
        v = _unit(-np.array([0.0, 0.0, -3.15], dtype=np.float32))
        diffuse = np.clip(np.sum(n * l, axis=-1), 0, 1)
        h = _unit(l + v)
        spec = np.power(np.clip(np.sum(n * h, axis=-1), 0, 1), 32.0)
        fres = np.power(1.0 - np.clip(np.sum(n * (-rd[hit]), axis=-1), 0, 1), 4.0)
        ca = np.asarray(p["color_a"], dtype=np.float32)[:3] / 255.0
        cb = np.asarray(p["color_b"], dtype=np.float32)[:3] / 255.0
        mix = np.clip(hp[:, 1] * 0.5 + 0.5 + 0.08 * (_hash3(hp, seed)[:, 1] - 0.5), 0, 1)[:, None]
        base = ca * (1.0 - mix) + cb * mix
        light = float(np.clip(p["ambient"], 0, 1)) + float(np.clip(p["diffuse"], 0, 2)) * diffuse[:, None]
        lit = base * light + float(np.clip(p["specular"], 0, 2)) * spec[:, None]
        lit = lit * (1.0 - float(np.clip(p["fresnel"], 0, 1)) * fres[:, None]) + bg2[hit] * fres[:, None] * float(np.clip(p["fresnel"], 0, 1))
        out[hit] = np.clip(lit, 0, 1)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB")
