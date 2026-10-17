"""Grinder hopper: hollow cone of convex panels, 18 mm throat, sliding gate, 50 two-ellipsoid beans."""
import os
import numpy as np
import mujoco
import matplotlib.pyplot as plt

# Declared parameters
BEAN_HALF = (0.0050, 0.0035, 0.0025)   # dome ellipsoid semi-axes, m
FLAT_HALF = (0.0048, 0.0034, 0.0010)   # flat ellipsoid, offset down: the flat face
BEAN_MASS = 0.00015                    # kg, 0.15 g
FRICTION = (0.5, 0.005, 0.0001)
TIMESTEP = 0.0005
N_BEANS = 50
THROAT_R = 0.009                       # 18 mm throat
Z_THROAT_BOT, Z_THROAT_TOP, Z_TOP, R_TOP = 0.090, 0.100, 0.160, 0.050
GATE_OPEN_T = 1.0
NPANEL = 16

def panel_ring(name, r0, z0, r1, z1, n, thick=0.0015):
    out = []
    zc, rc = (z0 + z1) / 2, (r0 + r1) / 2
    slant = np.hypot(r1 - r0, z1 - z0)
    tilt = np.arctan2(r1 - r0, z1 - z0)
    width = 2 * max(r0, r1) * np.tan(np.pi / n) * 1.05
    for k in range(n):
        a = 2 * np.pi * k / n
        # q = Rz(a) * Ry(tilt): tilt the panel so its top leans out, then spin it round
        ca, sa, ct, st = np.cos(a / 2), np.sin(a / 2), np.cos(tilt / 2), np.sin(tilt / 2)
        qw, qx, qy, qz = ca * ct, -sa * st, ca * st, sa * ct
        cx, cy = (rc + thick) * np.cos(a), (rc + thick) * np.sin(a)
        # local frame: z along the slant, x outward normal
        out.append(f'<geom name="{name}{k}" type="box" size="{thick} {width/2} {slant/2}" '
                   f'pos="{cx:.5f} {cy:.5f} {zc:.5f}" quat="{qw:.6f} {qx:.6f} {qy:.6f} {qz:.6f}" '
                   f'rgba="0.6 0.6 0.7 0.35" class="wall"/>')
    return "\n".join(out)


def funnel_mesh(n=32, thick=0.0015):
    verts, faces = [], []
    rings = [(THROAT_R, Z_THROAT_BOT), (THROAT_R, Z_THROAT_TOP), (R_TOP, Z_TOP)]
    for off in (0.0, thick):
        for r, z in rings:
            for k in range(n):
                a = 2 * np.pi * k / n
                verts.append(((r + off) * np.cos(a), (r + off) * np.sin(a), z))
    R = len(rings)
    def vid(layer, ring, k):
        return layer * R * n + ring * n + (k % n)
    for layer in (0, 1):
        for ring in range(R - 1):
            for k in range(n):
                a, b, c, e = vid(layer, ring, k), vid(layer, ring, k + 1), vid(layer, ring + 1, k + 1), vid(layer, ring + 1, k)
                faces += [(a, b, c), (a, c, e)] if layer else [(a, c, b), (a, e, c)]
    for ring in (0, R - 1):
        for k in range(n):
            a, b, c, e = vid(0, ring, k), vid(0, ring, k + 1), vid(1, ring, k + 1), vid(1, ring, k)
            faces += [(a, b, c), (a, c, e)]
    vs = " ".join(f"{x:.5f} {y:.5f} {z:.5f}" for x, y, z in verts)
    fs = " ".join(f"{a} {b} {c}" for a, b, c in faces)
    return vs, fs

VS, FS = funnel_mesh()
walls = '<geom name="cone" type="mesh" mesh="funnel" rgba="0.6 0.6 0.7 0.35" class="wall"/>'
_unused = panel_ring("cone", THROAT_R, Z_THROAT_TOP, R_TOP, Z_TOP, NPANEL) + "\n" + \
        panel_ring("throat", THROAT_R, Z_THROAT_BOT, THROAT_R, Z_THROAT_TOP, 12)

rng = np.random.default_rng(1)
beans, placed, z = [], 0, Z_TOP + 0.010
while placed < N_BEANS:
    rz = 0.03
    for x in np.arange(-rz, rz + 1e-9, 0.011):
        for y in np.arange(-rz, rz + 1e-9, 0.011):
            if x * x + y * y <= rz * rz and placed < N_BEANS:
                q = rng.normal(size=4); q /= np.linalg.norm(q)
                beans.append(f'''<body name="bean{placed}" pos="{x:.4f} {y:.4f} {z:.4f}" quat="{q[0]:.4f} {q[1]:.4f} {q[2]:.4f} {q[3]:.4f}">
  <freejoint/>
  <geom type="ellipsoid" size="{BEAN_HALF[0]} {BEAN_HALF[1]} {BEAN_HALF[2]}" mass="{BEAN_MASS*0.7}" class="bean"/>
  <geom type="ellipsoid" size="{FLAT_HALF[0]} {FLAT_HALF[1]} {FLAT_HALF[2]}" pos="0 0 -0.0014" mass="{BEAN_MASS*0.3}" class="bean"/>
</body>''')
                placed += 1
    z += 0.009

