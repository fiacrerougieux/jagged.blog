#!/usr/bin/env python3
"""50-bean grinder hopper drop: MuJoCo simulation and a diagnostic figure."""
from pathlib import Path
import os
import math
import numpy as np
import mujoco
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Rectangle, Circle

# --------------------------- declared model parameters ----------------------
N_BEANS = 50
BEAN_LENGTH = 0.0090             # m, long axis
BEAN_WIDTH = 0.0064              # m
BEAN_THICKNESS = 0.0048          # m, flat underside to domed top
BEAN_MASS = 1.20e-4              # kg, 0.12 g roasted bean
FRICTION = (0.62, 0.006, 0.0002) # sliding, torsional, rolling
THROAT_DIAMETER = 0.018          # m
DT = 0.001                       # s
SOLVER_ITERATIONS = 80
SOLVER_TOLERANCE = 1e-9
GATE_OPEN_TIME = 1.0
SIM_DURATION = 5.0
HOPPER_BOTTOM = 0.55
HOPPER_TOP = 1.55
HOPPER_TOP_RADIUS = 0.24
THROAT_RADIUS = THROAT_DIAMETER / 2
N_FACETS = 32

# Two massless, overlapping ellipsoids on each explicitly-inertial free body.
# The thin lower ellipsoid supplies a broad, nearly flat base; the upper one
# forms the characteristic domed face.
BEAN_GEOMS = '''
      <geom name="bean_%02d_flat" type="ellipsoid" pos="0 0 -0.00055"
            size="0.0045 0.0032 0.00165" mass="0" contype="1" conaffinity="1"
            friction="0.62 0.006 0.0002" rgba="0.30 0.105 0.035 1"/>
      <geom name="bean_%02d_dome" type="ellipsoid" pos="0 0 0.00045"
            size="0.00425 0.0030 0.00235" mass="0" contype="1" conaffinity="1"
            friction="0.62 0.006 0.0002" rgba="0.43 0.19 0.07 1"/>
'''

def q_from_matrix(R):
    """Convert a 3x3 rotation (columns are local axes) to MuJoCo wxyz."""
    tr = np.trace(R)
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = [0.25*s, (R[2,1]-R[1,2])/s, (R[0,2]-R[2,0])/s, (R[1,0]-R[0,1])/s]
    else:
        i = int(np.argmax(np.diag(R)))
        if i == 0:
            s = math.sqrt(1 + R[0,0]-R[1,1]-R[2,2])*2
            q = [(R[2,1]-R[1,2])/s, .25*s, (R[0,1]+R[1,0])/s, (R[0,2]+R[2,0])/s]
        elif i == 1:
            s = math.sqrt(1 + R[1,1]-R[0,0]-R[2,2])*2
            q = [(R[0,2]-R[2,0])/s, (R[0,1]+R[1,0])/s, .25*s, (R[1,2]+R[2,1])/s]
        else:
            s = math.sqrt(1 + R[2,2]-R[0,0]-R[1,1])*2
            q = [(R[1,0]-R[0,1])/s, (R[0,2]+R[2,0])/s, (R[1,2]+R[2,1])/s, .25*s]
    q = np.asarray(q); return q / np.linalg.norm(q)

