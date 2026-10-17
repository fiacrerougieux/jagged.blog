"""Grinder hopper: 50 roasted coffee beans discharge through an 18 mm throat.

Units: metres, kilograms, seconds.  Z is up.  The hopper is a 28-facet cone
narrowing to the throat at z = 0; a sliding gate just under the throat is
opened at t = 1 s; beans fall onto a finite tray with raised lips.
"""
import os
import numpy as np
import mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT", os.path.join(HERE, "figure.png"))

# ---------------- parameters ----------------
N_BEANS = 50
SEED = 7
T_END = 5.0
DT = 2.0e-4                     # solver timestep
T_OPEN = 1.0                    # gate starts moving
GATE_TRAVEL = 0.08              # gate slides +x by this much
GATE_TIME = 0.25                # time to slide clear

R_THROAT = 0.009                # 18 mm throat diameter
R_TOP = 0.070                   # hopper top radius (open)
H_HOP = 0.300                   # hopper height, throat plane at z = 0
N_FACET = 28
WALL_T = 0.002                  # wall plate thickness
GATE_Z = -0.006
TRAY_Z = -0.134                 # tray floor top surface at z = -0.130

BEAN_MASS = 1.6e-4              # 0.16 g roasted bean
# bean semi-axes (m) of the overall body, used only for the inertia tensor
BEAN_SEMI = np.array([5.3e-3, 3.85e-3, 2.6e-3])
# flat face: flattened ellipsoid; domed face: taller ellipsoid on top
FLAT_R = (5.4e-3, 4.0e-3, 1.6e-3)
FLAT_C = (0.0, 0.0, -1.0e-3)
DOME_R = (5.2e-3, 3.7e-3, 2.6e-3)
DOME_C = (0.0, 0.0, 0.0)
BEAN_FRICTION = "0.5 0.005 0.0001"
WALL_FRICTION = "0.3 0.005 0.0001"

# ---------------- geometry helpers ----------------
def hop_r(z):
    """Inner radius of the hopper cone at height z."""
    return R_THROAT + (R_TOP - R_THROAT) * np.clip(z, 0, H_HOP) / H_HOP


def wall_plates():
    """Return list of (name, pos, quat, halfsize) for the cone facets."""
    dr = R_TOP - R_THROAT
    dz = H_HOP
    L = np.hypot(dr, dz)
    plates = []
    rmid = 0.5 * (R_THROAT + R_TOP)
    w = np.pi * rmid / N_FACET * 1.12  # half chord with a little overlap
    for i in range(N_FACET):
        th = 2 * np.pi * i / N_FACET
        er = np.array([np.cos(th), np.sin(th), 0.0])
        ez = np.array([0.0, 0.0, 1.0])
        gu = (dr * er + dz * ez) / L            # along the generatrix
        n = (dz * er - dr * ez) / L             # outward normal
        yv = np.cross(n, gu)                    # tangential
        ctr = 0.5 * (R_THROAT + R_TOP) * er + 0.5 * H_HOP * ez + 0.5 * WALL_T * n
        R = np.column_stack([gu, yv, n])
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, R.flatten())
        plates.append((f"wall{i}", ctr, q, (0.5 * L, w, 0.5 * WALL_T)))
    return plates


def random_quat(rng):
    q = rng.normal(size=4)
    return q / np.linalg.norm(q)


def fmt(v):
    return " ".join(f"{x:.6g}" for x in v)


