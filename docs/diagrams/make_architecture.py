"""Draw docs/diagrams/architecture-3d.svg, an isometric view of the system architecture.

Run from the repo root: python docs/diagrams/make_architecture.py
"""

import math
from pathlib import Path

U = 32                      # pixels per world unit
COS, SIN = math.cos(math.pi / 6), math.sin(math.pi / 6)
OX, OY = 360, 112           # screen position of world (0, 0, 0)
SIZE = 1.9                  # footprint of a component block
GAP = 4.6                   # distance between block centres
HALF = SIZE / 2

PALETTE = {                 # top, left face, right face, outline
    "client":   ("#e0e7ff", "#c7d2fe", "#a5b4fc", "#4338ca"),
    "compute":  ("#dbeafe", "#bfdbfe", "#93c5fd", "#1d4ed8"),
    "api":      ("#bfdbfe", "#93c5fd", "#60a5fa", "#1e40af"),
    "secret":   ("#fef3c7", "#fde68a", "#fcd34d", "#b45309"),
    "data":     ("#ccfbf1", "#99f6e4", "#5eead4", "#0f766e"),
    "report":   ("#f3e8ff", "#e9d5ff", "#d8b4fe", "#7e22ce"),
    "azure":    ("#e9eff8", "#d3deee", "#bccbe0", "#94a3b8"),
    "stores":   ("#f1f5f9", "#e2e8f0", "#cbd5e1", "#94a3b8"),
}

AZURE_Z = 0.25              # top of the Azure tenant slab
STORES_Z = AZURE_Z + 0.2    # top of the data-store slab
PIPE_Z = AZURE_Z + 0.3      # arrows run at this height, between the blocks' sides

API_X = 2 * GAP
STORE_X = 3 * GAP + 0.6
STORES = (STORE_X - HALF - 0.3, -HALF - 0.3, SIZE + 0.6, 3 * GAP + SIZE + 0.6)  # x, y, w, d
AZURE = (GAP - HALF - 0.5, -HALF - 0.7, STORE_X + HALF + 1.0 - (GAP - HALF - 0.5), 3 * GAP + SIZE + 1.4)
BI_X = STORE_X + GAP

# name, subtitle, centre x, centre y, height, palette, base z
BLOCKS = [
    ("Browser",           "all three roles",   0.0,     GAP,     0.7, "client",  0.0),
    ("React app",         "Static Web Apps",   GAP,     GAP,     0.7, "client",  AZURE_Z),
    ("Key Vault",         "secrets",           API_X,   0.0,     0.7, "secret",  AZURE_Z),
    ("FastAPI",           "App Service",       API_X,   GAP,     1.0, "api",     AZURE_Z),
    ("Storage Queue",     "pending runs",      API_X,   2 * GAP, 0.7, "compute", AZURE_Z),
    ("Worker",            "score · classify",  API_X,   3 * GAP, 1.0, "compute", AZURE_Z),
    ("Azure SQL",         "13 tables · 3NF",   STORE_X, 0.6,     0.8, "data",    STORES_Z),
    ("Blob Storage",      "source files",      STORE_X, 0.6 + 1.5 * GAP - 0.3, 0.8, "data", STORES_Z),
    ("Cosmos DB",         "match reports",     STORE_X, 3 * GAP, 0.8, "data",    STORES_Z),
    ("Power BI",          "3 SQL views",       BI_X,    0.6,     0.7, "report",  0.0),
]

# from (x, y), to (x, y), label, label lift in pixels
ARROWS = [
    ((HALF, GAP),           (GAP - HALF, GAP),          "",             0),
    ((GAP + HALF, GAP),     (API_X - HALF, GAP),        "HTTPS, token", -16),
    ((API_X, GAP - HALF),   (API_X, HALF),              "secrets",      0),
    ((API_X + HALF, GAP),   (STORES[0], GAP),           "SQL, files",   0),
    ((API_X, GAP + HALF),   (API_X, 2 * GAP - HALF),    "run job",      0),
    ((API_X, 2 * GAP + HALF), (API_X, 3 * GAP - HALF),  "",             0),
    ((API_X + HALF, 3 * GAP), (STORE_X - HALF, 3 * GAP), "results",     0),
    ((STORE_X + HALF, 0.6), (BI_X - HALF, 0.6),         "views",        0),
]


def p(x, y, z=0.0):
    return OX + (x - y) * U * COS, OY + (x + y) * U * SIN - z * U


def poly(points, fill, stroke, width=1.0):
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"/>'


def box(x0, y0, w, d, h, z, colours, width=1.2):
    top, left, right, line = colours
    x1, y1, z1 = x0 + w, y0 + d, z + h
    return [
        poly([p(x0, y1, z), p(x1, y1, z), p(x1, y1, z1), p(x0, y1, z1)], left, line, width),
        poly([p(x1, y0, z), p(x1, y1, z), p(x1, y1, z1), p(x1, y0, z1)], right, line, width),
        poly([p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1)], top, line, width),
    ]


def text(x, y, s, size, weight=400, fill="#0f172a", anchor="middle"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}">{s}</text>')