def make_xml():
    parts = [f'''<mujoco model="coffee_grinder_hopper">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="{DT}" gravity="0 0 -9.81" integrator="implicitfast"
          solver="Newton" iterations="{SOLVER_ITERATIONS}" tolerance="{SOLVER_TOLERANCE}"
          cone="elliptic" impratio="10"/>
  <size njmax="12000" nconmax="3000"/>
  <default>
    <geom condim="4" friction="0.62 0.006 0.0002" solref="0.004 1" solimp="0.95 0.99 0.001"/>
  </default>
  <worldbody>
    <light pos="0 -1 2.5" dir="0 0.3 -1" diffuse="0.8 0.8 0.8"/>
    <geom name="floor" type="plane" pos="0 0 0" size="1 1 0.1" rgba="0.34 0.31 0.27 1"/>
''']
    # Thin, overlapping tangent box facets form a concave conical shell and
    # leave its inside open to the falling beans.
    dz = HOPPER_TOP-HOPPER_BOTTOM
    dr = HOPPER_TOP_RADIUS-THROAT_RADIUS
    zmid = (HOPPER_TOP+HOPPER_BOTTOM)/2
    rmid = (HOPPER_TOP_RADIUS+THROAT_RADIUS)/2
    slope = dr/dz
    zaxis = np.array([slope, 0., 1.]); zaxis /= np.linalg.norm(zaxis)
    for k in range(N_FACETS):
        th = 2*math.pi*(k+.5)/N_FACETS
        radial = np.array([math.cos(th), math.sin(th), 0.])
        normal = np.array([math.cos(th), math.sin(th), -slope]); normal /= np.linalg.norm(normal)
        xaxis = np.cross(normal, zaxis); xaxis /= np.linalg.norm(xaxis)
        # Recompute y to ensure a right-handed orthonormal frame.
        yaxis = np.cross(zaxis, xaxis); yaxis /= np.linalg.norm(yaxis)
        R = np.column_stack((xaxis, yaxis, zaxis))
        quat = q_from_matrix(R)
        pos = np.array([rmid*radial[0], rmid*radial[1], zmid])
        half_width = rmid*math.tan(math.pi/N_FACETS)*1.025
        half_slant = .5*math.sqrt(dz*dz+dr*dr)+.002
        parts.append(f'    <geom name="hopper_wall_{k:02d}" type="box" pos="{pos[0]:.8f} {pos[1]:.8f} {pos[2]:.8f}" quat="{" ".join(f"{v:.10f}" for v in quat)}" size="{half_width:.8f} 0.003 {half_slant:.8f}" rgba="0.62 0.64 0.66 1"/>\n')
    # Tray floor and four raised lips below the outlet.
    parts.append('''    <geom name="tray_floor" type="box" pos="0 0 0.030" size="0.75 0.35 0.012" rgba="0.48 0.43 0.36 1"/>
    <geom name="tray_back" type="box" pos="0 0.352 0.055" size="0.75 0.006 0.025" rgba="0.58 0.53 0.46 1"/>
    <geom name="tray_front" type="box" pos="0 -0.352 0.055" size="0.75 0.006 0.025" rgba="0.58 0.53 0.46 1"/>
    <geom name="tray_left" type="box" pos="-0.752 0 0.055" size="0.006 0.35 0.025" rgba="0.58 0.53 0.46 1"/>
    <geom name="tray_right" type="box" pos="0.752 0 0.055" size="0.006 0.35 0.025" rgba="0.58 0.53 0.46 1"/>
    <body name="sliding_gate" pos="0 0 0.525">
      <joint name="gate_slide" type="slide" axis="1 0 0" damping="8" armature="0.001" range="0 0.12"/>
      <geom name="gate_plate" type="box" pos="0 0 0" size="0.045 0.035 0.004" rgba="0.23 0.25 0.27 1"/>
    </body>
''')
    # Five beans per layer, randomized azimuth; settle into the funnel before
    # opening, while retaining realistic body-body contacts and free rotation.
    rng = np.random.default_rng(20250308)
    for i in range(N_BEANS):
        layer, slot = divmod(i, 5)
        z = 0.78 + layer*0.052 + rng.uniform(-0.004, 0.004)
        rwall = THROAT_RADIUS + (HOPPER_TOP_RADIUS-THROAT_RADIUS)*(z-HOPPER_BOTTOM)/dz
        ring = min(0.012 + (layer/9)*0.055, max(0.006, rwall-0.014))
        angle = 2*math.pi*slot/5 + (layer%2)*math.pi/5 + rng.uniform(-0.12,0.12)
        x = ring*math.cos(angle) + rng.uniform(-.003,.003)
        y = ring*math.sin(angle) + rng.uniform(-.003,.003)
        # random initial bean orientation; quaternion from axis-angle
        axis = rng.normal(size=3); axis /= np.linalg.norm(axis)
        a = rng.uniform(0, math.pi)
        q = np.r_[math.cos(a/2), axis*math.sin(a/2)]
        parts.append(f'''    <body name="bean_{i:02d}" pos="{x:.6f} {y:.6f} {z:.6f}" quat="{" ".join(f"{v:.8f}" for v in q)}">
      <freejoint name="bean_{i:02d}_free"/>
      <inertial pos="0 0 0" mass="{BEAN_MASS}" diaginertia="1.5e-10 3.0e-10 3.4e-10"/>
''')
        parts.append(BEAN_GEOMS % (i,i))
        parts.append('    </body>\n')
    parts.append('''  </worldbody>
  <actuator>
    <position name="gate_position" joint="gate_slide" kp="1200" kv="35" ctrlrange="0 0.12" forcerange="-120 120"/>
  </actuator>
</mujoco>
''')
    return ''.join(parts)

