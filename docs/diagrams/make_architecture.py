"""Draw docs/diagrams/architecture-3d.svg, an isometric view of the system architecture.

Run from the repo root: python docs/diagrams/make_architecture.py
"""

import math
from pathlib import Path

WIDTH, HEIGHT = 1200, 640
U = 29                      # pixels per world unit
COS, SIN = math.cos(math.pi / 6), math.sin(math.pi / 6)
OX, OY = 345, 150           # screen position of world (0, 0, 0)
SIZE = 1.9                  # footprint of a component block
GAP = 4.6                   # distance between block centres
HALF = SIZE / 2

BG = "#fbfbfa"
INK, MUTED, LINE = "#1f2937", "#6b7280", "#64748b"

# top (light, dark), left face, right face, edge
PALETTE = {
    "client":  (("#e8eaf6", "#d9ddf1"), "#b9c0e2", "#cbd1ec", "#5c66a8"),
    "api":     (("#e0eaf7", "#cddcf2"), "#9fbbe0", "#b7cdeb", "#36609c"),
    "compute": (("#e3eef5", "#d2e4ef"), "#a8c5d9", "#bed5e5", "#41728f"),
    "secret":  (("#f7efda", "#efe1bb"), "#d8bf83", "#e6d09d", "#94712a"),
    "data":    (("#def0eb", "#cae6de"), "#9acbbd", "#b3d9ce", "#33806d"),
    "report":  (("#eee6f5", "#e1d5ee"), "#c0aad8", "#d1bfe3", "#6f4f9b"),
}

AZURE_Z = 0.25              # top of the Azure tenant slab
STORES_Z = AZURE_Z + 0.2    # top of the data-store slab
PIPE_Z = AZURE_Z + 0.3      # arrows run at this height, between the blocks' sides

API_X = 2 * GAP
STORE_X = 3 * GAP + 0.6
STORES = (STORE_X - HALF - 0.3, -HALF - 0.3, SIZE + 0.6, 3 * GAP + SIZE + 0.6)  # x, y, w, d
AZURE = (GAP - HALF - 0.5, -HALF - 0.7, STORE_X + HALF + 1.0 - (GAP - HALF - 0.5), 3 * GAP + SIZE + 1.4)
BI_X = STORE_X + GAP
BLOB_Y = 0.6 + 1.5 * GAP - 0.3

# name, subtitle, top-face code, centre x, centre y, height, palette, base z
BLOCKS = [
    ("Browser",       "student · teacher · admin", "WEB",   0.0,     GAP,     0.7, "client",  0.0),
    ("React app",     "Static Web Apps",           "UI",    GAP,     GAP,     0.7, "client",  AZURE_Z),
    ("Key Vault",     "secrets",                   "KV",    API_X,   0.0,     0.7, "secret",  AZURE_Z),
    ("FastAPI",       "App Service",               "API",   API_X,   GAP,     1.0, "api",     AZURE_Z),
    ("Storage Queue", "pending runs",              "QUEUE", API_X,   2 * GAP, 0.7, "compute", AZURE_Z),
    ("Worker",        "score · classify",          "ML",    API_X,   3 * GAP, 1.0, "compute", AZURE_Z),
    ("Azure SQL",     "13 tables · 3NF",           "SQL",   STORE_X, 0.6,     0.8, "data",    STORES_Z),
    ("Blob Storage",  "source files",              "BLOB",  STORE_X, BLOB_Y,  0.8, "data",    STORES_Z),
    ("Cosmos DB",     "match reports",             "DOCS",  STORE_X, 3 * GAP, 0.8, "data",    STORES_Z),
    ("Power BI",      "3 SQL views",               "BI",    BI_X,    0.6,     0.7, "report",  0.0),
]
LABEL_BELOW = {"Blob Storage"}   # its label would sit on top of pipe 3

# from (x, y), to (x, y), step number
ARROWS = [
    ((HALF, GAP),             (GAP - HALF, GAP),          None),
    ((GAP + HALF, GAP),       (API_X - HALF, GAP),        1),
    ((API_X, GAP - HALF),     (API_X, HALF),              2),
    ((API_X + HALF, GAP),     (STORES[0], GAP),           3),
    ((API_X, GAP + HALF),     (API_X, 2 * GAP - HALF),    4),
    ((API_X, 2 * GAP + HALF), (API_X, 3 * GAP - HALF),    5),
    ((API_X + HALF, 3 * GAP), (STORE_X - HALF, 3 * GAP),  6),
    ((STORE_X + HALF, 0.6),   (BI_X - HALF, 0.6),         7),
]

