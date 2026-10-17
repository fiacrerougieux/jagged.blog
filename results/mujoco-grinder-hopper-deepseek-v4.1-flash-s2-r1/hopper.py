"""
Coffee grinder hopper: 50 roasted coffee beans released through an 18 mm throat
onto a tray.  One figure with four time snapshots, a diagnostic frame carrying
contact points and force vectors, and the cumulative beans-through-throat curve.

Simulated with MuJoCo.  The MJCF is written to model.xml beside this script.
"""

import os
import math

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

import mujoco

# =====================================================================
#  Declared parameters
# =====================================================================
# --- hopper -----------------------------------------------------------
THROAT_DIAM = 0.018                 # 18 mm throat
R_THROAT = THROAT_DIAM / 2.0        # 9 mm
R_TOP = 0.026                        # 26 mm top radius (52 mm opening)
H_CONE = 0.032                       # 32 mm cone height -> 28 deg half angle
N_PANEL = 48                         # flat facets approximating the cone
PANEL_T = 0.0015                     # wall thickness

# --- bean -------------------------------------------------------------
# one free body = two overlapping ellipsoids -> flat face + domed face
# ellipsoid A: wide + flat (the flat face)
A_SEMI = (0.0050, 0.0035, 0.0012)          # 10 x 7 x 2.4 mm
# ellipsoid B: smaller dome overlapping the top (the domed face)
B_SEMI = (0.0034, 0.0026, 0.0022)          # 6.8 x 5.2 x 4.4 mm
B_POS = (0.0, 0.0, 0.0006)
BEAN_MASS_TARGET = 0.15e-3                  # 0.15 g roasted bean
BEAN_DENSITY = BEAN_MASS_TARGET / (
    (4.0 / 3.0) * math.pi * A_SEMI[0] * A_SEMI[1] * A_SEMI[2]
    + (4.0 / 3.0) * math.pi * B_SEMI[0] * B_SEMI[1] * B_SEMI[2]
)                                           # ~885 kg/m^3

# --- contact / solver -------------------------------------------------
BEAN_FRICTION = (0.45, 0.004, 0.0006)       # slide, torsional, rolling
WALL_FRICTION = (0.35, 0.004, 0.0006)
SOLREF = (0.005, 1.0)                       # contact timeconst / damping
SOLIMP = (0.9, 0.95, 0.001)
TIMESTEP = 5e-4
INTEGRATOR = "implicitfast"
SOLVER = "Newton"
CONE = "elliptic"
ITERATIONS = 200
TOLERANCE = 1e-8

# --- scene ------------------------------------------------------------
N_BEANS = 50
TRAY_TOP = -0.085                    # tray floor 85 mm under the throat
TRAY_HALF = 0.14
TRAY_WALL_H = 0.030
GATE_CLOSED = np.array([0.0, 0.0, -0.0025])
GATE_OPEN_DX = 0.065
GATE_OPEN_START = 1.0
GATE_OPEN_TIME = 0.15
SETTLE_TIME = 1.0
SIM_TIME = 5.0
Z_THROAT = -0.004                    # plane used to count beans through throat
DRAW_TIMES = [0.0, 1.0, 2.0, 5.0]
DIAG_TIME = 1.40                     # instant of the contact/force diagnostic


# =====================================================================
#  Geometry helpers
# =====================================================================
def mat_to_quat(R):
    """Rotation matrix (columns = local axes in world) -> [w,x,y,z]."""
    t = np.trace(R)
    if t > 0.0:
        s = math.sqrt(t + 1.0) * 2.0
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2.0
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2.0
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2.0
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z], dtype=float)
    return q / np.linalg.norm(q)


