#!/usr/bin/env python3
"""The hopper has to be hollow, and the only way to know is to load it.

MuJoCo collides a mesh as its convex hull, so a hopper modelled as one cone
mesh is a solid cone: the beans start buried in it and the picture still looks
roughly right from outside. Everything below is decided against the model the
script writes out, loaded and probed here — a ray dropped down the axis has to
reach past the beans, which it cannot do through a filled cone.
"""
import os
import re
import subprocess
import sys
import tempfile

import mujoco
import numpy as np
from scipy.spatial import ConvexHull

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _grade import finish

N_BEANS = 50
ELLIPSOID = 4  # mjtGeom.mjGEOM_ELLIPSOID
FREE = 0  # mjtJoint.mjJNT_FREE


def bean_bodies(m):
    """Bodies that are one free body carrying geoms — the beans, whatever they
    are called. Named-based matching would only reward calling them "bean"."""
    out = []
    for b in range(1, m.nbody):
        if m.body_jntnum[b] != 1 or m.body_dofnum[b] != 6 or m.body_geomnum[b] < 1:
            continue
        if m.jnt_type[m.body_jntadr[b]] == FREE:
            out.append(b)
    return out


class Rays:
    """Rays against what the beans would actually collide with.

    2026-10-10: mj_ray alone missed the trap this checker exists for. It casts
    against a mesh's triangles, but MuJoCo collides a mesh as its convex hull,
    so a funnel mesh with real faces looked hollow to the probe while the beans
    rested on a solid cone. It also skips geoms drawn with alpha 0 and counts
    geoms that collide with nothing. So here: only geoms that can touch a bean
    count, whatever their colour, and a mesh counts as its hull.
    """

    def __init__(self, m, d, beans):
        bean_geoms = {g for b in beans for g in range(m.body_geomadr[b], m.body_geomadr[b] + m.body_geomnum[b])}

        def touches_beans(g):
            return any((m.geom_contype[g] & m.geom_conaffinity[b]) or (m.geom_contype[b] & m.geom_conaffinity[g])
                       for b in bean_geoms)

        self.m, self.d, self.hulls = m, d, []
        self.solid = set()
        for g in range(m.ngeom):
            if g in bean_geoms or not touches_beans(g):
                m.geom_group[g] = 5
                continue
            self.solid.add(g)
            if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH:
                m.geom_group[g] = 5
                k = m.geom_dataid[g]
                v = m.mesh_vert[m.mesh_vertadr[k]:m.mesh_vertadr[k] + m.mesh_vertnum[k]]
                w = d.geom_xpos[g] + v @ d.geom_xmat[g].reshape(3, 3).T
                try:
                    self.hulls.append((g, ConvexHull(w).equations))
                except Exception:
                    pass  # a flat or degenerate mesh has no inside to fall into
            else:
                m.geom_group[g] = 0
                m.geom_rgba[g, 3] = 1.0
        self.groups = np.array([1, 1, 1, 1, 1, 0], dtype=np.uint8)

    def cast(self, pnt, vec):
        """Distance to the first solid surface along the ray, or -1."""
        gid = np.zeros(1, dtype=np.int32)
        best = mujoco.mj_ray(self.m, self.d, pnt, vec, self.groups, 1, -1, gid)
        best = np.inf if best < 0 else best
        for _, eq in self.hulls:
            lo, hi = -np.inf, np.inf
            for n, off in zip(eq[:, :3], eq[:, 3]):
                num, den = -(n @ pnt + off), n @ vec
                if abs(den) < 1e-12:
                    if num < 0:
                        lo, hi = 1, 0
                        break
                elif den > 0:
                    hi = min(hi, num / den)
                else:
                    lo = max(lo, num / den)
            if lo <= hi and hi >= 0:
                best = min(best, max(lo, 0.0))
        return -1 if best == np.inf else best