def build_xml(bean_pos, bean_quat):
    m_i = BEAN_MASS
    a, b, c = BEAN_SEMI
    I = m_i / 5.0 * np.array([b * b + c * c, a * a + c * c, a * a + b * b])
    parts = []
    for i in range(N_BEANS):
        parts.append(f'''    <body name="bean{i}" pos="{fmt(bean_pos[i])}" quat="{fmt(bean_quat[i])}">
      <freejoint name="bean{i}_free"/>
      <inertial pos="0 0 0" mass="{m_i:.6g}" diaginertia="{fmt(I)}"/>
      <geom name="bean{i}_flat" type="ellipsoid" size="{fmt(FLAT_R)}" pos="{fmt(FLAT_C)}" class="bean"/>
      <geom name="bean{i}_dome" type="ellipsoid" size="{fmt(DOME_R)}" pos="{fmt(DOME_C)}" class="bean"/>
    </body>''')
    beans_xml = "\n".join(parts)

    walls = []
    for name, ctr, q, hs in wall_plates():
        walls.append(f'    <body name="{name}_body" pos="{fmt(ctr)}" quat="{fmt(q)}">'
                     f'<geom name="{name}" type="box" size="{fmt(hs)}" class="wall"/></body>')
    walls_xml = "\n".join(walls)

    tray_lip = 0.015
    tx = 0.12
    tray_xml = f'''    <body name="tray" pos="0 0 {TRAY_Z}">
      <geom name="tray_floor" type="box" size="{tx} {tx} 0.004" pos="0 0 0.004" class="wall"/>
      <geom name="tray_lipx1" type="box" size="0.004 {tx} {tray_lip/2}" pos="{tx} 0 {0.008+tray_lip/2}" class="wall"/>
      <geom name="tray_lipx0" type="box" size="0.004 {tx} {tray_lip/2}" pos="{-tx} 0 {0.008+tray_lip/2}" class="wall"/>
      <geom name="tray_lipy1" type="box" size="{tx} 0.004 {tray_lip/2}" pos="0 {tx} {0.008+tray_lip/2}" class="wall"/>
      <geom name="tray_lipy0" type="box" size="{tx} 0.004 {tray_lip/2}" pos="0 {-tx} {0.008+tray_lip/2}" class="wall"/>
    </body>'''

    xml = f'''<mujoco model="grinder_hopper">
  <option timestep="{DT}" gravity="0 0 -9.81" integrator="Euler" solver="Newton"
          iterations="100" tolerance="1e-10" cone="elliptic" impratio="5"/>
  <size nconmax="5000" njmax="20000"/>
  <default>
    <geom condim="3" solref="0.002 1" solimp="0.9 0.95 0.001"/>
    <default class="bean"><geom friction="{BEAN_FRICTION}" rgba="0.36 0.2 0.1 1"/></default>
    <default class="wall"><geom friction="{WALL_FRICTION}" rgba="0.7 0.72 0.75 1"/></default>
  </default>
  <worldbody>
{walls_xml}
{tray_xml}
    <body name="gate" mocap="true" pos="0 0 {GATE_Z}">
      <geom name="gate" type="box" size="0.03 0.03 0.0025" class="wall" rgba="0.8 0.3 0.2 1"/>
    </body>
{beans_xml}
  </worldbody>
</mujoco>
'''
    return xml


def place_beans(rng):
    """Random sequential placement of beans in the upper hopper body."""
    pos, quats = [], []
    tries = 0
    while len(pos) < N_BEANS:
        tries += 1
        if tries > 200000:
            raise RuntimeError("could not place beans")
        z = rng.uniform(0.02, 0.15)
        rho = rng.uniform(0, hop_r(z) - 0.008)
        ph = rng.uniform(0, 2 * np.pi)
        p = np.array([rho * np.cos(ph), rho * np.sin(ph), z])
        if any(np.linalg.norm(p - q) < 0.0118 for q in pos):
            continue
        pos.append(p)
        quats.append(random_quat(rng))
    return np.array(pos), np.array(quats)


# ---------------- simulation ----------------
def gate_x(t):
    s = np.clip((t - T_OPEN) / GATE_TIME, 0.0, 1.0)
    return GATE_TRAVEL * s * s * (3 - 2 * s)