def hopper_panels():
    """Return list of (pos, quat, size) for the faceted cone wall."""
    dr = R_TOP - R_THROAT
    alpha = math.atan2(dr, H_CONE)
    ca, sa = math.cos(alpha), math.sin(alpha)
    L = math.hypot(H_CONE, dr)
    r_mid = 0.5 * (R_TOP + R_THROAT)
    width = 2.0 * r_mid * math.tan(math.pi / N_PANEL)
    out = []
    for i in range(N_PANEL):
        th = 2.0 * math.pi * i / N_PANEL
        ct, st = math.cos(th), math.sin(th)
        d = np.array([sa * ct, sa * st, ca])            # up the slant
        tg = np.array([-st, ct, 0.0])                   # tangential
        nrm = np.array([-ca * ct, -ca * st, sa])        # inward normal
        surf = np.array([r_mid * ct, r_mid * st, 0.5 * H_CONE])
        pos = surf - nrm * (PANEL_T / 2.0)              # inner face on cone
        R = np.column_stack([d, tg, nrm])
        out.append((pos, mat_to_quat(R), (L, width, PANEL_T)))
    return out


def initial_bean_poses():
    """Loose hex packing inside the cone, above the closed gate."""
    rng = np.random.default_rng(7)
    poses = []
    z = 0.0045
    dy = 0.0098
    dx = 0.0105
    while len(poses) < N_BEANS and z < H_CONE * 0.95:
        Rz = R_THROAT + (R_TOP - R_THROAT) * (z / H_CONE)
        rmax = max(Rz - 0.0055, 0.0)
        if rmax > 0.0035:
            ny = int(rmax / dy) + 1
            for iy in range(-ny, ny + 1):
                y = iy * dy
                if abs(y) > rmax:
                    continue
                half = math.sqrt(max(rmax * rmax - y * y, 0.0))
                nx = int(half / dx) + 1
                for ix in range(-nx, nx + 1):
                    x = ix * dx + (0.5 * dx if (iy % 2) else 0.0)
                    if x * x + y * y <= rmax * rmax:
                        poses.append((x, y, z))
                        if len(poses) >= N_BEANS:
                            break
                if len(poses) >= N_BEANS:
                    break
        z += 0.0058
    while len(poses) < N_BEANS:                        # fallback: keep stacking
        poses.append((0.0, 0.0, z))
        z += 0.006
    poses = poses[:N_BEANS]
    quats = []
    for _ in range(N_BEANS):
        q = rng.normal(size=4)
        q /= np.linalg.norm(q)
        if q[0] < 0:
            q = -q
        quats.append(q)
    return poses, quats


