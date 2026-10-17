#!/usr/bin/env python3
"""A small, reproducible MuJoCo hopper discharge study."""
import os
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import mujoco
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Ellipse, FancyArrowPatch

HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "model.xml"
OUT = os.environ.get("OUT", str(HERE / "hopper.png"))
N_BEANS = 50
BEAN_LENGTH = 0.0080
BEAN_WIDTH = 0.0045
BEAN_THICKNESS = 0.0030
BEAN_MASS = 0.00008                 # 0.08 g, roasted arabica-scale bean
BEAN_FRICTION = (0.30, 0.005, 0.0001)
THROAT_DIAMETER = 0.018
DT = 0.001

# Funnel is a real open conical shell assembled from overlapping, thin wall facets.
z0, z1 = 0.22, 0.62
r0, r1 = THROAT_DIAMETER / 2, 0.080
slope = (r1-r0)/(z1-z0)
alpha = math.atan(slope)
length = math.hypot(z1-z0, r1-r0)

root = ET.Element('mujoco', model='50-bean grinder hopper')
compiler = ET.SubElement(root, 'compiler', angle='radian', autolimits='true')
ET.SubElement(root, 'option', timestep=str(DT), gravity='0 0 -9.81', integrator='implicitfast',
              solver='Newton', iterations='80', tolerance='1e-10', cone='elliptic')
ET.SubElement(root, 'size', njmax='5000', nconmax='2000')
asset = ET.SubElement(root, 'asset')
ET.SubElement(asset, 'material', name='steel', rgba='0.40 0.48 0.54 1', specular='0.35', shininess='0.25')
ET.SubElement(asset, 'material', name='traymat', rgba='0.24 0.27 0.29 1')
ET.SubElement(asset, 'material', name='beanmat', rgba='0.29 0.105 0.035 1', specular='0.12')
world = ET.SubElement(root, 'worldbody')
ET.SubElement(world, 'light', pos='0 0 1.8', dir='0 0 -1', diffuse='0.8 0.8 0.8')
# Tray and a modest raised rim so beans are retained.
ET.SubElement(world, 'geom', name='tray', type='box', pos='0 0 0.045', size='0.19 0.15 0.008',
              material='traymat', friction='0.8 0.01 0.001')
for sign in (-1, 1):
    ET.SubElement(world, 'geom', name=f'tray_rim_{sign}', type='box', pos=f'{sign*0.185} 0 0.065',
                  size='0.005 0.15 0.02', material='traymat', friction='0.8 0.01 0.001')
# A sealed thin-wall conical shell, represented by a triangulated frustum mesh.
facets = 48
verts = []
for radius, z in ((r0, z0), (r1, z1), (r0+0.0015, z0), (r1+0.0015, z1)):
    for i in range(facets):
        a = 2*math.pi*i/facets
        verts.extend((radius*math.cos(a), radius*math.sin(a), z))
faces = []
for i in range(facets):
    j = (i+1) % facets
    faces.extend(((i, j, facets+j), (i, facets+j, facets+i)))
    faces.extend(((2*facets+i, 3*facets+i, 3*facets+j), (2*facets+i, 3*facets+j, 2*facets+j)))
    faces.extend(((i, 2*facets+i, 2*facets+j), (i, 2*facets+j, j)))
    faces.extend(((facets+i, facets+j, 3*facets+j), (facets+i, 3*facets+j, 3*facets+i)))
ET.SubElement(asset, 'mesh', name='hopper_shell_mesh',
              vertex=' '.join(f'{v:.8g}' for v in verts),
              face=' '.join(str(x) for tri in faces for x in tri))
ET.SubElement(world, 'geom', name='hopper_shell', type='mesh', mesh='hopper_shell_mesh',
              material='steel', friction='0.30 0.005 0.0001', contype='0', conaffinity='0')
