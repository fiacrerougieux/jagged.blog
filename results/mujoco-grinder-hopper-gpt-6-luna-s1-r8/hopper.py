#!/usr/bin/env python3
"""A small MuJoCo coffee-grinder hopper release experiment."""
from pathlib import Path
import os
import math
import numpy as np
import mujoco
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Circle, Rectangle

# SI units throughout.  Each coffee bean is a single free rigid body carrying
# two overlapping ellipsoids: a low, flattened underside and a larger dome.
N_BEANS = 50
BEAN_RADII = (0.0050, 0.0031, 0.0024)  # dome semi-axes (m), length/width/thickness
BEAN_MASS = 0.00012                    # 120 mg per roasted bean
FRICTION = (0.32, 0.008, 0.0001)      # sliding, torsional, rolling
DT = 0.001
SIM_TIME = 5.0
THROAT_RADIUS = 0.009                 # 18 mm clear diameter
GATE_Z = 0.285
TRAY_Z = 0.035

# Closely overlapping collision ribs form a conical shell without sealing its throat.
N_RIBS = 192
R_TOP, Z_TOP = 0.105, 0.82
R_BOTTOM, Z_BOTTOM = THROAT_RADIUS, 0.288
RIB_RAD = 0.0025

def v3(a):
    return ' '.join(f'{x:.8g}' for x in a)

world = []
world.append('<mujoco model="roasted_coffee_hopper"><compiler angle="radian" autolimits="true"/><option timestep="0.001" gravity="0 0 -9.81" integrator="implicitfast" cone="elliptic" iterations="80" tolerance="1e-10"/><size njmax="12000" nconmax="4000"/>')
# Mesh assets must precede worldbody in valid MJCF.
world.append('<default><geom condim="4" friction="0.32 0.008 0.0001" solref="0.004 1" solimp="0.95 0.99 0.001"/><joint damping="0.0004" armature="0.000002"/></default>')
world.append('<asset><material name="steel" rgba="0.38 0.44 0.49 1"/><material name="hopper" rgba="0.68 0.72 0.74 1"/><material name="gate" rgba="0.92 0.42 0.10 1"/></asset>')
world.append('<worldbody><light pos="0.3 -0.4 1.6" dir="-0.2 0.3 -1" diffuse="0.9 0.9 0.9"/><camera name="overview" pos="0.58 -1.08 1.18" xyaxes="0.88 0.48 0 -0.23 0.43 0.87" fovy="42"/>')
world.append(f'<geom name="tray" type="box" pos="0 0 {TRAY_Z-0.012:.6f}" size="0.24 0.18 0.012" material="steel"/>')
# Tray box already provides the catch surface; avoid a hidden, unbounded
# safety plane that could distract from the finite tray simulation.
# raised tray edges
for x in (-0.235,0.235):
    world.append(f'<geom type="box" pos="{x} 0 {TRAY_Z+0.012:.6f}" size="0.005 0.18 0.025" material="steel"/>')
for y in (-0.175,0.175):
    world.append(f'<geom type="box" pos="0 {y} {TRAY_Z+0.012:.6f}" size="0.24 0.005 0.025" material="steel"/>')
# Radial capsule ribs overlap around the circumference. Their centre-lines
# are offset by the capsule radius normal to the cone, preserving throat ID.
slope=(R_TOP-R_BOTTOM)/(Z_TOP-Z_BOTTOM)
radial_offset=RIB_RAD*math.sqrt(1+slope*slope)
for k in range(N_RIBS):
    a=2*math.pi*k/N_RIBS
    p1=np.array([(R_BOTTOM+radial_offset)*math.cos(a),(R_BOTTOM+radial_offset)*math.sin(a),Z_BOTTOM])
    p2=np.array([(R_TOP+radial_offset)*math.cos(a),(R_TOP+radial_offset)*math.sin(a),Z_TOP])
    world.append(f'<geom name="hopper_wall_{k:03d}" type="capsule" fromto="{v3(p1)} {v3(p2)}" size="{RIB_RAD}" material="hopper"/>')
