"""50-bean hopper experiment. Run with MuJoCo, NumPy and Matplotlib.
All dynamics are SI; plotted dimensions are mm. No trajectories are prescribed.
"""
import os
from pathlib import Path
import numpy as np
import mujoco as mj
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
from matplotlib.patches import FancyArrowPatch

SEED = 24
N = 50
DT = 0.00025
rng = np.random.default_rng(SEED)
# The union is asymmetric: a full dome and a shallow overlapping underside.
SHAPES = [(np.array([0, 0, .0008]), np.array([.005, .003, .0019])),
          (np.array([0, 0, -.0010]), np.array([.0049, .0029, .00045]))]
parts = ['''<mujoco model="roasted_coffee_hopper">
<compiler angle="radian" autolimits="true"/>
<option timestep="0.00025" gravity="0 0 -9.81" integrator="implicitfast"
 solver="Newton" iterations="60" ls_iterations="20" tolerance="1e-9" cone="elliptic"/>
<size memory="128M"/>
<default><geom solref="0.001 1" solimp="0.95 0.99 0.001" friction="0.45 0.0001 0.00002" condim="4"/></default>
<asset>''']
wall_meshes = []
for section, lo, hi, rlo, rhi in [('cone', .085, .150, .009, .043), ('neck', .077, .085, .009, .009)]:
    for j in range(48):
        a, b = 2*np.pi*np.array([j, j+1])/48
        vs = []
        for thick in [0, .002]:
            for z, r in [(lo,rlo),(hi,rhi)]:
                for t in [a,b]:
                    rr = (r+thick)/np.cos(np.pi/48)
                    vs.append([rr*np.cos(t),rr*np.sin(t),z])
        name = f'{section}_{j}'
        parts.append(f'<mesh name="{name}" vertex="' + ' '.join(f'{v:.8f}' for v in np.ravel(vs)) + '"/>')
        wall_meshes.append(name)
parts.append('</asset><worldbody>')
for name in wall_meshes:
    parts.append(f'<geom name="wall_{name}" type="mesh" mesh="{name}" rgba="0.35 0.48 0.48 1" friction="0.30 0.0001 0.00002" priority="1"/>')
parts.append('''<geom name="tray" type="box" pos="0 0 -0.003" size="0.085 0.065 0.003" friction="0.5 0.0001 0.00002" priority="1"/>
<geom name="rim_xp" type="box" pos="0.086 0 0.004" size="0.001 0.067 0.007"/>
<geom name="rim_xm" type="box" pos="-0.086 0 0.004" size="0.001 0.067 0.007"/>
<geom name="rim_yp" type="box" pos="0 0.066 0.004" size="0.085 0.001 0.007"/>
<geom name="rim_ym" type="box" pos="0 -0.066 0.004" size="0.085 0.001 0.007"/>
<body name="gate" mocap="true" pos="0 0 0.0755">
<geom name="gate_plate" type="box" size="0.014 0.013 0.001" friction="0.3 0.0001 0.00002" priority="1"/>
</body>''')
centers = []
for z in [.108, .120, .132, .144]:
    radius = .009 + (z-.085)*(.034/.065)
    layer = [(x,y,z) for x in np.arange(-3,4)*.0115 for y in np.arange(-3,4)*.0115 if np.hypot(x,y)+.0055 < radius]
    rng.shuffle(layer)
    centers.extend(layer)
centers = centers[:N]
assert len(centers)==N
for i, pos in enumerate(centers):
    q = rng.normal(size=4); q /= np.linalg.norm(q)
    parts.append(f'<body name="bean_{i:02d}" pos="'+' '.join(map(str,pos))+'" quat="'+' '.join(map(str,q))+'"><freejoint/>')
    for k,(off, size) in enumerate(SHAPES):
        parts.append(f'<geom name="bean_{i:02d}_{k}" type="ellipsoid" pos="'+' '.join(map(str,off))+'" size="'+' '.join(map(str,size))+f'" mass="{.000096 if k==0 else .000024}" rgba="0.28 0.12 0.05 1"/>')
    parts.append('</body>')
parts.append('</worldbody></mujoco>')
xml = '\n'.join(parts)
Path(__file__).with_name('model.xml').write_text(xml)
# The render harness copies this script to a scratch directory. Keep the requested
# deliverable beside /work/hopper.py as well when running in that harness.
if Path('/work/hopper.py').exists() and Path(__file__).resolve().parent != Path('/work'):
    Path('/work/model.xml').write_text(xml)