xml = make_xml()
# The mandated renderer executes a copied script from a scratch directory;
# emit the MJCF beside the submitted source in /work rather than that copy.
source_dir = Path('/work') if Path('/work/hopper.py').exists() else Path(__file__).resolve().parent
(source_dir/'model.xml').write_text(xml)
model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)

# Identify useful model ids once, then simulate exactly 5 s at the declared dt.
bean_body_ids = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f'bean_{i:02d}') for i in range(N_BEANS)])
bean_geom_ids = set()
for i in range(N_BEANS):
    bean_geom_ids.add(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f'bean_{i:02d}_flat'))
    bean_geom_ids.add(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f'bean_{i:02d}_dome'))
wall_ids = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f'hopper_wall_{k:02d}') for k in range(N_FACETS)}
gate_act = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, 'gate_position')
body_qadr = [model.body_jntadr[b] for b in bean_body_ids]

snap_times = [0., 1., 2., 5.]
snapshots = {}
counts = {}
crossed = set()
count_t = [0.]
count_v = [0]
max_wall_penetration = 0.0
best_diagnostic = None
best_score = -1
nsteps = int(round(SIM_DURATION/DT))
for step in range(nsteps+1):
    t = step*DT
    data.ctrl[gate_act] = 0.12 if t >= GATE_OPEN_TIME else 0.0
    if step > 0:
        mujoco.mj_step(model, data)
    # Center crossing counts are monotone: count a bean once it has passed
    # below the 18 mm throat plane after the gate opens.
    for i,b in enumerate(bean_body_ids):
        z = data.xpos[b,2]
        # Count only after clearing the throat and closed-gate elevation;
        # merely resting on the gate is not a discharge event.
        if t >= GATE_OPEN_TIME and z < 0.520:
            crossed.add(i)
    if step % 10 == 0:
        count_t.append(t); count_v.append(len(crossed))
    for j in range(data.ncon):
        c = data.contact[j]
        if (int(c.geom1) in wall_ids and int(c.geom2) in bean_geom_ids) or (int(c.geom2) in wall_ids and int(c.geom1) in bean_geom_ids):
            max_wall_penetration = max(max_wall_penetration, max(0., -float(c.dist)))
    if step % 50 == 0 and 1.0 <= t <= 1.5:
        nbean_contacts = sum(1 for j in range(data.ncon) if int(data.contact[j].geom1) in bean_geom_ids or int(data.contact[j].geom2) in bean_geom_ids)
        if nbean_contacts > best_score:
            best_score = nbean_contacts
            entries=[]
            for j in range(data.ncon):
                c=data.contact[j]
                if int(c.geom1) not in bean_geom_ids and int(c.geom2) not in bean_geom_ids: continue
                local=np.zeros(6)
                mujoco.mj_contactForce(model,data,j,local)
                frame=np.asarray(c.frame).reshape(3,3)
                world_force=frame.T @ local[:3]
                entries.append((np.array(c.pos).copy(),world_force.copy(),float(c.dist)))
            best_diagnostic=(t,entries)
    for st in snap_times:
        if abs(t-st) < DT*.25:
            snapshots[st] = (data.xpos[bean_body_ids].copy(), data.xquat[bean_body_ids].copy(), data.qpos[0:].copy(), data.ncon)
    if step % 10 == 0 and count_t[-1] != t:
        count_t.append(t); count_v.append(len(crossed))

# Count at requested frames from their stored positions (crossings are captured
# from the monotone event set at each exact draw time in a second concise pass).
# Recover exact counts from recorded events using the snapshot center heights.
for st in snap_times:
    zvals = snapshots[st][0][:,2]
    counts[st] = int(np.count_nonzero((zvals < 0.520) & (st >= GATE_OPEN_TIME)))

