#!/usr/bin/env python3
"""
Measure a GPX track against the streets it claims to run along.

The bench's "on real streets" check is a number, not an impression: the share
of track points within 25 m of a mapped street centreline. Before this it was
measured by hand once and quoted in a post, which is not a check anyone else
can repeat. Everything here is free — the OSM extract already ships with the
renderer, so judging a route costs no tokens.

    python3 harness/checkers/gpx-streets.py <file.gpx> [--json]

Distances are planar, computed in metres on a local equirectangular projection
about the track's own centre. Over a few kilometres at 38 degrees south the
error against a proper geodesic is well under a metre, which is far below the
25 m the check turns on.
"""
import json, math, os, sys, xml.etree.ElementTree as ET

BASEMAP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "renderers", "melbourne_cbd.json")
NEAR_M = 25.0          # the check's threshold
BANDS = (8, 15, 25, 50)

def track_points(path):
    """Every trkpt, in order, with the segment it belongs to."""
    ns = {"g": "http://www.topografix.com/GPX/1/1"}
    root = ET.parse(path).getroot()
    if not root.tag.startswith("{"):
        ns = {"g": ""}
    segs = []
    for seg in root.iter():
        if seg.tag.split("}")[-1] != "trkseg":
            continue
        pts = [(float(p.get("lon")), float(p.get("lat")))
               for p in seg if p.tag.split("}")[-1] == "trkpt"]
        if pts:
            segs.append(pts)
    return segs

def projector(lat0):
    """Degrees to metres, east and north, about a reference latitude."""
    mlat = 111132.92 - 559.82 * math.cos(2 * math.radians(lat0))
    mlon = 111412.84 * math.cos(math.radians(lat0))
    return lambda lon, lat: (lon * mlon, lat * mlat)

def seg_distance(px, py, ax, ay, bx, by):
    """Point to line-segment distance, all in metres."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def measure(gpx_path):
    segs = track_points(gpx_path)
    pts = [p for s in segs for p in s]
    if not pts:
        raise SystemExit(f"no track points in {gpx_path}")

    lat0 = sum(lat for _, lat in pts) / len(pts)
    to_m = projector(lat0)

    basemap = json.load(open(BASEMAP))
    # Flatten every street into metre-space segments once, tagged with a name,
    # so the nearest-street lookup also says which street it is.
    edges = []
    for way in basemap["streets"]:
        g = [to_m(lon, lat) for lon, lat in way["g"]]
        for a, b in zip(g, g[1:]):
            edges.append((a[0], a[1], b[0], b[1], way.get("n") or "(unnamed)"))

    dists, names = [], {}
    for lon, lat in pts:
        px, py = to_m(lon, lat)
        best, who = float("inf"), None
        for ax, ay, bx, by, name in edges:
            # Cheap reject before the real distance: a segment whose endpoints
            # are both far away in one axis cannot be the nearest.
            if min(ax, bx) - px > best or px - max(ax, bx) > best:
                continue
            if min(ay, by) - py > best or py - max(ay, by) > best:
                continue
            d = seg_distance(px, py, ax, ay, bx, by)
            if d < best:
                best, who = d, name
        dists.append(best)
        names[who] = names.get(who, 0) + 1

    # Route length, and the largest jump between consecutive points: a track
    # that teleports between letters is not one continuous run.
    length, jump = 0.0, 0.0
    for s in segs:
        m = [to_m(lon, lat) for lon, lat in s]
        for a, b in zip(m, m[1:]):
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            length += d
            jump = max(jump, d)

    n = len(dists)
    return {
        "file": os.path.basename(gpx_path),
        "points": n,
        "segments": len(segs),
        "length_km": round(length / 1000, 2),
        "largest_gap_m": round(jump, 1),
        "worst_point_m": round(max(dists), 1),
        "median_m": round(sorted(dists)[n // 2], 1),
        "within": {f"{b}m": round(100 * sum(d <= b for d in dists) / n, 1) for b in BANDS},
        "on_streets_pct": round(100 * sum(d <= NEAR_M for d in dists) / n, 1),
        "streets_used": sorted(names.items(), key=lambda kv: -kv[1])[:10],
    }

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__.strip())
    r = measure(args[0])
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2))
    else:
        print(f"{r['file']}: {r['points']} points in {r['segments']} segment(s), {r['length_km']} km")
        print(f"  on streets (<={int(NEAR_M)} m): {r['on_streets_pct']}%   median {r['median_m']} m   worst {r['worst_point_m']} m")
        print("  within: " + ", ".join(f"{k} {v}%" for k, v in r["within"].items()))
        print(f"  largest gap between points: {r['largest_gap_m']} m")
        print("  nearest streets: " + ", ".join(f"{n} ({c})" for n, c in r["streets_used"][:6]))
