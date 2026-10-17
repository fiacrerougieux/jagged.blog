"""Grinder hopper: 50 roasted coffee beans released through an 18 mm throat.

Units: metres, kilograms, seconds. Each bean = one free body with two
overlapping ellipsoids (a domed upper ellipsoid and a flatter lower one whose
bottom is nearly planar -> one flat face, one domed face).
The hopper is a 32-facet cone (half-angle 30 deg, steeper than the wall
friction angle so beans can flow). A kinematic (mocap) sliding gate under the
throat opens between t = 1.0 s and 1.3 s.
"""
import os
import numpy as np
import mujoco
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.gridspec import GridSpec

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT", os.path.join(HERE, "figure.png"))

# ---------------- parameters ----------------
N_BEANS = 50
SEED = 7
# bean size (semi-axes, m): dome ellipsoid and flat-base ellipsoid
DOME_SEMI = (0.0053, 0.0037, 0.0032)
DOME_POS = (0.0, 0.0, 0.0016)
BASE_SEMI = (0.0050, 0.0036, 0.0014)
BASE_POS = (0.0, 0.0, -0.0008)
BEAN_MASS = 1.2e-4                  # kg (0.12 g) per bean
BEAN_FRICTION = "0.1 0.005 0.0001"  # bean-bean / bean-gate / bean-tray
WALL_FRICTION = "0.1 0.005 0.0001"  # bean-hopper wall
BEAN_BOUND_R = 0.0058               # rough bounding radius for spawning
MIN_SPAWN_DIST = 0.013

# hopper geometry
R_T = 0.009                 # throat radius (18 mm diameter)
H = 0.10                    # hopper height above throat
HALF_ANG = np.deg2rad(30)   # cone half-angle from vertical
N_FACET = 32
WALL_T = 0.002
R_MID = R_T + 0.5 * H * np.tan(HALF_ANG)

# gate
GATE_OPEN_T = 1.0
GATE_DUR = 0.3
GATE_TRAVEL = 0.05
GATE_HALF = (0.02, 0.03, 0.0025)
GATE_Z = -0.0025            # gate top sits on the throat plane z = 0
TRAY_Z = -0.14

# simulation
T_END = 5.0
DT = 5e-4                   # 0.5 ms
ITER = 100
REC_EVERY = 20              # record every 10 ms
SNAP_T = [0.0, 1.0, 2.0, 5.0]
DIAG_T = 1.5

# ---------------- geometry helpers ----------------
def cone_radius(z):
    return R_T + z * np.tan(HALF_ANG)


def bean_xml(i, pos, quat):
    dm = BEAN_MASS / 2
    return f'''
    <body name="bean{i}" pos="{pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}" quat="{quat[0]:.6f} {quat[1]:.6f} {quat[2]:.6f} {quat[3]:.6f}">
      <freejoint name="bean{i}_free"/>
      <geom name="bean{i}_dome" type="ellipsoid" size="{DOME_SEMI[0]} {DOME_SEMI[1]} {DOME_SEMI[2]}"
            pos="{DOME_POS[0]} {DOME_POS[1]} {DOME_POS[2]}" mass="{dm:.6e}" friction="{BEAN_FRICTION}" rgba="0.45 0.27 0.14 1"/>
      <geom name="bean{i}_base" type="ellipsoid" size="{BASE_SEMI[0]} {BASE_SEMI[1]} {BASE_SEMI[2]}"
            pos="{BASE_POS[0]} {BASE_POS[1]} {BASE_POS[2]}" mass="{dm:.6e}" friction="{BEAN_FRICTION}" rgba="0.45 0.27 0.14 1"/>
    </body>'''