def main():
    rng = np.random.default_rng(SEED)
    bean_pos, bean_quat = place_beans(rng)
    xml = build_xml(bean_pos, bean_quat)
    xml_path = os.path.join(HERE, "model.xml")
    with open(xml_path, "w") as f:
        f.write(xml)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)

    gate_mocap = model.body("gate").mocapid[0]
    bean_bodies = [model.body(f"bean{i}").id for i in range(N_BEANS)]
    bean_geom = np.zeros(model.ngeom, bool)
    wall_geom = np.zeros(model.ngeom, bool)
    for g in range(model.ngeom):
        nm = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
        if nm.startswith("bean"):
            bean_geom[g] = True
        if nm.startswith("wall"):
            wall_geom[g] = True
    bean_ids_of_geom = np.full(model.ngeom, -1)
    for i in range(N_BEANS):
        for suf in ("flat", "dome"):
            bean_ids_of_geom[model.geom(f"bean{i}_{suf}").id] = i
    # body-level ids for beans for quick position lookup
    bean_body_ids = np.array(bean_bodies)

    mujoco.mj_forward(model, data)
    data.mocap_pos[gate_mocap] = [gate_x(0.0), 0, GATE_Z]

    snap_times = [0.0, 1.0, 2.0, 5.0]
    snap_steps = {int(round(t / DT)): t for t in snap_times}
    snaps = {}
    ts_t, ts_count = [], []
    passed = np.zeros(N_BEANS, bool)
    max_pen = 0.0
    max_pen_bean = -1
    left = set()
    record_every = int(round(0.01 / DT))
    nsteps = int(round(T_END / DT))

    def capture(t):
        contacts = []
        for k in range(data.ncon):
            c = data.contact[k]
            f6 = np.zeros(6)
            mujoco.mj_contactForce(model, data, k, f6)
            contacts.append(dict(pos=c.pos.copy(), normal=c.frame[:3].copy(),
                                 fn=f6[0], dist=c.dist,
                                 kind=("wall" if (wall_geom[c.geom[0]] or wall_geom[c.geom[1]])
                                       else "bean-bean" if (bean_geom[c.geom[0]] and bean_geom[c.geom[1]])
                                       else "tray/gate")
                                 ))
        snaps[t] = dict(
            xpos=data.xpos[bean_body_ids].copy(),
            xmat=data.xmat[bean_body_ids].reshape(-1, 3, 3).copy(),
            gate=gate_x(t),
            contacts=contacts,
            count=int(passed.sum()),
            n_throat=int(np.sum((np.hypot(data.xpos[bean_body_ids, 0], data.xpos[bean_body_ids, 1]) < R_THROAT)
                                & (data.xpos[bean_body_ids, 2] > -0.012) & (data.xpos[bean_body_ids, 2] < 0.01))),
        )

    def update_stats():
        nonlocal max_pen, max_pen_bean
        cs = data.contact
        if data.ncon:
            g1 = cs.geom[:, 0]
            g2 = cs.geom[:, 1]
            sel = ((wall_geom[g1] & bean_geom[g2]) | (wall_geom[g2] & bean_geom[g1]))
            if np.any(sel):
                d = -cs.dist[sel]
                gb = np.where(bean_geom[g1[sel]], g1[sel], g2[sel])
                j = np.argmax(d)
                if d[j] > max_pen:
                    max_pen = float(d[j])
                    max_pen_bean = int(bean_ids_of_geom[gb[j]])
        z = data.xpos[bean_body_ids, 2]
        newly = (z < -0.012) & (~passed)
        passed[newly] = True
        xy = data.xpos[bean_body_ids]
        out = (np.abs(xy[:, 0]) > 0.2) | (np.abs(xy[:, 1]) > 0.2) | (xy[:, 2] < -0.25) | (xy[:, 2] > 0.4)
        for i in np.where(out)[0]:
            left.add(int(i))

    capture(0.0)
    update_stats()
    for step in range(1, nsteps + 1):
        t_now = step * DT
        data.mocap_pos[gate_mocap] = [gate_x(t_now - DT), 0, GATE_Z]
        mujoco.mj_step(model, data)
        update_stats()
        if step in snap_steps:
            capture(snap_steps[step])
        if step % record_every == 0:
            ts_t.append(step * DT)
            ts_count.append(int(passed.sum()))

    # report
    print(f"Model written to {xml_path}")
    print(f"Maximum penetration into hopper walls: {max_pen*1e3:.3f} mm (bean {max_pen_bean})")
    for t in snap_times:
        s = snaps[t]
        print(f"t={t:.1f} s: cumulative beans through throat = {s['count']}, "
              f"beans in throat zone now = {s['n_throat']}, gate x = {s['gate']*1e3:.1f} mm")
    print(f"Beans through throat at end: {int(passed.sum())} / {N_BEANS}")
    if left:
        print(f"Beans that left the model: {sorted(left)}")
    else:
        print("Beans that left the model: none")

    plot(snaps, snap_times, ts_t, ts_count, model)


# ---------------- plotting ----------------
def ellipse_proj(center, M, n=60):
    """Projection (x,z) of an ellipsoid with world matrix M = R*diag(radii)."""
    P = np.array([[1, 0, 0], [0, 0, 1.0]])
    A = P @ M
    U, S, _ = np.linalg.svd(A)
    th = np.linspace(0, 2 * np.pi, n)
    circ = np.vstack([np.cos(th), np.sin(th)]) * S[:, None]
    pts = (U @ circ).T + np.array([center[0], center[2]])
    return pts