def hidden_length(b, z):
    """How much of an arrow ending at b, coming from behind, the target block's front face covers."""
    for _, _, cx, cy, h, _, base in BLOCKS:
        if abs(b[0] - cx) <= HALF + 1e-6 and abs(b[1] - cy) <= HALF + 1e-6:
            return max(0.0, 2 * (base + h - z))   # one unit of x + y rises half a unit on screen
    return 0.0


def arrow(a, b, label, lift=0, z=PIPE_Z):
    """Return the arrow (drawn in depth order, so blocks in front hide it) and its label (drawn last)."""
    if a[0] + a[1] < b[0] + b[1]:
        # pointing towards the viewer: stop where the target block starts to hide the line
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        cut = min(hidden_length(b, z), length - 0.4)
        b = (b[0] - dx / length * cut, b[1] - dy / length * cut)
    (sx, sy), (ex, ey) = p(*a, z), p(*b, z)
    ang = math.atan2(ey - sy, ex - sx)
    head = [(ex, ey),
            (ex - 9 * math.cos(ang - 0.4), ey - 9 * math.sin(ang - 0.4)),
            (ex - 9 * math.cos(ang + 0.4), ey - 9 * math.sin(ang + 0.4))]
    out = [f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#475569" stroke-width="1.6"/>',
           poly(head, "#475569", "#475569")]
    tag = []
    if label:
        # a block in front hides the far end of the arrow, so put the label nearer the back end
        t = 0.5 if a[0] + a[1] < b[0] + b[1] else 0.62
        mx, my = sx + (ex - sx) * t, sy + (ey - sy) * t - lift
        w = len(label) * 6.4 + 12
        tag.append(f'<rect x="{mx - w / 2:.1f}" y="{my - 9:.1f}" width="{w:.1f}" height="18" rx="9" '
                   f'fill="#ffffff" stroke="#cbd5e1"/>')
        tag.append(text(mx, my + 4, label, 11, 500, "#334155"))
    return out, tag


def build():
    parts = []
    # Azure tenant slab and the raised data-store slab
    ax, ay, aw, ad = AZURE
    parts += box(ax, ay, aw, ad, AZURE_Z, 0, PALETTE["azure"])
    parts += box(*STORES[:2], *STORES[2:], STORES_Z - AZURE_Z, AZURE_Z, PALETTE["stores"])
    # slab captions run along the slab's front-left edge (parallel to the x axis)
    for (x, y, z), caption in [((ax + 0.6, ay + ad, 0), "AZURE TENANT · SINGLE REGION"),
                               ((STORES[0] + 0.3, STORES[1] + STORES[3], AZURE_Z), "DATA STORES")]:
        tx, ty = p(x, y, z)
        parts.append(f'<text font-size="11" font-weight="700" letter-spacing="1.5" fill="#64748b" '
                     f'transform="matrix({COS:.4f} {SIN:.4f} 0 1 {tx:.1f} {ty + 2:.1f})">{caption}</text>')

    # painter's order: whatever is further back (smaller x + y) is drawn first
    scene, tags = [], []
    for name, sub, cx, cy, h, kind, z in BLOCKS:
        shape = box(cx - HALF, cy - HALF, SIZE, SIZE, h, z, PALETTE[kind], 1.6 if kind == "api" else 1.2)
        scene.append((cx + cy, shape))
    for a, b, label, lift in ARROWS:
        line, tag = arrow(a, b, label, lift)
        scene.append(((a[0] + a[1] + b[0] + b[1]) / 2, line))
        tags += tag
    for _, shape in sorted(scene, key=lambda item: item[0]):
        parts += shape
    for name, sub, cx, cy, h, kind, z in BLOCKS:
        tx, ty = p(cx, cy, z + h)
        parts.append(text(tx, ty - 1, name, 13, 700))
        parts.append(text(tx, ty + 13, sub, 10, 400, "#334155"))
    parts += tags

    legend = [("client", "Client"), ("api", "API and worker"), ("secret", "Secrets"),
              ("data", "Data stores"), ("report", "Analytics")]
    lx = 28
    for kind, label in legend:
        parts.append(f'<rect x="{lx}" y="80" width="12" height="12" rx="3" fill="{PALETTE[kind][1]}" '
                     f'stroke="{PALETTE[kind][3]}"/>')
        parts.append(text(lx + 18, 90, label, 12, 500, "#334155", "start"))
        lx += 34 + len(label) * 6.6

    return parts


def main():
    width, height = 980, 680
    body = "\n  ".join(build())
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Inter, 'Segoe UI', Helvetica, Arial, sans-serif">
  <rect width="{width}" height="{height}" rx="16" fill="#f8fafc"/>
  <text x="28" y="42" font-size="22" font-weight="700" fill="#0f172a">CodeTwin · system architecture</text>
  <text x="28" y="64" font-size="13" fill="#475569">The API guards every store; a queue feeds the background worker that runs the comparison.</text>
  {body}
  <text x="{width - 28}" y="{height - 22}" font-size="11" fill="#64748b" text-anchor="end">The API and the worker both read their secrets from Key Vault (API link shown).</text>
</svg>
"""
    out = Path(__file__).with_name("architecture-3d.svg")
    out.write_text(svg)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
