"""Grinder hopper releasing 50 roasted coffee beans through an 18 mm throat.

Units: metres, kilograms, seconds.  z = 0 is the throat plane, +z up.
  * Hopper: 24-facet cone, inner radius 50 mm at z=140 mm narrowing to the
    9 mm throat radius at z=20 mm, then an 18 mm throat tube down to z=0.
  * Gate: kinematic (mocap) plate under the throat; closed until 1 s, then
    slides sideways out of the throat footprint over 0.3 s.
  * Tray: flat plate at z=-100 mm.
  * Bean: one free body = two overlapping ellipsoids. The upper one is the
    domed face; the lower one is offset down and flattened so the bottom is
    a broad, nearly flat face.
"""
import os
import numpy as np
import mujoco
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT", os.path.join(HERE, "figure.png"))

# ---------------- parameters ----------------
N_BEANS = 50
THROAT_R = 0.009                     # 18 mm throat
TOP_Z, TOP_R = 0.140, 0.050
CONE_BOT_Z = 0.020
N_FACETS = 24
WALL_T = 0.002
GATE_T0, GATE_T1, GATE_X_OPEN = 1.0, 1.3, 0.06
GATE_Z = -0.003                      # gate centre height (plate spans z -0.006..0)
TRAY_Z = -0.100
SIM_T = 5.0
DT = 1.0e-4                          # solver / integration timestep
REC_DT = 0.01
BEAN_MASS = 1.3e-4                   # 0.13 g roasted bean
A_DOME = (0.0055, 0.0035, 0.0030)   # semi-axes of domed ellipsoid (m)
A_FLAT = (0.0055, 0.0035, 0.0016)   # semi-axes of flattened ellipsoid (m)
FLAT_OFFSET = -0.0016                # z-centre of flat ellipsoid in bean frame
FRIC_BEAN = "0.4 0.005 0.0001"       # sliding, torsional, rolling
FRIC_WALL = "0.3 0.005 0.0001"
SOLREF = "0.002 1"
SOLIMP = "0.9 0.95 0.001"
SEED = 7
SNAP_TIMES = [0.0, 1.0, 2.0, 5.0]
DIAG_TIME = 2.0


def radius_at(z):
    """Nominal inner hopper radius at height z."""
    if z >= CONE_BOT_Z:
        f = (z - CONE_BOT_Z) / (TOP_Z - CONE_BOT_Z)
        return THROAT_R + f * (TOP_R - THROAT_R)
    return THROAT_R


def quat_from_cols(X, Y, Z):
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.column_stack([X, Y, Z]).reshape(-1))
    return q


def frustum_facets(z0, R0, z1, R1, prefix):
    """Flat facet boxes approximating a frustum; inner faces at the nominal radius."""
    out = []
    dr, dz = R1 - R0, z1 - z0
    L = np.hypot(dr, dz)
    d = np.array([dr, dz]) / L                  # generatrix direction (r, z)
    n = np.array([-d[1], d[0]])                 # outward normal (r, z)
    rm = 0.5 * (R0 + R1) / np.cos(np.pi / N_FACETS)   # facet mid-plane distance
    zm = 0.5 * (z0 + z1)
    half_w = rm * np.sin(np.pi / N_FACETS) * 1.2
    for i in range(N_FACETS):
        th = 2 * np.pi * i / N_FACETS
        ct, st = np.cos(th), np.sin(th)
        X = np.array([d[0] * ct, d[0] * st, d[1]])
        Y = np.array([-st, ct, 0.0])
        Z = np.array([n[0] * ct, n[0] * st, n[1]])
        # facet inner face lies on the mid-plane at distance rm*cos? -> we place the
        # box so that its inner surface is at the nominal apothem radius.
        apo = 0.5 * (R0 + R1)
        centre = np.array([apo * ct, apo * st, zm]) + Z * (WALL_T / 2)
        q = quat_from_cols(X, Y, Z)
        out.append(
            f'<geom name="{prefix}{i}" type="box" size="{L/2+0.0005:.6f} {half_w:.6f} {WALL_T/2:.6f}" '
            f'pos="{centre[0]:.6f} {centre[1]:.6f} {centre[2]:.6f}" '
            f'quat="{q[0]:.6f} {q[1]:.6f} {q[2]:.6f} {q[3]:.6f}" '
            f'friction="{FRIC_WALL}" solref="{SOLREF}" solimp="{SOLIMP}" rgba="0.55 0.6 0.7 1"/>')
    return out