def plot(snaps, snap_times, ts_t, ts_count, model):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 4, height_ratios=[1, 1.15])

    def draw_hopper(ax, t, s, show_beans=True, title=None):
        # walls: profile in x-z plane (y = 0)
        for sx in (-1, 1):
            ax.plot([sx * R_THROAT, sx * R_TOP], [0, H_HOP], color="0.35", lw=2)
        ax.plot([-R_TOP - 0.01, -R_TOP - 0.01], [0, 0], alpha=0)
        ax.plot([-0.1, -R_THROAT], [0, 0], color="0.35", lw=1, alpha=0.5)
        ax.plot([R_THROAT, 0.1], [0, 0], color="0.35", lw=1, alpha=0.5)
        # tray
        ax.plot([-0.12, 0.12], [TRAY_Z + 0.004 * 0, TRAY_Z], color="0.5", lw=0)
        ax.add_patch(Rectangle((-0.12, TRAY_Z - 0.004), 0.24, 0.008, color="0.55"))
        # gate
        gx = s["gate"]
        ax.add_patch(Rectangle((gx - 0.03, GATE_Z - 0.0025), 0.06, 0.005, color="tab:red", alpha=0.8))
        if show_beans:
            for i in range(N_BEANS):
                for rad, c_off in ((FLAT_R, FLAT_C), (DOME_R, DOME_C)):
                    R = s["xmat"][i]
                    ctr = s["xpos"][i] + R @ np.array(c_off)
                    M = R @ np.diag(rad)
                    pts = ellipse_proj(ctr, M)  # (x,z) outline
                    ax.add_patch(Polygon(pts, closed=True, fc="saddlebrown", ec="k", lw=0.3, alpha=0.85))
        ax.set_xlim(-0.09, 0.09)
        ax.set_ylim(-0.15, 0.32)
        ax.set_aspect("equal")
        ax.set_title(title or f"t = {t:g} s   through throat: {s['count']}")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("z [m]")

    for k, t in enumerate(snap_times):
        ax = fig.add_subplot(gs[0, k])
        draw_hopper(ax, t, snaps[t])

    # diagnostic frame at t = 2 s
    s2 = snaps[2.0]
    ax = fig.add_subplot(gs[1, 0:2])
    for i in range(N_BEANS):
        R = s2["xmat"][i]
        for rad, c_off in ((FLAT_R, FLAT_C), (DOME_R, DOME_C)):
            ctr = s2["xpos"][i] + R @ np.array(c_off)
            pts = ellipse_proj(ctr, R @ np.diag(rad))
            ax.add_patch(Polygon(pts, closed=True, fc="0.85", ec="0.5", lw=0.3))
    ax.plot([-R_TOP, -R_THROAT], [H_HOP, 0], color="0.3", lw=2)
    ax.plot([R_TOP, R_THROAT], [H_HOP, 0], color="0.3", lw=2)
    ax.add_patch(Rectangle((s2["gate"] - 0.03, GATE_Z - 0.0025), 0.06, 0.005, color="tab:red", alpha=0.6))
    ax.add_patch(Rectangle((-0.12, TRAY_Z - 0.004), 0.24, 0.008, color="0.55"))
    cons = s2["contacts"]
    if cons:
        P = np.array([c["pos"] for c in cons])
        fn = np.array([c["fn"] for c in cons])
        N = np.array([c["normal"] for c in cons])
        kinds = [c["kind"] for c in cons]
        colmap = {"wall": "tab:blue", "bean-bean": "tab:green", "tray/gate": "tab:purple"}
        cols = [colmap[k] for k in kinds]
        ax.scatter(P[:, 0], P[:, 2], s=10, c=cols, zorder=5)
        fmax = max(np.max(np.abs(fn)), 1e-12)
        L = 0.02
        for p, n_, f, cl in zip(P, N, fn, cols):
            v = n_ * (f / fmax) * L
            ax.arrow(p[0], p[2], v[0], v[2], color=cl, width=0.00012, head_width=0.0016,
                     length_includes_head=True, zorder=6)
    ax.set_xlim(-0.09, 0.09)
    ax.set_ylim(-0.15, 0.32)
    ax.set_aspect("equal")
    ax.set_title(f"Diagnostic at t = 2 s: {len(cons)} contacts "
                 f"(points; normal force arrows, max={max([c['fn'] for c in cons] or [0])*1e3:.2f} mN)\n"
                 "blue=wall, green=bean-bean, purple=tray/gate")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("z [m]")

    # cumulative count vs time
    ax = fig.add_subplot(gs[1, 2:4])
    ax.step(ts_t, ts_count, where="post", color="k")
    for t in snap_times:
        ax.axvline(t, color="0.7", ls="--")
        ax.plot([t], [snaps[t]["count"]], "o", color="tab:red")
        ax.annotate(f"{snaps[t]['count']}", (t, snaps[t]["count"]), xytext=(4, 4),
                    textcoords="offset points")
    ax.set_xlim(0, T_END)
    ax.set_ylim(-1, N_BEANS + 2)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("beans through 18 mm throat")
    ax.set_title("Beans through the throat over time (gate opens at 1 s)")
    ax.grid(alpha=0.3)

    fig.suptitle("Grinder hopper discharge: 50 roasted beans, 18 mm throat, 5 s")
    fig.tight_layout()
    fig.savefig(OUT, dpi=110)
    print(f"Figure saved to {OUT}")


if __name__ == "__main__":
    main()