def probe(m, beans):
    """Two questions about the hopper, asked of the model as written.

    Open: drop rays down the bean cloud's own axis and see whether they get
    past it. The beans are lifted out of the way first, so what the ray meets
    is the hopper. In a hopper built from convex pieces the axis is clear air
    and the ray runs on down to the gate or the tray, below every bean; in a
    single convex hull it stops at the cone's surface, above them.

    Enclosed (2026-10-10, new): the open probe passed beans stacked on top of
    a solid cone, and beans spawned beside the hopper, because in both the
    ray clears the bean cloud. So from each bean's start, look sideways in
    eight directions: a bean inside the hopper has a wall it would hit in
    nearly all of them. Most beans have to start that way.
    """
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    p = np.array([d.xpos[b] for b in beans])
    axis, ztop, zbot = p[:, :2].mean(axis=0), p[:, 2].max(), p[:, 2].min()

    for b in beans:  # park the beans a long way up
        d.qpos[m.jnt_qposadr[m.body_jntadr[b]] + 2] += 100.0
    mujoco.mj_kinematics(m, d)
    rays = Rays(m, d, beans)

    start_z = ztop + max(0.05, 0.5 * m.stat.extent)
    span = float(np.ptp(p[:, 2])) or 0.01
    step = max(0.002, 0.05 * span)
    clear = 0
    probes = [(0, 0), (step, 0), (-step, 0), (0, step), (0, -step)]
    for dx, dy in probes:
        pnt = np.array([axis[0] + dx, axis[1] + dy, start_z])
        dist = rays.cast(pnt, np.array([0.0, 0.0, -1.0]))
        # A ray that hits nothing at all has certainly cleared the bean zone.
        if dist < 0 or start_z - dist < zbot:
            clear += 1

    reach = max(0.3, float(m.stat.extent))
    sideways = [np.array([np.cos(a), np.sin(a), 0.0]) for a in np.arange(8) * np.pi / 4]
    enclosed = 0
    for q in p:
        hits = sum(0 <= rays.cast(q.copy(), v) <= reach for v in sideways)
        enclosed += hits >= 7
    return bool(clear >= 3), bool(enclosed >= 0.5 * len(beans))


src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
source = open(src, encoding="utf-8", errors="replace").read()

# Run it ourselves rather than trusting the frame's stdout, which the renderer
# truncates, and because model.xml is what we are really after.
with tempfile.TemporaryDirectory() as tmp:
    open(os.path.join(tmp, "script.py"), "w").write(source)
    fig = os.path.join(tmp, "figure.png")
    env = dict(os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=tmp, HOME=tmp, OUT=fig,
               MUJOCO_GL=os.environ.get("MUJOCO_GL", "osmesa"))
    try:
        p = subprocess.run([sys.executable, "script.py"], cwd=tmp, env=env,
                           capture_output=True, text=True, timeout=900)
        stdout, stderr, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, rc = "", "timed out after 900s", 1

    r["checks"]["script_runs"] = rc == 0 and bool(stdout.strip()) and os.path.exists(fig)
    # Imported however it is spelled — "import mujoco", "from mujoco import",
    # "import os, mujoco" — and actually integrated, not just used to write XML.
    r["checks"]["mujoco_stepped"] = bool(re.search(r"^\s*(?:import|from)\b.*\bmujoco\b", source, re.M)) and \
        bool(re.search(r"\bmj_step\b|\brollout\b", source))

    xml = os.path.join(tmp, "model.xml")
    m = None
    if os.path.exists(xml):
        try:
            m = mujoco.MjModel.from_xml_path(xml)
        except Exception as e:
            r["error"] = f"model.xml would not load: {e}"
    elif rc == 0:
        r["error"] = "the script left no model.xml beside itself"
    r["checks"]["mjcf_loads"] = m is not None

    beans = bean_bodies(m) if m is not None else []
    r["checks"][f"{N_BEANS}_free_beans"] = len(beans) == N_BEANS
    r["bean_bodies"] = len(beans)

    def pair_of_ellipsoids(b):
        g0 = m.body_geomadr[b]
        kinds = [m.geom_type[g] for g in range(g0, g0 + m.body_geomnum[b])]
        return kinds.count(ELLIPSOID) >= 2

    r["checks"]["beans_are_ellipsoid_pairs"] = bool(beans) and all(pair_of_ellipsoids(b) for b in beans)

    # 2026-10-10: gravity="0 0 0" left every bean where it started and still
    # passed. Nothing leaves a hopper without it.
    r["checks"]["gravity_down"] = m is not None and bool(m.opt.gravity[2] < -1.0)

    try:
        opened, enclosed = probe(m, beans) if beans else (False, False)
    except Exception as e:  # a probe that cannot run is not a pass
        opened = enclosed = False
        r.setdefault("error", f"the interior probe failed: {e}")
    r["checks"]["hopper_interior_open"] = opened
    r["checks"]["beans_start_inside_walls"] = enclosed

    if not r["checks"]["script_runs"]:
        # Said first: a script that died explains every other failure below it.
        r["error"] = f"the script exited {rc} or drew nothing: {stderr.strip()[-600:]}"
    r["stdout_tail"] = "\n".join(stdout.splitlines()[-30:])

finish(r, out)