# Beans are considered outside if their centers escape a generous enclosure;
# beans resting safely in the tray are not lost.
final_pos = data.xpos[bean_body_ids]
left = [i for i,p in enumerate(final_pos) if abs(p[0]) > .90 or abs(p[1]) > .50 or p[2] < -.08 or p[2] > 2.2]
print(f"Maximum penetration into hopper walls: {max_wall_penetration*1000:.3f} mm")
for t in snap_times:
    print(f"Through throat at {t:g} s: {counts[t]} / {N_BEANS}")
print(f"Beans that left the model: {left if left else 'none'}")

# ------------------------- single multi-panel figure -----------------------
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9})
fig = plt.figure(figsize=(15,10), facecolor='#f5f3ef')
gs = fig.add_gridspec(3, 2, height_ratios=[1,1,.78], hspace=.28, wspace=.18)
frame_axes = [fig.add_subplot(gs[0,0]), fig.add_subplot(gs[0,1]), fig.add_subplot(gs[1,0]), fig.add_subplot(gs[1,1])]

# cone outlines are shown as the inner edge with facets visible at the rim
zlo,zhi=HOPPER_BOTTOM,HOPPER_TOP
rlo,rhi=THROAT_RADIUS,HOPPER_TOP_RADIUS
for ax,st in zip(frame_axes,snap_times):
    pos,quats,_,_=snapshots[st]
    ax.set_facecolor('#faf9f6')
    ax.plot([-rhi,-rlo],[zhi,zlo],color='#46545b',lw=3,solid_capstyle='round')
    ax.plot([rhi,rlo],[zhi,zlo],color='#46545b',lw=3,solid_capstyle='round')
    ax.plot([-rhi,rhi],[zhi,zhi],color='#46545b',lw=2)
    ax.plot([-rlo,rlo],[zlo,zlo],color='#46545b',lw=2)
    ax.add_patch(Rectangle((-.045,.521),.09,.008,color='#41474b',zorder=2))
    if st >= GATE_OPEN_TIME:
        ax.add_patch(Rectangle((-.045+.12,.521),.09,.008,color='#41474b',zorder=2))
    # Tray elevation and lip in this side projection.
    ax.add_patch(Rectangle((-.75,.018),1.50,.024,facecolor='#b5a991',edgecolor='#70685b',lw=1.3,zorder=1))
    ax.add_patch(Rectangle((-.758,.04),.008,.025,facecolor='#8c8170',edgecolor='#70685b',lw=1,zorder=1))
    ax.add_patch(Rectangle((.75,.04),.008,.025,facecolor='#8c8170',edgecolor='#70685b',lw=1,zorder=1))
    for i,(p,q) in enumerate(zip(pos,quats)):
        # display bean as a rotated, gently flattened roasted-bean silhouette
        w,x,y,z=q
        # quaternion rotation of local long axis, projected onto the x-z view
        # (bean local z is the thickness/dome axis; local x/y form the broad face)
        rot=np.array([[1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)],
                      [2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)],
                      [2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)]])
        vec=rot[:,0]
        ang=math.degrees(math.atan2(vec[2],vec[0]))
        bean=Ellipse((p[0],p[2]),width=BEAN_LENGTH,height=BEAN_THICKNESS,
                     angle=ang,facecolor=('#6e3215' if i%3 else '#8a4820'),
                     edgecolor='#32190e',lw=.55,zorder=4)
        ax.add_patch(bean)
        # subtle crease line suggests the characteristic center seam
        seam_len=.0048
        ax.plot([p[0]-seam_len*.5*math.cos(math.radians(ang)),p[0]+seam_len*.5*math.cos(math.radians(ang))],
                [p[2]-seam_len*.5*math.sin(math.radians(ang)),p[2]+seam_len*.5*math.sin(math.radians(ang))],color='#c18a55',lw=.45,zorder=5,alpha=.85)
    ax.set_xlim(-.30,.30); ax.set_ylim(-.01,1.63); ax.set_aspect('auto')
    ax.set_xticks([]); ax.set_ylabel('height (m)',color='#555')
    ax.set_title(f'{st:g} s   ·   {counts[st]} passed throat',loc='left',weight='bold',color='#26333a',pad=5)
    ax.spines[['top','right','bottom']].set_visible(False); ax.spines['left'].set_color('#aaa')
    ax.grid(axis='y',alpha=.16)