# =====================================================================
#  MJCF
# =====================================================================
def build_xml():
    panels = hopper_panels()
    poses, quats = initial_bean_poses()

    lines = []
    a = lines.append
    a('<mujoco model="coffee_hopper">')
    a('  <compiler angle="radian" coordinate="local" inertiafromgeom="true"/>')
    a(f'  <option timestep="{TIMESTEP}" integrator="{INTEGRATOR}" solver="{SOLVER}"')
    a(f'          cone="{CONE}" iterations="{ITERATIONS}" tolerance="{TOLERANCE}"')
    a('          gravity="0 0 -9.81"/>')
    a('  <visual>')
    a('    <global offwidth="960" offheight="720"/>')
    a('    <headlight diffuse="0.75 0.75 0.75" ambient="0.40 0.40 0.40"'
      ' specular="0.25 0.25 0.25"/>')
    a('  </visual>')
    a('  <asset>')
    a('    <texture type="skybox" builtin="gradient" rgb1="0.55 0.70 0.85"')
    a('             rgb2="0.12 0.16 0.24" width="512" height="3072"/>')
    a('    <texture name="traytex" type="2d" builtin="checker"')
    a('             rgb1="0.58 0.54 0.49" rgb2="0.44 0.40 0.36"')
    a('             width="256" height="256"/>')
    a('    <material name="traymat" texture="traytex" texrepeat="8 8"'
      ' reflectance="0.05"/>')
    a('  </asset>')
    a('  <default>')
    a(f'    <geom condim="4" friction="{BEAN_FRICTION[0]} {BEAN_FRICTION[1]} '
      f'{BEAN_FRICTION[2]}"')
    a(f'          solref="{SOLREF[0]} {SOLREF[1]}" '
      f'solimp="{SOLIMP[0]} {SOLIMP[1]} {SOLIMP[2]}"/>')
    a('    <default class="bean">')
    a('      <geom type="ellipsoid" rgba="0.38 0.20 0.08 1"')
    a(f'            friction="{BEAN_FRICTION[0]} {BEAN_FRICTION[1]} '
      f'{BEAN_FRICTION[2]}"/>')
    a('    </default>')
    a('    <default class="wall">')
    a('      <geom type="box" rgba="0.64 0.68 0.74 0.45"')
    a(f'            friction="{WALL_FRICTION[0]} {WALL_FRICTION[1]} '
      f'{WALL_FRICTION[2]}"/>')
    a('    </default>')
    a('    <default class="tray">')
    a('      <geom type="box" material="traymat"')
    a(f'            friction="{WALL_FRICTION[0]} {WALL_FRICTION[1]} '
      f'{WALL_FRICTION[2]}"/>')
    a('    </default>')
    a('  </default>')
    a('  <worldbody>')
    a('    <light pos="0.20 -0.20 0.45" dir="-0.4 0.4 -0.8" directional="true"/>')
    a('    <light pos="-0.25 0.15 0.30" dir="0.5 -0.3 -0.8" directional="true"/>')

    # cone wall facets
    for i, (pos, quat, size) in enumerate(panels):
        a(f'    <geom name="hopperpanel_{i}" class="wall" type="box"')
        a(f'          size="{size[0]/2:.6f} {size[1]/2:.6f} {size[2]/2:.6f}"')
        a(f'          pos="{pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}"')
        a(f'          quat="{quat[0]:.6f} {quat[1]:.6f} {quat[2]:.6f} '
          f'{quat[3]:.6f}"')
        a('          contype="1" conaffinity="1"/>')

    # tray floor + 4 walls
    a(f'    <geom name="tray_floor" class="tray" '
      f'size="{TRAY_HALF:.4f} {TRAY_HALF:.4f} 0.004"')
    a(f'          pos="0 0 {TRAY_TOP - 0.004:.4f}"/>')
    wt = 0.004
    for name, px, py, sx, sy in [
        ("tray_xp", TRAY_HALF, 0.0, wt, TRAY_HALF),
        ("tray_xm", -TRAY_HALF, 0.0, wt, TRAY_HALF),
        ("tray_yp", 0.0, TRAY_HALF, TRAY_HALF, wt),
        ("tray_ym", 0.0, -TRAY_HALF, TRAY_HALF, wt),
    ]:
        a(f'    <geom name="{name}" class="tray" '
          f'size="{sx:.4f} {sy:.4f} {TRAY_WALL_H/2:.4f}"')
        a(f'          pos="{px:.4f} {py:.4f} {TRAY_TOP + TRAY_WALL_H/2:.4f}"/>')

    # sliding gate (mocap)
    a('    <body name="gate" mocap="true" pos="0 0 -0.0025">')
    a('      <geom name="gate_plate" class="wall" type="box" '
      'size="0.020 0.020 0.0015" rgba="0.80 0.80 0.83 1"/>')
    a('      <geom name="gate_handle" class="wall" type="box" '
      'size="0.006 0.004 0.0015" pos="0.024 0 0" rgba="0.35 0.35 0.38 1"/>')
    a('    </body>')

    # beans
    for i, ((x, y, z), q) in enumerate(zip(poses, quats)):
        a(f'    <body name="bean_{i}" pos="{x:.5f} {y:.5f} {z:.5f}"'
          f' quat="{q[0]:.5f} {q[1]:.5f} {q[2]:.5f} {q[3]:.5f}">')
        a(f'      <freejoint name="beanfree_{i}"/>')
        a(f'      <geom name="beanA_{i}" class="bean" '
          f'size="{A_SEMI[0]} {A_SEMI[1]} {A_SEMI[2]}"/>')
        a(f'      <geom name="beanB_{i}" class="bean" '
          f'size="{B_SEMI[0]} {B_SEMI[1]} {B_SEMI[2]}"')
        a(f'            pos="{B_POS[0]} {B_POS[1]} {B_POS[2]}"/>')
        a('    </body>')

    a('  </worldbody>')
    a('</mujoco>')
    return "\n".join(lines)