model = mj.MjModel.from_xml_string(xml)
data = mj.MjData(model)
ids = np.array([mj.mj_name2id(model,mj.mjtObj.mjOBJ_BODY,f'bean_{i:02d}') for i in range(N)])
wall_ids = {mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,'wall_'+s) for s in wall_meshes}
geom_bean = {g: int(np.where(ids==model.geom_bodyid[g])[0][0]) for g in range(model.ngeom) if model.geom_bodyid[g] in ids}
mj.mj_forward(model,data)
first = np.full(N,np.nan)
gate_crossing = np.full(N,np.nan)
neck_at_one = None
max_pen = 0.; max_pen_t = 0.
escaped = {}
snapshots = {}
history_t = []; history_count = []
diagnostic = None; diagnostic_score = -1

def capture():
    return (data.xpos[ids].copy(), data.xmat[ids].reshape(N,3,3).copy(), data.mocap_pos[0,0])

for step in range(round(5/DT)+1):
    t = step*DT
    if not (np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all()):
        raise RuntimeError(f'Non-finite physics at {t:.6f} s')
    if step in [round(v/DT) for v in [0,1,2,5]]:
        snapshots[round(t)] = capture()
    if step == round(1/DT):
        p = data.xpos[ids]
        neck_at_one = int(np.sum((p[:,2] >= .077) & (p[:,2] <= .085) & (np.linalg.norm(p[:,:2],axis=1) < .009)))
    contacts = []
    for c in data.contact:
        b1 = geom_bean.get(c.geom1); b2 = geom_bean.get(c.geom2)
        if (c.geom1 in wall_ids or c.geom2 in wall_ids) and (b1 is not None or b2 is not None):
            if -c.dist > max_pen:
                max_pen = -c.dist; max_pen_t = t
    # Record a peak-active throat frame shortly after opening (not an invented force field).
    if 1.025 <= t <= 1.5 and step % 10 == 0:
        for ci,c in enumerate(data.contact):
            if c.pos[2] < .069 or c.pos[2] > .112:
                continue
            b1 = geom_bean.get(c.geom1); b2 = geom_bean.get(c.geom2)
            if b1 is None and b2 is None: continue
            f = np.zeros(6); mj.mj_contactForce(model,data,ci,f)
            force = c.frame.reshape(3,3).T @ f[:3]
            if b2 is None: force = -force
            if np.linalg.norm(force) > 1e-6:
                contacts.append((c.pos.copy(),force.copy()))
        if len(contacts)>diagnostic_score:
            diagnostic_score = len(contacts)
            diagnostic = (t,capture(),contacts)
    pos = data.xpos[ids]
    if step:
        crossing = (previous[:,2] >= .077) & (pos[:,2] < .077) & np.isnan(first)
        # Throat outlet disk; first downward body-origin crossing, no recrossing counts.
        crossing &= np.linalg.norm(pos[:,:2],axis=1) < .009
        frac = (previous[crossing,2]-.077)/(previous[crossing,2]-pos[crossing,2])
        first[crossing] = t-DT+frac*DT
        gc = (previous[:,2] >= .0755) & (pos[:,2] < .0755) & np.isnan(gate_crossing)
        gc &= np.linalg.norm(pos[:,:2],axis=1) < .009
        gate_crossing[gc] = t-DT + DT*(previous[gc,2]-.0755)/(previous[gc,2]-pos[gc,2])
    outside = (abs(pos[:,0]) > .100) | (abs(pos[:,1]) > .080) | (pos[:,2] < -.015) | (pos[:,2] > .200)
    for i in np.flatnonzero(outside): escaped.setdefault(int(i),t)
    history_t.append(t); history_count.append(np.isfinite(first).sum())
    previous = pos.copy()
    if step==round(5/DT): break
    u = np.clip((t+DT-1)/.12,0,1)
    data.mocap_pos[0,0] = .032*u*u*(3-2*u)
    mj.mj_step(model,data)
    mj.mj_forward(model,data)