# Sliding gate is a real joint with a position actuator. It blocks the throat
# until t=1s, then translates far enough to clear the falling beans.
world.append(f'<body name="sliding_gate" pos="0 0 {GATE_Z:.4f}"><joint name="gate_slide" type="slide" axis="1 0 0" range="0 0.120" limited="true" damping="0.08"/><geom name="gate_plate" type="box" pos="0 0 0" size="0.032 0.032 0.0025" material="gate" friction="0.08 0.005 0.0001"/></body>')
# Deterministic loose packing. Beans begin well above the 18 mm throat, within
# the hopper, in staggered layers so the closed gate catches the early flow.
rng=np.random.default_rng(27)
bean_positions=[]
for i in range(N_BEANS):
    # Interleaved layers, broad at the top and progressively narrower below.
    layer=i//10
    z=0.735-0.055*layer + rng.uniform(-0.012,0.012)
    local_r=R_BOTTOM+(R_TOP-R_BOTTOM)*(z-Z_BOTTOM)/(Z_TOP-Z_BOTTOM)-0.012
    rad=math.sqrt(rng.uniform(0,1))*max(0.008,local_r)
    ang=rng.uniform(0,2*math.pi)
    pos=np.array([rad*math.cos(ang),rad*math.sin(ang),z])
    bean_positions.append(pos)
    quat=rng.uniform(-1,1,4); quat=quat/np.linalg.norm(quat)
    world.append(f'<body name="bean_{i:02d}" pos="{v3(pos)}" quat="{v3(quat)}"><freejoint name="bean_free_{i:02d}"/>')
    # The lower ellipsoid creates the broad, flattened face; the shifted upper
    # ellipsoid forms the domed side. They overlap and move as one free body.
    world.append(f'<geom name="bean_flat_{i:02d}" type="ellipsoid" pos="0 0 -0.00045" size="0.0042 0.0029 0.0014" mass="{BEAN_MASS*0.34:.7g}" rgba="0.55 0.29 0.12 1" friction="0.32 0.008 0.0001"/>')
    world.append(f'<geom name="bean_dome_{i:02d}" type="ellipsoid" pos="0 0 0.00085" size="{BEAN_RADII[0]} {BEAN_RADII[1]} {BEAN_RADII[2]}" mass="{BEAN_MASS*0.66:.7g}" rgba="0.29 0.12 0.045 1" friction="0.32 0.008 0.0001"/>')
    world.append('</body>')
world.append('</worldbody><actuator><position name="gate_drive" joint="gate_slide" kp="20000" kv="80" ctrlrange="0 0.12"/></actuator>')
world.append('</mujoco>')
xml='\n'.join(world)
# Save beside the authored script when run normally; render executes a scratch
# copy, so also keep the requested deliverable at /work/model.xml.
script_dir=Path(__file__).resolve().parent
(script_dir/'model.xml').write_text(xml)
if Path('/work').is_dir(): Path('/work/model.xml').write_text(xml)
model=mujoco.MjModel.from_xml_string(xml)
data=mujoco.MjData(model)
mujoco.mj_forward(model,data)

# Sample exact simulation states and contact diagnostics.
snapshot_times=(0.,1.,2.,5.)
snapshots={}
counts={}
count_curve_t=[]; count_curve_n=[]
crossed=set(); max_wall_pen=0.0; diagnostic=None; escaped=set()
wall_ids={mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,f'hopper_wall_{k:03d}') for k in range(N_RIBS)}
bean_geom_owner={}
for i in range(N_BEANS):
    for tag in ('flat','dome'):
        gid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,f'bean_{tag}_{i:02d}')
        bean_geom_owner[gid]=i

def positions():
    return np.array([data.xpos[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,f'bean_{i:02d}')].copy() for i in range(N_BEANS)])

def collect_snapshot(t):
    snapshots[t]=positions()
    counts[t]=len(crossed)

for step in range(int(SIM_TIME/DT)+1):
    t=step*DT
    if abs(t-round(t,3))<1e-9:
        if any(abs(t-s)<DT/2 for s in snapshot_times):
            ts=min(snapshot_times,key=lambda s:abs(s-t))
            if ts not in snapshots: collect_snapshot(ts)
    # Open sharply at t=1.000 seconds.
    data.ctrl[0]=0.0 if t < 1.0 else 0.120
    if step < int(SIM_TIME/DT):
        mujoco.mj_step(model,data)
    p=positions()
    for i,pt in enumerate(p):
        # Count once the bean centre passes just below the gate plane; this
        # records actual passage rather than requiring it to reach the tray.
        if pt[2] < GATE_Z-0.007 and abs(pt[0]) < 0.08 and abs(pt[1]) < 0.08: crossed.add(i)
        if pt[2] < TRAY_Z-0.08 or abs(pt[0])>0.30 or abs(pt[1])>0.30 or pt[2]>1.2:
            escaped.add(i)
    # Contact distances are MuJoCo's signed separations (negative is overlap).
    for ci in range(data.ncon):
        c=data.contact[ci]
        if c.geom1 in wall_ids or c.geom2 in wall_ids:
            max_wall_pen=max(max_wall_pen,max(0.0,-float(c.dist)))
    if abs(t-2.0)<DT/2:
        records=[]
        for ci in range(data.ncon):
            c=data.contact[ci]
            f=np.zeros(6)
            mujoco.mj_contactForce(model,data,ci,f)
            # Keep bean contacts and all hopper/gate/tray contacts for display.
            records.append((c.pos.copy(),c.frame.copy(),f.copy(),c.geom1,c.geom2))
        diagnostic=records
    if step%10==0:
        count_curve_t.append(t); count_curve_n.append(len(crossed))