# =====================================================================
#  Simulation helpers
# =====================================================================
def gate_x(t):
    if t <= GATE_OPEN_START:
        return 0.0
    u = min((t - GATE_OPEN_START) / GATE_OPEN_TIME, 1.0)
    return GATE_OPEN_DX * (3.0 * u * u - 2.0 * u * u * u)


def capture_state(model, data, bean_body_ids):
    """Snapshot bean poses, contact points and world-frame contact forces."""
    mujoco.mj_forward(model, data)
    poses = []
    for b in bean_body_ids:
        poses.append((data.xpos[b].copy(), data.xmat[b].reshape(3, 3).copy()))
    pts, vecs, mags = [], [], []
    for i in range(data.ncon):
        c = data.contact[i]
        res = np.zeros(6)
        mujoco.mj_contactForce(model, data, i, res)
        frame = np.asarray(c.frame, dtype=float).reshape(3, 3)
        fw = frame.T @ res[:3]
        pts.append(np.asarray(c.pos, dtype=float).copy())
        vecs.append(fw)
        mags.append(np.linalg.norm(fw))
    return {
        "poses": poses,
        "cpos": np.array(pts) if pts else np.zeros((0, 3)),
        "cforce": np.array(vecs) if vecs else np.zeros((0, 3)),
        "cmag": np.array(mags) if mags else np.zeros((0,)),
    }


def ellipsoid_surface(semi, R, center, nu=9, nv=6):
    u = np.linspace(0.0, 2.0 * math.pi, nu + 1)
    v = np.linspace(0.0, math.pi, nv + 1)
    U, V = np.meshgrid(u, v)
    xs = semi[0] * np.sin(V) * np.cos(U)
    ys = semi[1] * np.sin(V) * np.sin(U)
    zs = semi[2] * np.cos(V)
    P = np.stack([xs, ys, zs], axis=-1)
    P = P @ R.T + center
    return P[..., 0], P[..., 1], P[..., 2]