# The mesh is also the rendered wall; do not add overlapping collision facets.
for i in range(0):
    theta = 2*math.pi*i/facets
    # Local x is circumferential, local y is the wall normal and local z points up the slope.
    ct, st = math.cos(theta), math.sin(theta)
    ca, sa = math.cos(alpha), math.sin(alpha)
    # Tangent along the cone is (sin(alpha), cos(alpha)); outward normal
    # is (cos(alpha), -sin(alpha)). Local box y is the normal, local z tangent.
    R = np.array([[-st, ca*ct, sa*ct],
                  [ ct, ca*st, sa*st],
                  [  0,   -sa,    ca]])
    tr = np.trace(R)
    if tr > 0:
        q0 = math.sqrt(1+tr)*2
        quat = [q0/4, (R[2,1]-R[1,2])/q0, (R[0,2]-R[2,0])/q0, (R[1,0]-R[0,1])/q0]
    else:
        k = int(np.argmax(np.diag(R)))
        if k == 0:
            q = math.sqrt(1+R[0,0]-R[1,1]-R[2,2])*2
            quat = [(R[2,1]-R[1,2])/q, q/4, (R[0,1]+R[1,0])/q, (R[0,2]+R[2,0])/q]
        elif k == 1:
            q = math.sqrt(1+R[1,1]-R[0,0]-R[2,2])*2
            quat = [(R[0,2]-R[2,0])/q, (R[0,1]+R[1,0])/q, q/4, (R[1,2]+R[2,1])/q]
        else:
            q = math.sqrt(1+R[2,2]-R[0,0]-R[1,1])*2
            quat = [(R[1,0]-R[0,1])/q, (R[0,2]+R[2,0])/q, (R[1,2]+R[2,1])/q, q/4]
    # Facet overlap at the top radius closes the polygon without excessive seam gaps.
    halfwidth = (2*math.pi*((r0+r1)/2)/facets)*0.54
    rr = (r0+r1)/2 + 0.00075
    zz = (z0+z1)/2
    ET.SubElement(world, 'geom', name=f'hopper_wall_{i:02d}', type='box',
                  pos=f'{rr*ct:.8f} {rr*st:.8f} {zz:.8f}',
                  quat=' '.join(f'{x:.10g}' for x in quat),
                  size=f'{halfwidth:.8f} 0.0015 {length/2+0.002:.8f}',
                  material='steel', friction='0.30 0.005 0.0001')
# Sliding gate below the throat; the 36 mm stroke fully clears the opening.
gatebody = ET.SubElement(world, 'body', name='sliding_gate', pos='0 0 0.205')
ET.SubElement(gatebody, 'joint', name='gate_slide', type='slide', axis='1 0 0', range='0 0.040', damping='2',
              limited='true', ref='0')
ET.SubElement(gatebody, 'geom', name='gate_plate', type='box', pos='0 0 0', size='0.027 0.027 0.002',
              material='steel', friction='0.6 0.005 0.0001')
# Bean bodies: a thin flattened ellipsoid plus an overlapping, offset ellipsoid for the domed side.
# Their union is one free body per bean, with declared mass/inertia and identical contact behavior.
bean_zs = [0.405, 0.438, 0.471, 0.504, 0.537]
# deterministic staggered, gently packed layers, kept inside the widening funnel
layer_points = [(-0.032,-0.015),(-0.016,-0.015),(0,-0.015),(0.016,-0.015),(0.032,-0.015),
                (-0.024,0.005),(-0.008,0.005),(0.008,0.005),(0.024,0.005),(0.040,0.005)]
# shuffle order deterministically between layers without changing the layer spacing
for i in range(N_BEANS):
    layer, j = divmod(i, 10)
    x,y = layer_points[(j + layer*3) % 10]
    # Small deterministic offsets avoid a perfectly crystalline stack.
    x += 0.0011*math.sin(i*2.17)
    y += 0.0009*math.cos(i*1.71)
    z = bean_zs[layer] + 0.0006*math.sin(i*1.33)
    b = ET.SubElement(world, 'body', name=f'bean_{i:02d}', pos=f'{x:.6f} {y:.6f} {z:.6f}')
    ET.SubElement(b, 'freejoint', name=f'bean_free_{i:02d}')
    ET.SubElement(b, 'inertial', pos='0 0 0', mass=str(BEAN_MASS), diaginertia='1.3e-9 1.8e-9 2.0e-9')
    common = dict(type='ellipsoid', material='beanmat', friction=' '.join(map(str, BEAN_FRICTION)),
                  contype='1', conaffinity='1')
    ET.SubElement(b, 'geom', name=f'bean_{i:02d}_flat', pos='0 0 -0.00045', size='0.0040 0.00225 0.00065', **common)
    ET.SubElement(b, 'geom', name=f'bean_{i:02d}_dome', pos='0 0 0.00035', size='0.0034 0.00210 0.00135', **common)