def bean_inertia():
    a, b, c = A_DOME
    return BEAN_MASS * np.array([b * b + c * c, a * a + c * c, a * a + b * b]) / 5.0


def build_xml(pos0, quat0):
    walls = frustum_facets(TOP_Z, TOP_R, CONE_BOT_Z, THROAT_R, "wall_cone")
    walls += frustum_facets(CONE_BOT_Z, THROAT_R, 0.0, THROAT_R, "wall_throat")
    I = bean_inertia()
    beans = []
    for i in range(N_BEANS):
        p, q = pos0[i], quat0[i]
        beans.append(f'''
    <body name="bean{i}" pos="{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}" quat="{q[0]:.6f} {q[1]:.6f} {q[2]:.6f} {q[3]:.6f}">
      <freejoint name="bean{i}_free"/>
      <inertial pos="0 0 0" mass="{BEAN_MASS}" diaginertia="{I[0]:.4e} {I[1]:.4e} {I[2]:.4e}"/>
      <geom name="bean{i}_dome" type="ellipsoid" size="{A_DOME[0]} {A_DOME[1]} {A_DOME[2]}"
            friction="{FRIC_BEAN}" solref="{SOLREF}" solimp="{SOLIMP}" rgba="0.45 0.27 0.15 1"/>
      <geom name="bean{i}_flat" type="ellipsoid" size="{A_FLAT[0]} {A_FLAT[1]} {A_FLAT[2]}"
            pos="0 0 {FLAT_OFFSET}" friction="{FRIC_BEAN}" solref="{SOLREF}" solimp="{SOLIMP}"
            rgba="0.45 0.27 0.15 1"/>
    </body>''')
    return f'''<mujoco model="grinder_hopper">
  <compiler angle="radian"/>
  <option timestep="{DT}" gravity="0 0 -9.81" integrator="Euler" solver="Newton"
          iterations="100" tolerance="1e-8" cone="elliptic" impratio="10"/>
  <default><geom condim="3" margin="0.0"/></default>
  <worldbody>
    <light pos="0 0 0.5" dir="0 0 -1"/>
    <geom name="tray" type="box" size="0.15 0.15 0.004" pos="0 0 {TRAY_Z-0.004:.4f}"
          friction="{FRIC_WALL}" solref="{SOLREF}" solimp="{SOLIMP}" rgba="0.8 0.8 0.8 1"/>
    {''.join(walls)}
    <body name="gate" mocap="true" pos="0 0 {GATE_Z}">
      <geom name="gate_plate" type="box" size="0.014 0.02 0.003" friction="{FRIC_WALL}"
            solref="{SOLREF}" solimp="{SOLIMP}" rgba="0.9 0.3 0.2 1"/>
    </body>
    {''.join(beans)}
  </worldbody>
</mujoco>
'''


def sample_initial(rng):
    """Random non-overlapping bean poses filling the cone above the gate."""
    pos, quat = [], []
    tries = 0
    while len(pos) < N_BEANS:
        tries += 1
        if tries > 500000:
            raise RuntimeError("could not place beans")
        z = rng.uniform(0.025, 0.11)
        R = radius_at(z) - 0.007
        r = R * np.sqrt(rng.uniform())
        th = rng.uniform(0, 2 * np.pi)
        p = np.array([r * np.cos(th), r * np.sin(th), z])
        if all(np.linalg.norm(p - q) > 0.0130 for q in pos):
            pos.append(p)
            qq = rng.normal(size=4)
            quat.append(qq / np.linalg.norm(qq))
    return np.array(pos), np.array(quat)


def gate_x(t):
    if t <= GATE_T0:
        return 0.0
    if t >= GATE_T1:
        return GATE_X_OPEN
    return GATE_X_OPEN * (t - GATE_T0) / (GATE_T1 - GATE_T0)