def draw_diagnostic(ax, snap):
    """Matplotlib-3D diagnostic: hopper, beans, contact points, force vectors."""
    ax.set_facecolor("white")
    # hopper cone
    th = np.linspace(0.0, 2.0 * math.pi, 73)
    zz = np.linspace(0.0, H_CONE, 2)
    TH, ZZ = np.meshgrid(th, zz)
    RR = R_THROAT + (R_TOP - R_THROAT) * ZZ / H_CONE
    ax.plot_surface(RR * np.cos(TH), RR * np.sin(TH), ZZ,
                    color="steelblue", alpha=0.13, linewidth=0, shade=False)
    # cone wireframe for structure
    for zlev in (0.0, 0.5 * H_CONE, H_CONE):
        r = R_THROAT + (R_TOP - R_THROAT) * zlev / H_CONE
        ax.plot(r * np.cos(th), r * np.sin(th), np.full_like(th, zlev),
                color="steelblue", lw=0.6, alpha=0.6)
    # tray floor
    tx = np.array([[-TRAY_HALF, TRAY_HALF], [-TRAY_HALF, TRAY_HALF]])
    ty = np.array([[-TRAY_HALF, -TRAY_HALF], [TRAY_HALF, TRAY_HALF]])
    ax.plot_surface(tx, ty, np.full_like(tx, TRAY_TOP, dtype=float),
                    color="tan", alpha=0.35, linewidth=0, shade=False)

    # beans as two overlapping ellipsoids
    # sliding gate for context
    gx = gate_x(DIAG_TIME)
    ax.bar3d(gx - 0.020, -0.020, GATE_CLOSED[2] - 0.0015,
             0.040, 0.040, 0.003, color="0.8", alpha=0.35, shade=False)
    for (pos, R) in snap["poses"]:
        for semi, off in ((A_SEMI, np.zeros(3)), (B_SEMI, np.array(B_POS))):
            X, Y, Z = ellipsoid_surface(semi, R, pos + R @ off)
            ax.plot_surface(X, Y, Z, color="#7a4415", alpha=0.65,
                            linewidth=0, shade=True)

    # contact points + force vectors
    cp = snap["cpos"]
    if len(cp):
        ax.scatter(cp[:, 0], cp[:, 1], cp[:, 2], c="red", s=11,
                   depthshade=False, zorder=6)
        cf = snap["cforce"]
        fmax = max(snap["cmag"].max(), 1e-9)
        scale = 0.030 / fmax            # longest arrow 30 mm
        ax.quiver(cp[:, 0], cp[:, 1], cp[:, 2],
                  cf[:, 0], cf[:, 1], cf[:, 2],
                  length=scale, normalize=False, color="#ff7f00",
                  arrow_length_ratio=0.45, linewidth=1.1)
        from matplotlib.lines import Line2D
        handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor="red",
                          markersize=7, label=f"contact point (n={len(cp)})"),
                   Line2D([0], [0], color="#ff7f00", lw=2,
                          label=f"contact force (max {fmax*1e3:.1f} mN)")]
        ax.legend(handles=handles, loc="upper right", fontsize=9)

    lim = 0.050
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-0.050, 0.050)
    ax.set_box_aspect((1, 1, 1.0))
    ax.view_init(elev=22, azim=-52)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    try:
        ax.set_proj_type("persp", focal_length=0.5)
    except Exception:
        pass