def wall_xml():
    sa, ca = np.sin(HALF_ANG), np.cos(HALF_ANG)
    L = H / ca                                  # slant length
    lines = []
    for k in range(N_FACET):
        phi = 2 * np.pi * k / N_FACET
        u = np.array([np.cos(phi), np.sin(phi), 0.0])
        ez = np.array([0.0, 0.0, 1.0])
        d = sa * u + ca * ez                     # generatrix direction (up/out)
        n_out = ca * u - sa * ez                 # outward normal of the cone
        et = np.array([-np.sin(phi), np.cos(phi), 0.0])
        half_w = R_MID * np.tan(np.pi / N_FACET) * 1.2 + 0.0005
        center = R_MID * u + 0.5 * H * ez + n_out * WALL_T / 2
        M = np.column_stack([et, n_out, -d])     # det = +1
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, M.flatten())
        lines.append(
            f'<geom name="wall{k}" type="box" size="{half_w:.6f} {WALL_T/2:.6f} {L/2:.6f}" '
            f'pos="{center[0]:.6f} {center[1]:.6f} {center[2]:.6f}" '
            f'quat="{q[0]:.6f} {q[1]:.6f} {q[2]:.6f} {q[3]:.6f}" friction="{WALL_FRICTION}" rgba="0.6 0.7 0.8 0.35"/>')
    return "\n    ".join(lines)


def spawn_positions(rng):
    pts = []
    while len(pts) < N_BEANS:
        z = rng.uniform(0.015, 0.085)
        rmax = cone_radius(z) - BEAN_BOUND_R
        r = rmax * np.sqrt(rng.uniform())
        a = rng.uniform(0, 2 * np.pi)
        p = np.array([r * np.cos(a), r * np.sin(a), z])
        if all(np.linalg.norm(p - q) >= MIN_SPAWN_DIST for q in pts):
            pts.append(p)
    return pts


def build_xml(rng):
    pts = spawn_positions(rng)
    beans = []
    for i, p in enumerate(pts):
        q = rng.normal(size=4)
        q /= np.linalg.norm(q)
        beans.append(bean_xml(i, p, q))
    xml = f'''<mujoco model="grinder_hopper">
  <option timestep="{DT}" integrator="Euler" iterations="{ITER}" tolerance="1e-10"
          solver="Newton" cone="elliptic" impratio="10" gravity="0 0 -9.81"/>
  <default>
    <geom condim="3" solref="0.002 1" solimp="0.95 0.99 0.001"/>
  </default>
  <worldbody>
    <light pos="0 0 0.5" dir="0 0 -1"/>
    <!-- hopper: 32 inclined facets forming a cone narrowing to the throat -->
    {wall_xml()}
    <!-- tray -->
    <geom name="tray" type="box" size="0.4 0.4 0.005" pos="0 0 {TRAY_Z}" friction="0.4 0.005 0.0001" rgba="0.8 0.8 0.75 1"/>
    <!-- sliding gate, kinematically driven (mocap) -->
    <body name="gate" mocap="true" pos="0 0 {GATE_Z}">
      <geom name="gate" type="box" size="{GATE_HALF[0]} {GATE_HALF[1]} {GATE_HALF[2]}" friction="{BEAN_FRICTION}" rgba="0.3 0.3 0.35 1"/>
    </body>
    {''.join(beans)}
  </worldbody>
</mujoco>
'''
    return xml