# Serialize a usable standalone MJCF alongside this script.
ET.indent(root, space='  ')
ET.ElementTree(root).write(MODEL_PATH, encoding='unicode', xml_declaration=True)
model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
data = mujoco.MjData(model)

# Save state at requested times, plus contact diagnostics and crossing history.
requested = [0.0, 1.0, 2.0, 5.0]
snapshots = {}
contacts_at_2 = []
crossed = set()
cross_history = [(0.0, 0)]
max_wall_penetration = 0.0
wall_ids = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f'hopper_wall_{i:02d}') for i in range(facets)}
bean_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f'bean_{i:02d}') for i in range(N_BEANS)]
gate_qadr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'gate_slide')]
gate_dadr = model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'gate_slide')]

def capture(t):
    mujoco.mj_forward(model, data)
    states = np.array([data.xpos[b].copy() for b in bean_ids])
    axes = np.array([data.xmat[b].reshape(3,3)[:,0].copy() for b in bean_ids])
    snapshots[t] = (states, axes, len(crossed))
    if abs(t-2.0) < DT/2:
        for ci in range(data.ncon):
            c = data.contact[ci]
            force = np.zeros(6)
            mujoco.mj_contactForce(model, data, ci, force)
            frame = c.frame.reshape(3, 3)
            world_force = frame.T @ force[:3]
            contacts_at_2.append((c.pos.copy(), c.geom1, c.geom2, world_force))

capture(0.0)
next_snap = 1
nsteps = int(round(5.0/DT))
for step in range(1, nsteps+1):
    t = step*DT
    if 1.0 <= t < 1.05:
        data.qpos[gate_qadr] = min(0.040, (t-1.0)*0.8)
        data.qvel[gate_dadr] = 0.8 if data.qpos[gate_qadr] < 0.040 else 0.0
    elif t >= 1.05:
        data.qpos[gate_qadr] = 0.040
        data.qvel[gate_dadr] = 0
    mujoco.mj_step(model, data)
    # Throughput is the first downward crossing of the throat plane by each bean center.
    for k,bid in enumerate(bean_ids):
        z = data.xpos[bid,2]
        if z < z0 - 0.008 and k not in crossed:
            crossed.add(k)
            cross_history.append((t, len(crossed)))
    for ci in range(data.ncon):
        c = data.contact[ci]
        if c.geom1 in wall_ids or c.geom2 in wall_ids:
            max_wall_penetration = max(max_wall_penetration, max(0.0, -float(c.dist)))
    if step == 2000:
        capture(2.0)
    if next_snap < len(requested) and step == int(requested[next_snap]/DT):
        capture(requested[next_snap])
        next_snap += 1
    if step % 20 == 0 and (not cross_history or t-cross_history[-1][0] > 0.019):
        cross_history.append((t, len(crossed)))

# Any bean beyond the safety envelope is reported as escaped rather than silently discarded.
final_positions = np.array([data.xpos[b].copy() for b in bean_ids])
escaped = [i for i,p in enumerate(final_positions) if abs(p[0]) > 0.30 or abs(p[1]) > 0.30 or p[2] < -0.05 or p[2] > 1.0]

# One publication-style figure: four requested views, one force/contact diagnostic, one throughput plot.
fig, axs = plt.subplots(2, 3, figsize=(16, 10), constrained_layout=True)
fig.suptitle('50 roasted coffee beans through an 18 mm grinder throat  |  MuJoCo, 5 s', fontsize=16, weight='bold')