# =====================================================================
#  Main
# =====================================================================
def main():
    xml = build_xml()
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "model.xml"), "w") as f:
        f.write(xml)
    try:
        with open("/work/model.xml", "w") as f:
            f.write(xml)
    except Exception:
        pass

    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    dt = model.opt.timestep

    # --- identify geom families -------------------------------------
    panel_ids, gate_ids, tray_ids, bean_geom_ids = set(), set(), set(), set()
    for gid in range(model.ngeom):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, gid) or ""
        if name.startswith("hopperpanel"):
            panel_ids.add(gid)
        elif name.startswith("gate"):
            gate_ids.add(gid)
        elif name.startswith("tray"):
            tray_ids.add(gid)
        elif name.startswith("bean"):
            bean_geom_ids.add(gid)

    bean_body_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY,
                                       f"bean_{i}") for i in range(N_BEANS)]
    gate_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "gate")
    gate_mid = model.body_mocapid[gate_bid]

    bean_mass = model.body_mass[bean_body_ids[0]]
    print("=" * 70)
    print("DECLARED MODEL")
    print("=" * 70)
    print(f"  beans            : {N_BEANS} free bodies, each 2 overlapping ellipsoids")
    print(f"  bean size        : A {2*A_SEMI[0]*1e3:.1f} x {2*A_SEMI[1]*1e3:.1f} x "
          f"{2*A_SEMI[2]*1e3:.1f} mm  +  B {2*B_SEMI[0]*1e3:.1f} x "
          f"{2*B_SEMI[1]*1e3:.1f} x {2*B_SEMI[2]*1e3:.1f} mm")
    print(f"  bean mass        : {bean_mass*1e3:.3f} g  "
          f"(density {BEAN_DENSITY:.0f} kg/m^3)")
    print(f"  throat           : {THROAT_DIAM*1e3:.1f} mm diameter, cone top R "
          f"{R_TOP*1e3:.0f} mm, height {H_CONE*1e3:.0f} mm, {N_PANEL} facets")
    print(f"  friction bean    : slide {BEAN_FRICTION[0]}, torsional "
          f"{BEAN_FRICTION[1]}, rolling {BEAN_FRICTION[2]}")
    print(f"  friction wall    : slide {WALL_FRICTION[0]}, torsional "
          f"{WALL_FRICTION[1]}, rolling {WALL_FRICTION[2]}")
    print(f"  contact          : condim 4, solref {SOLREF}, solimp {SOLIMP}")
    print(f"  solver           : {SOLVER}, cone {CONE}, iters {ITERATIONS}, "
          f"tol {TOLERANCE}, integrator {INTEGRATOR}, dt {dt}")
    print("=" * 70)

    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.lookat[:] = [0.0, 0.0, -0.022]
    cam.distance = 0.210
    cam.azimuth = 135.0
    cam.elevation = -28.0

    renderer = mujoco.Renderer(model, height=520, width=680)
    opt_plain = mujoco.MjvOption()

    def render_frame():
        renderer.update_scene(data, camera=cam, scene_option=opt_plain)
        return renderer.render().copy()

    # --- settle with the gate closed --------------------------------
    data.mocap_pos[gate_mid] = GATE_CLOSED
    for _ in range(int(SETTLE_TIME / dt)):
        mujoco.mj_step(model, data)
    mujoco.mj_forward(model, data)
    data.time = 0.0
    data.qvel[:] = 0.0

    # --- statistics state -------------------------------------------
    prev_z = np.array([data.xpos[b][2] for b in bean_body_ids])
    through_count = 0
    through_events = [(0.0, 0)]
    max_pen = 0.0
    max_pen_t = 0.0
    escaped = {}
    diag_snap = None

    frames = {0.0: render_frame()}

    n_steps = int(round(SIM_TIME / dt))
    for step in range(1, n_steps + 1):
        gp = GATE_CLOSED.copy()
        gp[0] += gate_x(data.time)
        data.mocap_pos[gate_mid] = gp
        mujoco.mj_step(model, data)

        # penetration into hopper walls (bean <-> panel)
        for ci in range(data.ncon):
            c = data.contact[ci]
            g1, g2 = c.geom1, c.geom2
            pair = (g1 in panel_ids and g2 in bean_geom_ids) or \
                   (g2 in panel_ids and g1 in bean_geom_ids)
            if pair:
                pen = -c.dist
                if pen > max_pen:
                    max_pen = pen
                    max_pen_t = data.time

        # through-throat detection + escape test
        zs = np.array([data.xpos[b][2] for b in bean_body_ids])
        for i in range(N_BEANS):
            if prev_z[i] > Z_THROAT >= zs[i]:
                p = data.xpos[bean_body_ids[i]]
                if math.hypot(p[0], p[1]) < 0.05:
                    through_count += 1
                    through_events.append((data.time, through_count))
            p = data.xpos[bean_body_ids[i]]
            if (abs(p[0]) > 0.30 or abs(p[1]) > 0.30 or p[2] < -0.30
                    or not np.all(np.isfinite(p))) and i not in escaped:
                escaped[i] = (data.time, p.copy())
        prev_z = zs

        for tt in DRAW_TIMES:
            if tt > 0 and tt not in frames and abs(data.time - tt) < 0.5 * dt:
                frames[tt] = render_frame()
        if diag_snap is None and data.time >= DIAG_TIME:
            diag_snap = capture_state(model, data, bean_body_ids)

    through_events.append((data.time, through_count))
    if SIM_TIME not in frames:
        frames[SIM_TIME] = render_frame()
    if diag_snap is None:
        diag_snap = capture_state(model, data, bean_body_ids)

    # =============================================================
    #  Figure
    # =============================================================
    fig = plt.figure(figsize=(18.0, 10.4))
    gs = GridSpec(2, 4, figure=fig, height_ratios=[1.0, 1.08],
                  hspace=0.20, wspace=0.07)

    for i, tt in enumerate(DRAW_TIMES):
        ax = fig.add_subplot(gs[0, i])
        img = frames.get(tt)
        if img is not None:
            ax.imshow(img)
        ax.set_title(f"hopper at t = {tt:.0f} s", fontsize=14)
        ax.axis("off")

    ax_d = fig.add_subplot(gs[1, 0:2], projection="3d")
    draw_diagnostic(ax_d, diag_snap)
    ax_d.set_title(f"diagnostic at t = {DIAG_TIME:.2f} s: contact points "
                   f"+ force vectors", fontsize=14, pad=2)

    ax_p = fig.add_subplot(gs[1, 2:4])
    ev = np.array(through_events, dtype=float)
    ax_p.step(ev[:, 0], ev[:, 1], where="post", color="saddlebrown", lw=2.5)
    ax_p.axvline(GATE_OPEN_START, color="steelblue", ls="--", lw=1.8,
                 label="gate opens (1.0 s)")
    for tt in DRAW_TIMES:
        cnt = 0
        for (te, cc) in through_events:
            if te <= tt + 1e-9:
                cnt = cc
        ax_p.plot(tt, cnt, "o", color="crimson", ms=9)
        off = (7, 6) if cnt < N_BEANS * 0.5 else ((-42, -22) if tt >= 4 else (-14, -22))
        ax_p.annotate(f"{cnt}", (tt, cnt), textcoords="offset points",
                      xytext=off, fontsize=13, color="crimson",
                      weight="bold")
    ax_p.set_xlim(0, 5)
    ax_p.set_ylim(0, N_BEANS)
    ax_p.set_xlabel("time (s)", fontsize=13)
    ax_p.set_ylabel("cumulative beans through throat", fontsize=13)
    ax_p.set_title("beans through the 18 mm throat", fontsize=14)
    ax_p.grid(True, alpha=0.3)
    ax_p.legend(loc="upper left", fontsize=12)

    fig.suptitle("Coffee-bean hopper: 50 beans, 18 mm throat, "
                 "sliding gate opens at 1 s", fontsize=17, y=0.99)
    fig.text(0.5, 0.955,
             f"bean: two overlapping ellipsoids {2*A_SEMI[0]*1e3:.0f}x"
             f"{2*A_SEMI[1]*1e3:.0f}x{2*A_SEMI[2]*1e3:.0f} mm + "
             f"{2*B_SEMI[0]*1e3:.0f}x{2*B_SEMI[1]*1e3:.0f}x"
             f"{2*B_SEMI[2]*1e3:.0f} mm, {bean_mass*1e3:.3f} g  |  "
             f"friction {BEAN_FRICTION[0]}  |  {SOLVER}/{CONE} cone, "
             f"dt={TIMESTEP*1e3:.2f} ms, iters={ITERATIONS}",
             ha="center", fontsize=10.5, color="0.25")
    out = os.environ.get("OUT", "figure.png")
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)

    # =============================================================
    #  Report
    # =============================================================
    print()
    print("RESULTS")
    print(f"  max penetration into hopper walls : {max_pen*1e3:.4f} mm "
          f"(at t = {max_pen_t:.3f} s)")
    counts = {}
    for tt in DRAW_TIMES:
        c = 0
        for (te, cc) in through_events:
            if te <= tt + 1e-9:
                c = cc
        counts[tt] = c
        print(f"  beans through throat at t = {tt:.0f} s : {c}")
    if escaped:
        print("  beans that left the model        :")
        for i, (te, p) in sorted(escaped.items()):
            print(f"      bean {i} at t={te:.3f}s "
                  f"pos=({p[0]:.3f},{p[1]:.3f},{p[2]:.3f})")
    else:
        print("  beans that left the model        : none")
    print(f"  final time = {data.time:.3f} s, "
          f"total through = {through_count}/{N_BEANS}")
    print(f"  diagnostic contacts = {len(diag_snap['cpos'])}")
    print(f"  figure -> {out}")


if __name__ == "__main__":
    main()