print('Bean envelope 10 × 6 × 4.15 mm; mass 0.120 g each (96 + 24 mg).')
print('Two overlapping ellipsoids: shallow underside approximates a flat face; it is not exactly planar.')
print('Friction (sliding, torsional, rolling): bean .45, .0001 m, .00002 m; wall/gate .30; tray .50 (priority 1). condim=4; rolling coefficient inactive.')
print('Solver: Newton / elliptic, implicitfast, dt=0.25 ms, 60 iterations, tolerance=1e-9; solref=(.001,1), solimp=(.95,.99,.001).')
print(f'Maximum bean–hopper wall penetration: {max_pen*1000:.4f} mm at {max_pen_t:.4f} s (negative contact distance).')
for t in [0,1,2,5]: print(f'Through throat at {t} s: {np.sum(first<=t)}/50')
print('Beans that left model bounds (x±100, y±80, z−15…200 mm): '+(str(escaped) if escaped else 'none'))
print('MJCF: '+str(Path(__file__).with_name('model.xml')))
print(f'Validation: finite qpos/qvel at all {len(history_t)} samples; MuJoCo warning counts: {[int(w.number) for w in data.warning]}')
print(f'Bean origins inside neck at 1 s (z=77–85 mm, r<9 mm): {neck_at_one}')
print(f'First downward gate-plane crossings (z=75.5 mm, r<9 mm): {np.isfinite(gate_crossing).sum()}/50; before opening: {np.sum(gate_crossing < 1)}')
print('Gate x at drawn times / mm: '+str({t: round(snapshots[t][2]*1000,3) for t in [0,1,2,5]}))
valid = first[np.isfinite(first)]
if len(valid)>1:
    duration = valid.max()-valid.min()
    print(f'Outlet crossings span {valid.min():.4f}–{valid.max():.4f} s; mean event rate {(len(valid)-1)/duration:.1f} beans/s across that interval.')
# Hand-checkable capacity bound: sum of constituent volumes overestimates
# bean union volume because the two ellipsoids overlap.
bean_volume_upper = sum(4*np.pi/3*np.prod(s) for o,s in SHAPES)
hopper_volume = np.pi*.065/3*(.043**2+.043*.009+.009**2) + np.pi*.009**2*.008
print(f'Packing check: summed ellipsoid volumes ≤ {bean_volume_upper*1e9:.1f} mm³/bean; hopper capacity {hopper_volume*1e6:.1f} cm³; initial whole-hopper solid fraction ≤ {N*bean_volume_upper/hopper_volume:.3f} (not settled-bed packing).')
print('Geometry check: 18 mm throat spans 1.8 bean lengths or 3 bean widths; no geometric guarantee against bridging.')

# Scientific illustration: orthographic projections of actual simulated ellipsoid
# meshes; translucent hopper is intentionally cut away to expose all 50 bodies.
BG='#f6f2e9'; INK='#292d2b'; MUTED='#687771'; TEAL='#236b69'; ORANGE='#bf612e'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':INK,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,'axes.edgecolor':'#bac3ba'})
fig = plt.figure(figsize=(16,11),facecolor=BG)
fig.text(.045,.952,'GRAVITY / COFFEE',fontsize=12,color=TEAL,weight='bold',ha='left')
fig.text(.045,.908,'50 beans. One 18 mm throat.',fontsize=30,weight='bold')
fig.text(.955,.945,'MUJOCO  /  5.0 s',ha='right',fontsize=13,weight='bold')
fig.text(.955,.919,'Seed 24   •   SI dynamics   •   cutaway views',ha='right',fontsize=10,color=MUTED)
fig.text(.045,.872,'A sliding plate holds the charge until 1.00 s; it retracts 32 mm in 120 ms. No shaking, inflow or prescribed bean motion.',fontsize=11,color=MUTED)
# Camera right, up. Small elevation reveals tray and domes without hiding neck.
az=.35; el=.15
RIGHT=np.array([np.cos(az),np.sin(az),0]); UP=np.array([-np.sin(az)*np.sin(el),np.cos(az)*np.sin(el),np.cos(el)])
VIEW=np.cross(RIGHT,UP)
def project(p): return np.stack([np.asarray(p)@RIGHT,np.asarray(p)@UP],axis=-1)*1000
phis=np.linspace(0,2*np.pi,17); ths=np.linspace(0,np.pi,10)
verts=np.array([[np.sin(th)*np.cos(ph),np.sin(th)*np.sin(ph),np.cos(th)] for th in ths for ph in phis])
faces=np.array([[a*17+b,a*17+b+1,(a+1)*17+b+1,(a+1)*17+b] for a in range(9) for b in range(16)])
light=np.array([-.4,-.5,1]); light/=np.linalg.norm(light)