def surface_points(p, q, n_u=28, n_v=14):
    """World-frame surface samples of both ellipsoids of one bean (pos p, quat q)."""
    R = np.zeros(9)
    mujoco.mju_quat2Mat(R, q)
    R = R.reshape(3, 3)
    u, v = np.meshgrid(np.linspace(0, 2 * np.pi, n_u), np.linspace(0, np.pi, n_v))
    unit = np.stack([np.cos(u) * np.sin(v), np.sin(u) * np.sin(v), np.cos(v)], -1).reshape(-1, 3)
    pts = []
    for a, off in ((A_DOME, np.zeros(3)), (A_FLAT, np.array([0, 0, FLAT_OFFSET]))):
        pts.append((unit * np.array(a) + off) @ R.T + p)
    return np.vstack(pts)


def draw_hopper(ax, gx):
    zz = np.linspace(CONE_BOT_Z, TOP_Z, 50)
    Rz = np.array([radius_at(z) for z in zz])
    ax.plot(Rz, zz, "k-", lw=1.5); ax.plot(-Rz, zz, "k-", lw=1.5)
    ax.plot([-THROAT_R, -THROAT_R], [0, CONE_BOT_Z], "k-", lw=1.5)
    ax.plot([THROAT_R, THROAT_R], [0, CONE_BOT_Z], "k-", lw=1.5)
    ax.plot([-0.15, 0.15], [TRAY_Z, TRAY_Z], color="0.5", lw=3)
    ax.add_patch(plt.Rectangle((gx - 0.014, GATE_Z - 0.003), 0.028, 0.006, color="tab:red", alpha=0.8))
    ax.set_xlim(-0.07, 0.09); ax.set_ylim(TRAY_Z - 0.01, TOP_Z + 0.01)
    ax.set_aspect("equal"); ax.set_xlabel("x [m]"); ax.set_ylabel("z [m]")