STEPS = [
    ("Sign in and call the API", "HTTPS only, short-lived signed token"),
    ("Secrets from Key Vault", "managed identity, nothing in the repo"),
    ("Upload stored", "files to Blob, rows to Azure SQL"),
    ("Run queued", "API returns 202, never scores inline"),
    ("Worker scores every pair", "fingerprint + embedding → classifier"),
    ("Results saved all or none", "reports to Cosmos, one SQL transaction"),
    ("Analytics", "Power BI reads 3 views, read-only user"),
]


def p(x, y, z=0.0):
    return OX + (x - y) * U * COS, OY + (x + y) * U * SIN - z * U


def pts(points):
    return " ".join(f"{a:.1f},{b:.1f}" for a, b in points)


def poly(points, fill, stroke="none", width=1.0, extra=""):
    return (f'<polygon points="{pts(points)}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" '
            f'stroke-linejoin="round"{extra}/>')


def text(x, y, s, size, weight=400, fill=INK, anchor="middle", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{s}</text>')


def flat_text(x, y, z, s, size, fill):
    """Text lying on the plane z, reading along the x axis."""
    tx, ty = p(x, y, z)
    return (f'<text font-size="{size}" font-weight="700" letter-spacing="1" fill="{fill}" fill-opacity="0.8" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'transform="matrix({COS:.4f} {SIN:.4f} {-COS:.4f} {SIN:.4f} {tx:.1f} {ty:.1f})">{s}</text>')


def slab(x0, y0, w, d, h, z, top, left, right, edge):
    x1, y1, z1 = x0 + w, y0 + d, z + h
    return [
        poly([p(x0, y1, z), p(x1, y1, z), p(x1, y1, z1), p(x0, y1, z1)], left, edge, 1),
        poly([p(x1, y0, z), p(x1, y1, z), p(x1, y1, z1), p(x1, y0, z1)], right, edge, 1),
        poly([p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)], top, edge, 1),
    ]


def grid(x0, y0, w, d, z, step=1.0):
    lines = []
    x = x0 + step
    while x < x0 + w - 1e-6:
        (a, b), (c, e) = p(x, y0, z), p(x, y0 + d, z)
        lines.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{e:.1f}"/>')
        x += step
    y = y0 + step
    while y < y0 + d - 1e-6:
        (a, b), (c, e) = p(x0, y, z), p(x0 + w, y, z)
        lines.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{e:.1f}"/>')
        y += step
    return ['<g stroke="#94a3b8" stroke-opacity="0.12" stroke-width="1">'] + lines + ["</g>"]


def block(name, code, cx, cy, h, kind, z):
    (top_a, top_b), left, right, edge = PALETTE[kind]
    x0, y0, x1, y1, z1 = cx - HALF, cy - HALF, cx + HALF, cy + HALF, z + h
    gid = f"g-{name.replace(' ', '')}"
    return [
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{top_a}"/><stop offset="1" stop-color="{top_b}"/></linearGradient>',
        poly([p(x0, y1, z), p(x1, y1, z), p(x1, y1, z1), p(x0, y1, z1)], left, edge, 1, ' stroke-opacity="0.6"'),
        poly([p(x1, y0, z), p(x1, y1, z), p(x1, y1, z1), p(x1, y0, z1)], right, edge, 1, ' stroke-opacity="0.6"'),
        poly([p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)], f"url(#{gid})", edge, 1,
             ' stroke-opacity="0.6"'),
        flat_text(cx, cy, z1, code, 13 if len(code) <= 3 else 11, edge),
    ]


def shadow(cx, cy, z):
    x0, y0, x1, y1 = cx - HALF + 0.3, cy - HALF + 0.3, cx + HALF + 0.45, cy + HALF + 0.45
    return poly([p(x0, y0, z), p(x1, y0, z), p(x1, y1, z), p(x0, y1, z)], "#334155",
                extra=' fill-opacity="0.12" filter="url(#soft)"')


def hidden_length(b, z):
    """How much of an arrow ending at b, coming from behind, the target block's front face covers."""
    for *_, cx, cy, h, _, base in BLOCKS:
        if abs(b[0] - cx) <= HALF + 1e-6 and abs(b[1] - cy) <= HALF + 1e-6:
            return max(0.0, 2 * (base + h - z))   # one unit of x + y rises half a unit on screen
    return 0.0


def badge(x, y, step):
    return [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9.5" fill="#ffffff" stroke="{LINE}" stroke-width="1.2"/>',
            text(x, y + 3.8, str(step), 10.5, 700, INK)]