def bean_polygons(ax,snap):
    positions,rots,_=snap; polygons=[]; colors=[]; depths=[]
    for i,(p,r) in enumerate(zip(positions,rots)):
        base=np.array([.33,.16,.073])*(.89+.20*(i%7)/6)
        for off,sz in SHAPES:
            local=verts*sz+off
            world=local@r.T+p
            for face in faces:
                w=world[face]; normal=((verts[face].mean(axis=0)/sz)@r.T); normal/=np.linalg.norm(normal)
                shade=.66+.40*max(0,normal@light)
                polygons.append(project(w)); colors.append(np.clip(base*shade,0,1)); depths.append(w.mean(axis=0)@VIEW)
    order=np.argsort(depths)
    ax.add_collection(PolyCollection([polygons[k] for k in order],facecolors=[colors[k] for k in order],edgecolors='none',zorder=3))

def wire(ax,pts,**kw):
    q=project(np.asarray(pts)); ax.plot(q[:,0],q[:,1],**kw)
def scene(ax,snap,zoom=False):
    ax.set_facecolor(BG)
    # Cone silhouette and rings; intentionally non-occluding shell.
    theta=np.linspace(0,2*np.pi,97)
    for z,r in [(.150,.043),(.085,.009),(.077,.009)]:
        wire(ax,np.c_[r*np.cos(theta),r*np.sin(theta),np.full(len(theta),z)],color=TEAL,lw=1,alpha=.7,zorder=4)
    for a in np.linspace(0,2*np.pi,13)[:-1]:
        wire(ax,[[.043*np.cos(a),.043*np.sin(a),.150],[.009*np.cos(a),.009*np.sin(a),.085],[.009*np.cos(a),.009*np.sin(a),.077]],color=TEAL,lw=.65,alpha=.25,zorder=2)
    for sign in [-1,1]:
        # outer contour in camera horizontal direction
        points=[sign*.043*RIGHT+np.array([0,0,.150]),sign*.009*RIGHT+np.array([0,0,.085]),sign*.009*RIGHT+np.array([0,0,.077])]
        wire(ax,points,color=TEAL,lw=1.4,zorder=4)
    tray=np.array([[-.085,-.065,0],[.085,-.065,0],[.085,.065,0],[-.085,.065,0]])
    ax.add_collection(PolyCollection([project(tray)],facecolor='#e4e5dc',edgecolor='#82958a',lw=1,zorder=0))
    for i in range(4):
        wire(ax,[tray[i]+[0,0,.011],tray[(i+1)%4]+[0,0,.011]],color='#82958a',lw=.75,zorder=1)
    x=snap[2]
    gate=np.array([[x-.014,-.013,.0765],[x+.014,-.013,.0765],[x+.014,.013,.0765],[x-.014,.013,.0765]])
    ax.add_collection(PolyCollection([project(gate)],facecolor=ORANGE,edgecolor='#833d1d',lw=.8,zorder=2))
    bean_polygons(ax,snap)
    ax.set_aspect('equal'); ax.set_xlim((-32,55) if zoom else (-108,108)); ax.set_ylim((67,115) if zoom else (-20,164))
    ax.set_axis_off()

for idx,t in enumerate([0,1,2,5]):
    left=.043+idx*.237
    ax=fig.add_axes([left,.47,.219,.352])
    scene(ax,snapshots[t])
    # Use a narrower horizontal window: tray extends nearly the full panel.
    ax.set_xlim(-102,102)
    fig.text(left,.825,f'{t:.0f}.00 s',fontsize=17,weight='bold')
    fig.text(left+.21,.829,f'{np.sum(first<=t):02d} / 50 passed',ha='right',color=TEAL,fontsize=10,weight='bold')
    subtitle=['Initial charge','Gate starts opening','Discharged onto tray','Final state'][idx]
    fig.text(left,.796,subtitle,fontsize=10,color=MUTED)
    if idx==0:
        ax.annotate('18 mm',xy=(0,84),xytext=(-68,67),color=TEAL,fontsize=9,arrowprops={'arrowstyle':'-','color':TEAL,'lw':.8})
        ax.text(-96,-19,'170 × 130 mm tray',fontsize=8,color=MUTED)
    if idx==1:
        ax.annotate('slide →',xy=(7,75),xytext=(25,54),color=ORANGE,fontsize=9,arrowprops={'arrowstyle':'-','color':ORANGE,'lw':.8})