# assure end snapshot and robust count reporting
for st in snapshot_times:
    if st not in snapshots:
        # snapshots at exact time captured before the corresponding step
        data.time=st
        collect_snapshot(st)

# A clean multi-panel engineering illustration, with consistent side cutaway.
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':11})
fig=plt.figure(figsize=(15.2,10.2),facecolor='#f5f3ef')
gs=fig.add_gridspec(2,4,height_ratios=[1.28,1.0],hspace=.31,wspace=.22)
bean_colors=['#8b451f','#bd7941']

def draw_scene(ax, pts, title, label_count=None, contacts=False):
    ax.set_facecolor('#fbfaf7')
    # Hopper side cutaway outline is the true conical profile.
    ax.plot([-R_TOP,-R_BOTTOM],[Z_TOP,Z_BOTTOM],color='#44515a',lw=4,solid_capstyle='round',zorder=1)
    ax.plot([ R_TOP, R_BOTTOM],[Z_TOP,Z_BOTTOM],color='#44515a',lw=4,solid_capstyle='round',zorder=1)
    ax.plot([-R_TOP,R_TOP],[Z_TOP,Z_TOP],color='#44515a',lw=2,zorder=1)
    # small cylindrical throat / outlet lip
    ax.plot([-R_BOTTOM,-R_BOTTOM],[Z_BOTTOM,GATE_Z+0.005],color='#44515a',lw=3)
    ax.plot([R_BOTTOM,R_BOTTOM],[Z_BOTTOM,GATE_Z+0.005],color='#44515a',lw=3)
    # Gate positions from actuator at drawn time.
    gate_x=0 if title.startswith('0.0') or title.startswith('1.0') else .120
    ax.add_patch(Rectangle((gate_x-.032,GATE_Z-.0025),.064,.005,color='#ee771c',zorder=2))
    # tray plane and subtle side walls
    ax.add_patch(Rectangle((-.24,TRAY_Z-.012),.48,.012,color='#687982',zorder=0))
    ax.plot([-.235,-.235],[TRAY_Z,.075],color='#687982',lw=2)
    ax.plot([ .235, .235],[TRAY_Z,.075],color='#687982',lw=2)
    for i,p in enumerate(pts):
        if p[2] < -0.1 or p[2] > 1.0: continue
        # side projection of the 11.2 x 7 mm bean, giving recognizable roasted
        # ellipsoids and a visible lighter flattened underside highlight.
        # At this page scale true-sized 6 mm-high beans vanish; enlarge the
        # glyph for legibility while the parameter banner retains real size.
        body=Ellipse((p[0],p[2]),width=.016,height=.010,angle=0,
                     facecolor=bean_colors[i%2],edgecolor='#4a2818',lw=.35,zorder=3)
        ax.add_patch(body)
        ax.add_patch(Ellipse((p[0],p[2]-.0015),width=.012,height=.0035,
                             facecolor='#d2a06a',edgecolor='none',alpha=.8,zorder=4))
    ax.set_xlim(-.27,.27); ax.set_ylim(0,.90); ax.set_aspect('equal',adjustable='box')
    ax.set_title(title,loc='left',fontweight='bold',pad=8)
    ax.set_xlabel('x (m)'); ax.set_ylabel('height z (m)')
    ax.grid(axis='y',color='#dedbd5',lw=.5)
    if label_count is not None:
        ax.text(.98,.97,f'{label_count}/50 passed',transform=ax.transAxes,ha='right',va='top',
                color='#763d1d',fontweight='bold',bbox=dict(boxstyle='round,pad=.25',fc='#fff4e8',ec='#d9b08c'))

for j,t in enumerate(snapshot_times):
    ax=fig.add_subplot(gs[0,j])
    draw_scene(ax,snapshots[t],f'{t:.0f} s  |  gate '+('closed' if t<=1 else 'open'),counts[t])