def arrow(a, b, step, z=PIPE_Z):
    """Return the arrow (drawn in depth order, so blocks in front hide it) and its step badge (drawn last)."""
    if a[0] + a[1] < b[0] + b[1]:
        # pointing towards the viewer: stop where the target block starts to hide the line
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        cut = min(hidden_length(b, z), length - 0.4)
        b = (b[0] - dx / length * cut, b[1] - dy / length * cut)
    (sx, sy), (ex, ey) = p(*a, z), p(*b, z)
    ang = math.atan2(ey - sy, ex - sx)
    head = [(ex, ey),
            (ex - 8 * math.cos(ang - 0.42), ey - 8 * math.sin(ang - 0.42)),
            (ex - 8 * math.cos(ang + 0.42), ey - 8 * math.sin(ang + 0.42))]
    out = [f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex - 4 * math.cos(ang):.1f}" y2="{ey - 4 * math.sin(ang):.1f}" '
           f'stroke="{LINE}" stroke-width="1.4"/>',
           poly(head, LINE)]
    if not step:
        return out, []
    t = 0.5 if a[0] + a[1] < b[0] + b[1] else 0.6
    return out, badge(sx + (ex - sx) * t, sy + (ey - sy) * t, step)


def label(name, sub, cx, cy, h, z):
    """Name and subtitle above the block, or below it; a halo in the background colour keeps them legible."""
    tx, ty = p(cx, cy, z + h)
    if name in LABEL_BELOW:
        y = p(cx + HALF, cy + HALF, z)[1] + 20
    else:
        y = ty - SIZE * U * SIN - 22
    halo = f' stroke="{BG}" stroke-width="4" stroke-linejoin="round" paint-order="stroke"'
    return [text(tx, y, name, 13, 600, INK, extra=halo),
            text(tx, y + 14, sub, 10.5, 400, MUTED, extra=halo)]


def panel():
    x, y, w = 872, 104, 300
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="440" rx="12" fill="#ffffff" stroke="#e5e7eb"/>',
           text(x + 22, y + 32, "Data flow", 14, 700, INK, "start")]
    for i, (title, detail) in enumerate(STEPS):
        ry = y + 70 + i * 52
        out += badge(x + 32, ry, i + 1)
        out += [text(x + 54, ry - 1, title, 12.5, 600, INK, "start"),
                text(x + 54, ry + 15, detail, 11, 400, MUTED, "start")]
    return out


def build():
    parts = []
    ax, ay, aw, ad = AZURE
    parts += slab(ax, ay, aw, ad, AZURE_Z, 0, "#eef2f7", "#dbe3ee", "#e3e9f2", "#b8c4d4")
    parts += grid(ax, ay, aw, ad, AZURE_Z)
    parts += slab(*STORES, STORES_Z - AZURE_Z, AZURE_Z, "#e4f1ed", "#cfe5de", "#d9ebe5", "#a7cbc0")
    # captions on the slabs' side faces: one runs along x (front-left), the other back along y (front-right)
    tx, ty = p(ax + 0.6, ay + ad, 0)
    parts.append(f'<text font-size="10" font-weight="600" letter-spacing="1.5" fill="{MUTED}" '
                 f'transform="matrix({COS:.4f} {SIN:.4f} 0 1 {tx:.1f} {ty + 1:.1f})">AZURE TENANT · SINGLE REGION</text>')
    tx, ty = p(STORES[0] + STORES[2], STORES[1] + STORES[3] - 0.6, AZURE_Z)
    parts.append(f'<text font-size="10" font-weight="600" letter-spacing="1.5" fill="#3f7f6e" '
                 f'transform="matrix({COS:.4f} {-SIN:.4f} 0 1 {tx + 4:.1f} {ty + 12:.1f})">DATA STORES</text>')

    for *_, cx, cy, h, kind, z in BLOCKS:
        parts.append(shadow(cx, cy, z))

    # painter's order: whatever is further back (smaller x + y) is drawn first
    scene, badges = [], []
    for name, sub, code, cx, cy, h, kind, z in BLOCKS:
        scene.append((cx + cy, block(name, code, cx, cy, h, kind, z)))
    for a, b, step in ARROWS:
        line, mark = arrow(a, b, step)
        scene.append(((a[0] + a[1] + b[0] + b[1]) / 2, line))
        badges += mark
    for _, shape in sorted(scene, key=lambda item: item[0]):
        parts += shape
    for name, sub, code, cx, cy, h, kind, z in BLOCKS:
        parts += label(name, sub, cx, cy, h, z)
    parts += badges
    parts += panel()
    return parts


def main():
    body = "\n  ".join(build())
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Inter, 'Segoe UI', -apple-system, Helvetica, Arial, sans-serif">
  <title>CodeTwin system architecture</title>
  <defs>
    <filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4"/></filter>
  </defs>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14" fill="{BG}" stroke="#e5e7eb"/>
  <text x="28" y="46" font-size="22" font-weight="700" fill="{INK}">CodeTwin system architecture</text>
  <text x="28" y="70" font-size="13" fill="{MUTED}">The API guards every store; a queue feeds the background worker that runs the comparison.</text>
  {body}
</svg>
"""
    out = Path(__file__).with_name("architecture-3d.svg")
    out.write_text(svg)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