# ---------------- simulation ----------------
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def main():
    rng = np.random.default_rng(SEED)
    xml = build_xml(rng)
    xml_path = os.path.join(HERE, "model.xml")
    with open(xml_path, "w") as f:
        f.write(xml)

    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    mocap_id = m.body_mocapid[m.body("gate").id]
    wall_ids = {m.geom(f"wall{k}").id for k in range(N_FACET)}
    bean_body = [m.body(f"bean{i}").id for i in range(N_BEANS)]
    bean_geoms = {}
    for g in range(m.ngeom):
        name = m.geom(g).name
        if name.startswith("bean"):
            bean_geoms[g] = int(name[4:name.index("_")])

    def bean_states():
        return d.xpos[bean_body].copy(), d.xquat[bean_body].copy()

    def set_gate(t):
        x = GATE_TRAVEL * smoothstep((t - GATE_OPEN_T) / GATE_DUR)
        d.mocap_pos[mocap_id] = [x, 0.0, GATE_Z]

    passed = np.zeros(N_BEANS, bool)
    cross_t, cross_id = [], []
    max_pen = 0.0
    max_pen_t = 0.0
    left = {}
    rec_t, rec_cum, rec_thr = [], [], []
    snaps = {}
    diag = None

    mujoco.mj_forward(m, d)
    set_gate(0.0)
    n_steps = int(round(T_END / DT))

    def record(t):
        nonlocal_pos = d.xpos[bean_body]
        rec_t.append(t)
        rec_cum.append(int(passed.sum()))
        r = np.hypot(nonlocal_pos[:, 0], nonlocal_pos[:, 1])
        thr = (np.abs(nonlocal_pos[:, 2]) < 0.01) & (r < R_T)
        rec_thr.append(int(thr.sum()))

    record(0.0)
    snaps[0.0] = bean_states()
    for step in range(1, n_steps + 1):
        t_prev = d.time
        set_gate(t_prev)
        mujoco.mj_step(m, d)
        t = d.time

        # wall penetration from current contacts
        for c in range(d.ncon):
            con = d.contact[c]
            if con.geom1 in wall_ids or con.geom2 in wall_ids:
                other = con.geom2 if con.geom1 in wall_ids else con.geom1
                if other in bean_geoms:
                    pen = -con.dist
                    if pen > max_pen:
                        max_pen, max_pen_t = pen, t

        # passed-through detection
        pos = d.xpos[bean_body]
        newly = (~passed) & (pos[:, 2] < 0.0) & (np.hypot(pos[:, 0], pos[:, 1]) < R_T)
        for i in np.where(newly)[0]:
            cross_t.append(t)
            cross_id.append(i)
        passed |= newly

        # bean left the model?
        out = (np.abs(pos[:, 0]) > 0.35) | (np.abs(pos[:, 1]) > 0.35) | (pos[:, 2] < -0.3) | (pos[:, 2] > 0.4)
        for i in np.where(out)[0]:
            if i not in left:
                left[i] = t

        if diag is None and t >= DIAG_T - 1e-9:
            # contact forces at the diagnostic time
            cps, fvec, fmag = [], [], []
            f6 = np.zeros(6)
            for c in range(d.ncon):
                con = d.contact[c]
                mujoco.mj_contactForce(m, d, c, f6)
                n = con.frame[0:3]
                t1 = con.frame[3:6]
                t2 = con.frame[6:9]
                fv = f6[0] * n + f6[1] * t1 + f6[2] * t2
                cps.append(con.pos.copy())
                fvec.append(fv)
                fmag.append(abs(f6[0]))
            diag = dict(t=t, pos=pos.copy(), quat=d.xquat[bean_body].copy(),
                        cp=np.array(cps).reshape(-1, 3), fv=np.array(fvec).reshape(-1, 3),
                        fn=np.array(fmag))

        if step % REC_EVERY == 0:
            record(t)
        for ts in SNAP_T:
            if ts not in snaps and abs(t - ts) < 0.5 * DT:
                snaps[ts] = bean_states()

    # ---------------- report ----------------
    print(f"model written: {xml_path}")
    print(f"max penetration into hopper walls: {max_pen*1e3:.3f} mm (at t={max_pen_t:.4f} s)")
    print("count through throat (cumulative beans below throat plane) at drawn times:")
    rt = np.array(rec_t)
    rc = np.array(rec_cum)
    rth = np.array(rec_thr)
    for ts in SNAP_T:
        k = int(np.argmin(np.abs(rt - ts)))
        print(f"  t={ts:.1f} s: passed={rc[k]:3d}  in throat zone now={rth[k]:3d}")
    print(f"total beans through throat by t=5 s: {int(passed.sum())} / {N_BEANS}")
    if left:
        print("beans that left the model:")
        for i, tl in left.items():
            print(f"  bean{i} at t={tl:.3f} s")
    else:
        print("beans that left the model: none")

    # ---------------- figure ----------------
    fig = plt.figure(figsize=(18, 10))
    gs = GridSpec(2, 4, figure=fig, height_ratios=[1, 1.1], hspace=0.3, wspace=0.25)

    def draw_hopper(ax, title, bstate, gate_x, cps=None, fv=None):
        ax.set_title(title, fontsize=10)
        zb = -0.16
        ax.plot([-cone_radius(H), -R_T], [H, 0], "k-", lw=2)
        ax.plot([R_T, cone_radius(H)], [0, H], "k-", lw=2)
        ax.plot([-cone_radius(H), -cone_radius(H)], [H, H + 0.01], "k-", lw=2)
        ax.plot([cone_radius(H), cone_radius(H)], [H, H + 0.01], "k-", lw=2)
        ax.plot([-0.4, 0.4], [TRAY_Z, TRAY_Z], color="gray", lw=3)
        # gate (plate at z in [-0.005, 0]) as seen in x-z section
        ax.add_patch(plt.Rectangle((gate_x - GATE_HALF[0], -2 * GATE_HALF[2]), 2 * GATE_HALF[0], 2 * GATE_HALF[2],
                                   color="0.3"))
        pos, quat = bstate
        for i in range(N_BEANS):
            R = np.zeros(9)
            mujoco.mju_quat2Mat(R, quat[i])
            R = R.reshape(3, 3)
            col = "tab:brown"
            if pos[i, 2] < 0.0:
                col = "tab:green"
            for semi, off in ((DOME_SEMI, DOME_POS), (BASE_SEMI, BASE_POS)):
                M = R @ np.diag(semi)
                C = (M @ M.T)[np.ix_([0, 2], [0, 2])]
                w, V = np.linalg.eigh(C)
                th = np.linspace(0, 2 * np.pi, 24)
                circ = np.stack([np.cos(th), np.sin(th)]) * np.sqrt(np.maximum(w, 0))[:, None]
                ell = V @ circ
                c = pos[i] + R @ np.array(off)
                ax.add_patch(Polygon(np.column_stack([c[0] + ell[0], c[2] + ell[1]]), closed=True,
                                     fc=col, ec="k", lw=0.3, alpha=0.85))
        ax.set_xlim(-0.08, 0.08)
        ax.set_ylim(-0.17, 0.12)
        ax.set_aspect("equal")
        ax.set_xlabel("x [m]", fontsize=8)
        ax.set_ylabel("z [m]", fontsize=8)
        ax.tick_params(labelsize=7)

    for k, ts in enumerate(SNAP_T):
        ax = fig.add_subplot(gs[0, k])
        gate_x = GATE_TRAVEL * smoothstep((ts - GATE_OPEN_T) / GATE_DUR)
        n_thr = int(np.argmin(np.abs(rt - ts)))
        draw_hopper(ax, f"t = {ts:.0f} s  (through throat: {rc[n_thr]})", snaps[ts], gate_x)

    # diagnostic frame
    axd = fig.add_subplot(gs[1, 0:2])
    gate_x = GATE_TRAVEL * smoothstep((diag["t"] - GATE_OPEN_T) / GATE_DUR)
    draw_hopper(axd, f"Diagnostic frame at t = {diag['t']:.2f} s: beans (x-z projection), "
                     f"contact points (red) and force vectors (blue)", (diag["pos"], diag["quat"]), gate_x)
    if len(diag["cp"]):
        axd.scatter(diag["cp"][:, 0], diag["cp"][:, 2], s=8, c="red", zorder=5)
        fv = diag["fv"]
        mx = np.max(np.linalg.norm(fv, axis=1)) if len(fv) else 1.0
        if mx > 0:
            sc = 0.02 / mx
            axd.quiver(diag["cp"][:, 0], diag["cp"][:, 2], fv[:, 0] * sc, fv[:, 2] * sc,
                       angles="xy", scale_units="xy", scale=1, color="blue", width=0.003, zorder=6)
        axd.text(0.02, -0.165, f"{len(diag['cp'])} contacts; longest force arrow = {mx:.3g} N (drawn 20 mm)",
                 fontsize=8)

    # beans through throat over time
    axc = fig.add_subplot(gs[1, 2:4])
    axc.step(rt, rc, where="post", color="k", lw=2, label="cumulative through throat")
    axc.plot(rt, rth, color="tab:orange", lw=1.2, label="in throat zone now")
    for ts in SNAP_T:
        axc.axvline(ts, color="0.7", ls=":", lw=1)
    axc.axvline(GATE_OPEN_T, color="tab:red", ls="--", lw=1, label="gate opens")
    axc.set_xlabel("time [s]")
    axc.set_ylabel("bean count")
    axc.set_xlim(0, T_END)
    axc.set_ylim(0, N_BEANS + 2)
    axc.set_title("Beans through the 18 mm throat over time", fontsize=10)
    axc.legend(fontsize=8, loc="center right")
    axc.grid(alpha=0.3)

    fig.suptitle(f"Grinder hopper: {N_BEANS} beans, 18 mm throat, gate opens at 1 s  "
                 f"(max wall penetration {max_pen*1e3:.2f} mm)", fontsize=12)
    fig.savefig(OUT, dpi=110, bbox_inches="tight")
    print(f"figure saved to {OUT}")


if __name__ == "__main__":
    main()