# separator
fig.add_artist(plt.Line2D([.045,.955],[.464,.464],transform=fig.transFigure,color='#cdd2c7',lw=1))
fig.text(.045,.429,'CONTACT AUDIT',fontsize=12,color=TEAL,weight='bold')
fig.text(.545,.429,'DISCHARGE HISTORY',fontsize=12,color=TEAL,weight='bold')
dt,ds,cs=diagnostic
ax=fig.add_axes([.042,.208,.455,.197]); scene(ax,ds,True)
# Full resolved force (normal + tangential), on a bean; one vector/contact.
force_scale=1600 # plot mm per newton; no normalization or clipping
strongest = set(np.argsort([np.linalg.norm(f) for p,f in cs])[-24:])
for ci,(p,f) in enumerate(cs):
    q=project(p); vec=np.array([f@RIGHT,f@UP])*force_scale
    ax.scatter(*q,s=5,color=ORANGE,zorder=6,edgecolor=BG,linewidth=.2)
    if ci in strongest:
        ax.annotate('',xy=q+vec,xytext=q,arrowprops={'arrowstyle':'-|>','color':'#db762d','lw':1.1,'mutation_scale':8},zorder=7)
ax.annotate('',xy=(38,109),xytext=(30,109),arrowprops={'arrowstyle':'-|>','color':ORANGE,'lw':1.1,'mutation_scale':8})
ax.text(34,111,'5 mN',ha='center',fontsize=8,color=ORANGE)
fig.text(.045,.185,f'{dt:.3f} s  ·  {len(cs)} loaded contacts near the throat',fontsize=10,weight='bold')
fig.text(.045,.163,'All contact points; 24 strongest forces on beans shown as scaled arrows.',fontsize=9,color=MUTED)
fig.text(.045,.140,f'Max wall penetration  {max_pen*1000:.3f} mm   |   Escaped  {len(escaped)} / 50',fontsize=10,color=TEAL,weight='bold')
axh=fig.add_axes([.565,.208,.38,.191],facecolor=BG)
axh.axvspan(1,1.12,color=ORANGE,alpha=.14,lw=0)
axh.step(history_t,history_count,where='post',color=TEAL,lw=2)
axh.set_xlim(0,5); axh.set_ylim(-1,53); axh.set_xticks(range(6)); axh.set_yticks([0,10,20,30,40,50]); axh.grid(axis='y',color='#d9ded3',lw=.65)
axh.spines[['top','right']].set_visible(False)
axh.set_ylabel('Unique beans passed',fontsize=9); axh.set_xlabel('Time / s',fontsize=9)
for t in [0,1,2,5]: axh.plot(t,np.sum(first<=t),'o',ms=4,color=TEAL,clip_on=False)
axh.text(1.15,45,'gate travel',fontsize=8,color=ORANGE)
fig.text(.545,.149,'Count = first downward origin crossing at z = 77 mm, within r < 9 mm.',fontsize=9,color=MUTED)
fig.text(.545,.130,'A bean is counted once; crossing is not a claim of full-body clearance.',fontsize=9,color=MUTED)
fig.add_artist(plt.Line2D([.045,.955],[.111,.111],transform=fig.transFigure,color='#cdd2c7',lw=1))
fig.text(.045,.087,'BEANS',fontsize=9,color=TEAL,weight='bold')
fig.text(.102,.087,'10 × 6 × 4.15 mm · 0.120 g each · 2 overlapping ellipsoids/free body · shallow underside, not a truly planar face',fontsize=9)
fig.text(.045,.066,'CONTACT',fontsize=9,color=TEAL,weight='bold')
fig.text(.102,.066,'μ = 0.45 bean / 0.30 wall & gate / 0.50 tray · torsion 0.10 mm · condim 4 · solref 1 ms, ζ = 1',fontsize=9)
fig.text(.045,.045,'SOLVER',fontsize=9,color=TEAL,weight='bold')
fig.text(.102,.045,'Newton, 60 iterations, 10⁻⁹ tolerance · elliptic cone · implicitfast, Δt = 0.25 ms · 48 facets · gravity 9.81 m/s²',fontsize=9)
fig.savefig(os.environ['OUT'],dpi=160,facecolor=BG)
plt.close(fig)