def main():
    rng = np.random.default_rng(SEED)
    pos0, quat0 = sample_initial(rng)
    xml = build_xml(pos0, quat0)
    xml_path = os.path.join(HERE, "model.xml")
    with open(xml_path, "w") as f:
        f.write(xml)

    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    mid = m.body("gate").mocapid[0]
    bodies = [m.body(f"bean{i}").id for i in range(N_BEANS)]
    wall_geom = np.array([(mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or "").startswith("wall")
                          for g in range(m.ngeom)])
    bean_of_geom = np.array([b - bodies[0] if b in bodies else -1 for b in m.geom_bodyid])

    n_steps = int(round(SIM_T / DT))
    rec_every = int(round(REC_DT / DT))
    snap_steps = {int(round(t / DT)): t for t in SNAP_TIMES}
    diag_step = int(round(DIAG_TIME / DT))

    passed = np.zeros(N_BEANS, bool)
    left = set()
    max_pen, max_pen_bean = 0.0, -1
    count_t, count_n, rec_xyz = [], [], []
    snaps, diag = {}, None

    for step in range(n_steps + 1):
        t = step * DT
        d.mocap_pos[mid] = [gate_x(t), 0.0, GATE_Z]
        if step % 10 == 0 or step in snap_steps or step == diag_step:
            mujoco.mj_forward(m, d)
        # penetration into hopper walls (negative dist = overlap)
        for k in range(d.ncon):
            c = d.contact[k]
            if wall_geom[c.geom1] or wall_geom[c.geom2]:
                other = c.geom2 if wall_geom[c.geom1] else c.geom1
                if -c.dist > max_pen:
                    max_pen, max_pen_bean = -c.dist, bean_of_geom[other]
        if step % rec_every == 0:
            bp = d.xpos[bodies].copy()
            bq = d.xquat[bodies].copy()
            newly = (~passed) & (bp[:, 2] < GATE_Z)
            passed |= newly
            count_t.append(t); count_n.append(int(passed.sum()))
            rec_xyz.append(bp)
            for i in range(N_BEANS):
                if np.hypot(*bp[i, :2]) > 0.2 or bp[i, 2] < TRAY_Z - 0.1:
                    left.add(i)
        if step in snap_steps:
            snaps[snap_steps[step]] = (d.xpos[bodies].copy(), d.xquat[bodies].copy(), passed.copy())
        if step == diag_step:
            cons = []
            for k in range(d.ncon):
                c = d.contact[k]
                f6 = np.zeros(6)
                mujoco.mj_contactForce(m, d, k, f6)
                cons.append((c.pos.copy(), c.frame[:3].copy(), f6[0], c.dist))
            diag = (t, cons)
        if step == n_steps:
            break
        mujoco.mj_step(m, d)

    # ---------- report ----------
    print(f"model written: {xml_path}")
    print(f"max penetration into hopper walls: {max_pen*1e3:.3f} mm (bean {max_pen_bean})")
    count_t = np.array(count_t); count_n = np.array(count_n)
    for t in SNAP_TIMES:
        idx = int(np.argmin(np.abs(count_t - t)))
        print(f"count through throat at t={t:.0f} s: {count_n[idx]} / {N_BEANS}")
    print("beans that left the model: " + (str(sorted(left)) if left else "none"))
    print(f"lowest bean centre z: {min(r[:,2].min() for r in rec_xyz):.4f} m, tray top at {TRAY_Z:.3f} m")
    print(f"final on tray / below gate: {int(passed.sum())}; still in hopper: {N_BEANS - int(passed.sum())}")

    # ---------- figure ----------
    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.1, 1.0], hspace=0.35, wspace=0.3)
    colors = plt.cm.tab20(np.linspace(0, 1, N_BEANS))

    for col, t in enumerate(SNAP_TIMES):
        ax = fig.add_subplot(gs[0, col])
        xyz, quat, pa = snaps[t]
        draw_hopper(ax, gate_x(t))
        for i in range(N_BEANS):
            pts = surface_points(xyz[i], quat[i], n_u=14, n_v=8)
            ax.scatter(pts[:, 0], pts[:, 2], s=0.8, color=colors[i])
        ax.set_title(f"t = {t:.0f} s   through throat: {int(pa.sum())}")

    # diagnostic frame at DIAG_TIME: contacts and normal-force vectors
    ax = fig.add_subplot(gs[1, 0:2])
    t_d, cons = diag
    draw_hopper(ax, gate_x(t_d))
    xyz_d = rec_xyz[int(round(t_d / REC_DT))]
    quat_d = snaps[DIAG_TIME][1]
    for i in range(N_BEANS):
        pts = surface_points(xyz_d[i], quat_d[i], n_u=14, n_v=8)
        ax.scatter(pts[:, 0], pts[:, 2], s=0.3, color="0.75")
    fmax = max([c[2] for c in cons] + [1e-12])
    scale = 0.015 / fmax
    for pos, nrm, fn, dist in cons:
        ax.scatter(pos[0], pos[2], s=10, color="k", zorder=5)
        if fn > 0:
            ax.arrow(pos[0], pos[2], nrm[0] * fn * scale, nrm[2] * fn * scale,
                     color="tab:blue", width=0.0001, head_width=0.0012,
                     length_includes_head=True, zorder=6)
    ax.set_title(f"diagnostic t = {t_d:.1f} s: {len(cons)} contacts "
                 f"(dots = contact points, blue = normal force, max {fmax:.2f} N)")

    ax = fig.add_subplot(gs[1, 2])
    ax.step(count_t, count_n, where="post", color="tab:green")
    for t in SNAP_TIMES:
        ax.axvline(t, color="0.7", ls=":")
    ax.axvline(GATE_T0, color="tab:red", ls="--", label="gate opens")
    ax.set_xlabel("time [s]"); ax.set_ylabel("beans through throat")
    ax.set_ylim(0, N_BEANS + 2); ax.legend(); ax.set_title("throat count vs time")

    ax = fig.add_subplot(gs[1, 3])
    for i in range(N_BEANS):
        ts = count_t
        zs = np.array([r[i, 2] for r in rec_xyz])
        xs = np.array([r[i, 0] for r in rec_xyz])
        ax.plot(ts, zs, color=colors[i], lw=0.6)
    ax.axhline(GATE_Z, color="tab:red", ls="--", lw=0.8)
    ax.set_xlabel("time [s]"); ax.set_ylabel("bean centre z [m]")
    ax.set_title("bean height vs time (all beans)")

    fig.suptitle(f"Grinder hopper: {N_BEANS} beans, 18 mm throat, gate opens at 1 s; "
                 f"max wall penetration {max_pen*1e3:.2f} mm")
    fig.savefig(OUT, dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    main()