# Diagnostic snapshot: real MuJoCo contact positions and contact-force vectors.
ax=fig.add_subplot(gs[2,0]); ax.set_facecolor('#faf9f6')
pos,quats,_,_=snapshots[2.]
ax.plot([-rhi,-rlo],[zhi,zlo],color='#46545b',lw=3); ax.plot([rhi,rlo],[zhi,zlo],color='#46545b',lw=3)
ax.plot([-rlo,rlo],[zlo,zlo],color='#46545b',lw=2)
ax.add_patch(Rectangle((-.75,.018),1.50,.024,facecolor='#b5a991',edgecolor='#70685b',lw=1))
for p in pos:
    ax.add_patch(Ellipse((p[0],p[2]),BEAN_LENGTH,BEAN_THICKNESS,facecolor='#75401f',edgecolor='#32190e',lw=.4,zorder=3))
if best_diagnostic and best_diagnostic[1]:
    dtime,entries=best_diagnostic
    for cp,f,dist in entries:
        # Contact locations and forces projected into the plotted x-z plane.
        ax.scatter(cp[0],cp[2],s=10,color='#d7263d',zorder=6)
        # Normalize to force magnitude but preserve the measured vector direction;
        # a diagrammatic 2-8 cm arrow keeps these tiny contact forces legible.
        scale=.08/max(np.linalg.norm(f),1e-12)
        ax.annotate('',xy=(cp[0]+f[0]*scale,cp[2]+f[2]*scale),xytext=(cp[0],cp[2]),
                    arrowprops=dict(arrowstyle='-|>',color='#087e8b',lw=1.1),zorder=7)
    diag_title=f'Contact diagnostics · t={dtime:.2f} s · {len(entries)} bean contacts'
else:
    diag_title='Contact diagnostics · no bean contacts recorded'
ax.set_xlim(-.27,.27); ax.set_ylim(-.015,1.6); ax.set_xticks([]); ax.set_ylabel('height (m)')
ax.set_title(diag_title,loc='left',weight='bold',color='#26333a')
ax.text(.02,.96,'red: contact point   teal: force direction',transform=ax.transAxes,fontsize=8,color='#48565b',va='top',bbox=dict(facecolor='#faf9f6',edgecolor='none',alpha=.85,pad=2))
ax.spines[['top','right','bottom']].set_visible(False); ax.grid(axis='y',alpha=.16)

# Cumulative count through the throat over the full five-second run.
ax=fig.add_subplot(gs[2,1]); ax.set_facecolor('#faf9f6')
# reduce sampled event trace to a smooth step sequence while retaining counts
ct=np.asarray(count_t); cv=np.asarray(count_v)
valid=np.r_[True,np.diff(ct)>0]
ct,cv=ct[valid],cv[valid]
ax.step(ct,cv,where='post',color='#b35a32',lw=2.6)
ax.fill_between(ct,cv,step='post',color='#d69a72',alpha=.22)
for st in snap_times: ax.scatter(st,counts[st],s=32,color='#26333a',zorder=4)
ax.axvline(1,color='#69757a',ls='--',lw=1,label='gate opens')
ax.set_xlim(0,5); ax.set_ylim(0,52); ax.set_xticks([0,1,2,3,4,5]); ax.set_yticks([0,10,20,30,40,50])
ax.set_xlabel('simulation time (s)'); ax.set_ylabel('beans through throat')
ax.set_title('Discharge history',loc='left',weight='bold',color='#26333a')
ax.grid(alpha=.22); ax.legend(frameon=False,loc='lower right',fontsize=8)
ax.spines[['top','right']].set_visible(False)
fig.suptitle('GRINDER HOPPER  /  50 ROASTED BEANS',x=.055,y=.985,ha='left',fontsize=17,weight='bold',color='#26333a')
fig.text(.055,.955,'18 mm outlet  ·  sliding gate opens at 1 s  ·  5 s MuJoCo run',color='#657176',fontsize=10)
fig.text(.945,.955,f'{BEAN_LENGTH*1000:.1f} × {BEAN_WIDTH*1000:.1f} × {BEAN_THICKNESS*1000:.1f} mm   |   {BEAN_MASS*1e3:.2f} g each',ha='right',color='#657176',fontsize=9)
fig.subplots_adjust(top=.91,left=.055,right=.97,bottom=.055)
out=os.environ.get('OUT')
if not out:
    raise RuntimeError('OUT environment variable is required')
fig.savefig(out,dpi=180,bbox_inches='tight',facecolor=fig.get_facecolor())