# Diagnostic frame at 2 seconds with genuine MuJoCo contact locations and
# contact-force vectors in world coordinates, projected into x-z cutaway.
ax=fig.add_subplot(gs[1,0:2])
draw_scene(ax,snapshots[2.], '2 s diagnostic  |  contact points & forces', counts[2.])
if diagnostic:
    shown=0
    for pos,frame,force,g1,g2 in diagnostic:
        if shown>=45: break
        if pos[2]<0 or pos[2]>.9: continue
        # Contact frame's first axis is the contact normal; force[0] is normal
        # load in that frame. Scale arrows for visibility, not physical units.
        norm=frame[:3]
        vec=norm*force[0]
        if np.linalg.norm(vec)<1e-9: continue
        ax.scatter([pos[0]],[pos[2]],s=14,c='#13a6a1',edgecolors='white',linewidths=.35,zorder=7)
        ax.annotate('',xy=(pos[0]+vec[0]*.00035,pos[2]+vec[2]*.00035),xytext=(pos[0],pos[2]),
                    arrowprops=dict(arrowstyle='-|>',color='#d73536',lw=1.0,mutation_scale=8),zorder=8)
        shown+=1
ax.scatter([],[],s=20,c='#13a6a1',label='MuJoCo contact')
ax.plot([],[],color='#d73536',label='normal-force direction')
ax.legend(loc='upper left',fontsize=8,framealpha=.9)

ax2=fig.add_subplot(gs[1,2:4])
ax2.set_facecolor('#fbfaf7')
ax2.step(count_curve_t,count_curve_n,where='post',color='#994b22',lw=2.6)
ax2.fill_between(count_curve_t,count_curve_n,step='post',color='#d9945a',alpha=.2)
ax2.axvline(1,color='#ee771c',ls='--',lw=1.6,label='gate opens (1 s)')
for t in snapshot_times:
    ax2.scatter([t],[counts[t]],s=40,color='#39261b',zorder=4)
    ax2.annotate(str(counts[t]),(t,counts[t]),xytext=(4,8),textcoords='offset points',fontsize=9,fontweight='bold')
ax2.set_xlim(0,5); ax2.set_ylim(-1,52)
ax2.set_xticks(np.arange(0,5.1,.5)); ax2.set_yticks(np.arange(0,51,10))
ax2.grid(color='#dedbd5',lw=.6)
ax2.set_xlabel('simulation time (s)'); ax2.set_ylabel('unique beans below throat')
ax2.set_title('Beans through the throat over time',loc='left',fontweight='bold')
ax2.legend(loc='lower right',fontsize=8)
fig.suptitle('ROASTED COFFEE  |  50-bean grinder hopper release',x=.5,y=.98,fontsize=16,fontweight='bold',color='#38271c')
fig.text(.5,.947,'18 mm outlet  •  120 mg each  •  11.2 × 7.0 mm ellipsoid pair  •  μ = 0.65  •  Δt = 1 ms  •  5 s',ha='center',fontsize=9,color='#55504b')
fig.text(.015,.012,f'Max hopper-wall penetration: {max_wall_pen*1000:.3f} mm    |    Beans leaving model: {sorted(escaped) if escaped else "none"}',fontsize=8.5,color='#504b46')
fig.subplots_adjust(top=.91,bottom=.065,left=.055,right=.985)
out=os.environ.get('OUT','hopper.png')
fig.savefig(out,dpi=180,bbox_inches='tight',facecolor=fig.get_facecolor())
print(f'MuJoCo simulation: {SIM_TIME:.1f} s, {N_BEANS} beans; gate opens at 1.0 s.')
print(f'Bean semi-axes: {BEAN_RADII} m plus flattened ellipsoid; mass={BEAN_MASS*1000:.3f} g; friction={FRICTION}.')
print('Solver: implicitfast, timestep=0.001 s, 80 iterations, tolerance=1e-10, elliptic cone.')
print('Count through throat at drawn times: '+', '.join(f'{t:.0f}s={counts[t]}/50' for t in snapshot_times))
print(f'Maximum hopper-wall penetration: {max_wall_pen*1000:.6f} mm')
print('Beans that left the model: '+(', '.join(map(str,sorted(escaped))) if escaped else 'none'))
for st in snapshot_times:
    pp=snapshots[st]
    print(f'Diagnostic {st:.0f}s: z={pp[:,2].min():.4f}..{pp[:,2].max():.4f} m, xy span={np.ptp(pp[:,:2],axis=0)}; first={pp[0]}')
print(f'Gate slide qpos={data.qpos[0]:.4f} m.')