XML = f'''<mujoco model="grinder_hopper">
  <option timestep="{TIMESTEP}" gravity="0 0 -9.81" solver="Newton" iterations="50" cone="elliptic"/>
  <default>
    <default class="wall"><geom friction="{FRICTION[0]} {FRICTION[1]} {FRICTION[2]}" solref="0.002 1"/></default>
    <default class="bean"><geom friction="{FRICTION[0]} {FRICTION[1]} {FRICTION[2]}" rgba="0.35 0.2 0.1 1" solref="0.002 1" condim="4"/></default>
  </default>
  <asset><mesh name="funnel" vertex="{VS}" face="{FS}"/></asset>
  <worldbody>
    <geom name="floor" type="plane" size="0.3 0.3 0.01" rgba="0.9 0.9 0.9 1"/>
    <geom name="tray" type="box" size="0.08 0.08 0.004" pos="0 0 0.02" rgba="0.3 0.3 0.3 1" class="wall"/>
    {walls}
    <body name="gate" pos="0 0 {Z_THROAT_BOT - 0.002}">
      <joint name="gate_slide" type="slide" axis="1 0 0" damping="5"/>
      <geom name="gate" type="box" size="0.016 0.016 0.0015" mass="0.02" rgba="0.8 0.2 0.2 1" class="wall"/>
    </body>
    {"".join(beans)}
  </worldbody>
  <actuator><position name="gate_act" joint="gate_slide" kp="200" ctrlrange="0 0.05"/></actuator>
</mujoco>'''

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "model.xml"), "w") as f:
    f.write(XML)
m = mujoco.MjModel.from_xml_path(os.path.join(here, "model.xml"))
d = mujoco.MjData(m)
bean_ids = [m.body(f"bean{i}").id for i in range(N_BEANS)]
wall_ids = {g for g in range(m.ngeom) if m.geom_bodyid[g] == 0 and m.geom(g).name.startswith(("cone", "throat"))}

mujoco.mj_forward(m, d)
snap_t = [0.0, 1.0, 2.0, 5.0]
snaps, counts_t, counts, max_pen, left = {}, [], [], 0.0, set()
diag = None
nsteps = int(5.0 / TIMESTEP)
for step in range(nsteps + 1):
    t = step * TIMESTEP
    d.ctrl[0] = 0.045 if t >= GATE_OPEN_T else 0.0
    for c in d.contact[:d.ncon]:
        if c.geom1 in wall_ids or c.geom2 in wall_ids:
            max_pen = max(max_pen, -c.dist)
    if step % 20 == 0:
        z = d.xpos[bean_ids, 2]
        counts_t.append(t); counts.append(int((z < Z_THROAT_BOT).sum()))
    for ts in snap_t:
        if abs(t - ts) < TIMESTEP / 2:
            snaps[ts] = d.xpos[bean_ids].copy()
    if abs(t - 0.8) < TIMESTEP / 2:
        diag = []
        f6 = np.zeros(6)
        for i in range(d.ncon):
            c = d.contact[i]
            mujoco.mj_contactForce(m, d, i, f6)
            diag.append((c.pos.copy(), c.frame[:3] * f6[0]))
    for b, p in zip(bean_ids, d.xpos[bean_ids]):
        if np.any(np.abs(p) > 0.5) or p[2] < -0.01:
            left.add(b)
    if step < nsteps:
        mujoco.mj_step(m, d)

print(f"bean semi-axes {BEAN_HALF} m + flat {FLAT_HALF} m, mass {BEAN_MASS*1000:.2f} g, friction {FRICTION}, dt {TIMESTEP}, Newton solver")
print(f"max penetration into hopper walls: {max_pen*1000:.3f} mm")
for ts in snap_t:
    print(f"t={ts:.0f}s through throat: {int((snaps[ts][:, 2] < Z_THROAT_BOT).sum())}")
print("beans that left the model:", sorted(m.body(b).name for b in left) or "none")

fig = plt.figure(figsize=(16, 8))
cone_x = [-R_TOP, -THROAT_R, -THROAT_R, None, THROAT_R, THROAT_R, R_TOP]
cone_z = [Z_TOP, Z_THROAT_TOP, Z_THROAT_BOT, None, Z_THROAT_BOT, Z_THROAT_TOP, Z_TOP]
for k, ts in enumerate(snap_t):
    ax = fig.add_subplot(2, 3, k + 1 if k < 3 else 4)
    ax.plot([-R_TOP, -THROAT_R, -THROAT_R], [Z_TOP, Z_THROAT_TOP, Z_THROAT_BOT], "k")
    ax.plot([R_TOP, THROAT_R, THROAT_R], [Z_TOP, Z_THROAT_TOP, Z_THROAT_BOT], "k")
    ax.scatter(snaps[ts][:, 0], snaps[ts][:, 2], s=12, c="saddlebrown")
    ax.set_title(f"t = {ts:.0f} s"); ax.set_aspect("equal"); ax.set_ylim(0, 0.18)
ax = fig.add_subplot(2, 3, 5)
for p, fv in diag or []:
    ax.plot(p[0], p[2], "r.", ms=3)
    ax.arrow(p[0], p[2], fv[0] * 0.01, fv[2] * 0.01, color="b", width=0.0002)
ax.plot([-R_TOP, -THROAT_R, -THROAT_R], [Z_TOP, Z_THROAT_TOP, Z_THROAT_BOT], "k")
ax.plot([R_TOP, THROAT_R, THROAT_R], [Z_TOP, Z_THROAT_TOP, Z_THROAT_BOT], "k")
ax.set_title("contacts and forces, t = 0.8 s"); ax.set_aspect("equal")
ax = fig.add_subplot(2, 3, 6)
ax.plot(counts_t, counts); ax.axvline(GATE_OPEN_T, ls="--"); ax.set_xlabel("s"); ax.set_ylabel("beans through throat")
fig.savefig(os.environ.get("OUT", "hopper.png"), dpi=80)