def draw_scene(ax, t, diagnostic=False):
    pos, axes, crossed_count = snapshots[t]
    ax.set_title(f't = {t:g} s  |  through throat: {crossed_count} / 50', fontsize=11)
    # Cross-section shows internal beans; subtle end-on view of modeled circular throat.
    ax.plot([-r1, -r0], [z1, z0], color='#46545d', lw=5, solid_capstyle='butt')
    ax.plot([r1, r0], [z1, z0], color='#46545d', lw=5, solid_capstyle='butt')
    ax.plot([-r1, r1], [z1,z1], color='#46545d', lw=2)
    ax.plot([-0.027,0.027],[0.205,0.205], color='#aa5736', lw=5, solid_capstyle='butt')
    ax.plot([-0.18,0.18],[0.053,0.053], color='#444b50', lw=3)
    ax.plot([-0.19,-0.19],[0.053,0.085], color='#444b50', lw=2)
    ax.plot([0.19,0.19],[0.053,0.085], color='#444b50', lw=2)
    for p, axis in zip(pos, axes):
        # Side-view bean glyph: brown body with a visible lighter flat/domed-face cue.
        width = BEAN_LENGTH
        height = BEAN_THICKNESS
        angle = math.degrees(math.atan2(axis[2], axis[0]))
        ax.add_patch(Ellipse((p[0],p[2]), width, height, angle=angle,
                             facecolor='#87441f', edgecolor='#402316', linewidth=.45, zorder=3))
        ax.add_patch(Ellipse((p[0]+0.0006,p[2]+0.00015), width*.54, height*.42, angle=angle,
                             facecolor='#b77843', edgecolor='none', alpha=.78, zorder=4))
    if diagnostic:
        for p,g1,g2,f in contacts_at_2:
            # MuJoCo contact-force normal is expressed in the contact frame; reconstruct world vector.
            # contact frame x-axis is the normal, so use the frame stored in data at capture time below.
            if np.linalg.norm(f) > 0:
                ax.scatter([p[0]],[p[2]],s=17,c='#00a5a8',edgecolors='black',linewidths=.35,zorder=7)
        ax.text(.02,.975,f'{len(contacts_at_2)} contacts; cyan = contact points\nred arrows = MuJoCo contact force',
                transform=ax.transAxes,va='top',fontsize=8,bbox=dict(boxstyle='round',fc='white',alpha=.85))
        # Illustrative force vectors are drawn at points; world normal is recovered from MuJoCo frames.
        for p,g1,g2,f in contacts_at_2[::max(1, len(contacts_at_2)//35)]:
            if np.linalg.norm(f) > 0:
                scale = min(0.004, 0.004 / max(np.linalg.norm(f), 1e-9))
                ax.annotate('', xy=(p[0]+f[0]*scale,p[2]+f[2]*scale), xytext=(p[0],p[2]),
                            arrowprops=dict(arrowstyle='-|>', color='#c43c35', lw=1.2), zorder=8)
    ax.set_xlim(-.105,.105); ax.set_ylim(0,.68)
    ax.set_aspect('equal', adjustable='box'); ax.set_xlabel('x (m)'); ax.set_ylabel('height z (m)')
    ax.grid(alpha=.18)

for ax,t in zip(axs.flat[:4], requested):
    draw_scene(ax,t)
draw_scene(axs.flat[4],2.0,True)
ax=axs.flat[5]
ts=np.array([q[0] for q in cross_history]); cs=np.array([q[1] for q in cross_history])
ax.step(ts,cs,where='post',color='#8b4a24',lw=2.5)
for t in requested:
    j=np.searchsorted(ts,t,side='right')-1
    ax.scatter([t],[cs[max(0,j)]],color='#d27a33',zorder=3)
    ax.annotate(str(cs[max(0,j)]),(t,cs[max(0,j)]),xytext=(4,7),textcoords='offset points',fontsize=9)
ax.axvline(1,color='#aa5736',ls='--',lw=1.4,label='gate opens')
ax.set(xlim=(0,5),ylim=(-1,52),xlabel='time (s)',ylabel='beans through throat (cumulative)',title='Discharge history')
ax.grid(alpha=.25); ax.legend(loc='lower right',fontsize=8)
fig.savefig(OUT,dpi=180,bbox_inches='tight')
plt.close(fig)

print(f'Maximum hopper-wall penetration: {max_wall_penetration*1000:.4f} mm')
for t in requested:
    count = snapshots[t][2]
    print(f'Beans through throat at {t:g} s: {count} / {N_BEANS}')
print('Beans that left the model: ' + (', '.join(f'{i:02d}' for i in escaped) if escaped else 'none'))
print(f'MJCF: {MODEL_PATH}')
print(f'Figure: {OUT}')
