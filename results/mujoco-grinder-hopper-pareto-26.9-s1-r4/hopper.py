"""Coffee hopper: SI-unit MuJoCo simulation and a reproducible figure.
Run with /opt/checkenv/bin/python3 hopper.py (OUT is the output PNG).
Two ellipsoids approximate a flattened underside; no ellipsoid has a truly planar face.
"""
from pathlib import Path
import os
import numpy as np
import mujoco
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Polygon, Rectangle, Ellipse

SEED = 41
DT = 0.0005
rng = np.random.default_rng(SEED)
# 10 x 6.5 x 4.55 mm compound beans; 0.130 g each.
PARTS = [(np.array([0., 0., .0008]), np.array([.005, .00325, .0022]), .000105),
         (np.array([0., 0., -.00105]), np.array([.0048, .0031, .0005]), .000025)]
NSECT = 40
assets, walls = [], []
# Individually convex, adjoining trapezoidal sectors: a non-convex hollow hopper.
for section, zlo, zhi, rlo, rhi in [('cone', .055, .115, .009, .038),
                                      ('neck', .049, .055, .009, .009)]:
    for i in range(NSECT):
        a, b = 2*np.pi*np.array([i, i+1])/NSECT
        verts = []
        for z, r in [(zlo,rlo),(zhi,rhi)]:
            for rr in [r, r+.0025]:
                for t in [a,b]:
                    verts.extend([rr*np.cos(t),rr*np.sin(t),z])
        name = f'{section}_{i}'
        assets.append(f'<mesh name="{name}" vertex="'+ ' '.join(f'{v:.9f}' for v in verts)+'"/>')
        walls.append(f'<geom name="wall_{name}" type="mesh" mesh="{name}" friction="0.32 0.0001 0.00002" rgba="0.5 0.65 0.65 0.35"/>')
# Nonintersecting starting lattice. All bounding spheres are inside the cone.
positions = []
for z in [.070, .080, .090, .100, .110]:
    rad = .009+(z-.055)*(.029/.060)-.006
    layer = []
    for j in range(-3,4):
        for i in range(-3,4):
            x = (i+.5*(j%2))*.011
            y = j*.0096
            if x*x+y*y < rad*rad:
                layer.append([x,y,z])
    rng.shuffle(layer)
    positions.extend(layer)
positions = positions[:50]
assert len(positions)==50
beans = []
for i,p in enumerate(positions):
    # Random yaw with a modest initial tilt, rather than coincident or penetrating seeds.
    yaw = rng.uniform(-np.pi,np.pi)
    tilt = rng.uniform(-.35,.35)
    quat = [np.cos(yaw/2)*np.cos(tilt/2), -np.sin(yaw/2)*np.sin(tilt/2),
            np.cos(yaw/2)*np.sin(tilt/2), np.sin(yaw/2)*np.cos(tilt/2)]
    gs = ''.join(f'<geom name="bean_{i:02d}_{j}" type="ellipsoid" pos="'+
                 ' '.join(map(str,off))+'" size="'+' '.join(map(str,size))+
                 f'" mass="{mass}" friction="0.48 0.00015 0.00003" rgba="0.3 0.12 0.05 1"/>'
                 for j,(off,size,mass) in enumerate(PARTS))
    beans.append(f'<body name="bean_{i:02d}" pos="'+ ' '.join(map(str,p))+'" quat="'+
                 ' '.join(map(str,quat))+f'"><freejoint/>{gs}</body>')
xml = f'''<mujoco model="50 roasted beans / 18 mm hopper">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="{DT}" gravity="0 0 -9.81" integrator="implicitfast"
          solver="Newton" iterations="60" tolerance="1e-10" cone="elliptic"/>
  <size njmax="6000" nconmax="2000"/>
  <default><geom condim="4" solref="0.003 1" solimp="0.95 0.99 0.0001" margin="0"/></default>
  <asset>{''.join(assets)}</asset>
  <worldbody>
    <light pos="0 -0.1 0.3"/>
    {''.join(walls)}
    <geom name="tray" type="box" pos="0 0 0" size="0.100 0.085 0.002" friction="0.5 0.00015 0.00003"/>
    <geom name="tray_xp" type="box" pos="0.101 0 0.007" size="0.001 0.087 0.009"/>
    <geom name="tray_xm" type="box" pos="-0.101 0 0.007" size="0.001 0.087 0.009"/>
    <geom name="tray_yp" type="box" pos="0 0.086 0.007" size="0.100 0.001 0.009"/>
    <geom name="tray_ym" type="box" pos="0 -0.086 0.007" size="0.100 0.001 0.009"/>
    <body name="gate" mocap="true" pos="0 0 0.0478">
      <geom name="gate_geom" type="box" size="0.022 0.024 0.0012" friction="0.3 0.0001 0.00002"/>
    </body>
    {''.join(beans)}
  </worldbody>
</mujoco>'''
path = Path(__file__).resolve().with_name('model.xml')
path.write_text(xml)
# The render harness runs a copy in a temporary directory; also retain the deliverable.
if Path('/work/hopper.py').is_file() and path != Path('/work/model.xml'):
    Path('/work/model.xml').write_text(xml)
m = mujoco.MjModel.from_xml_string(xml)
d = mujoco.MjData(m)
ids = np.array([mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_BODY,f'bean_{i:02d}') for i in range(50)])
wall_ids = {i for i in range(m.ngeom) if (mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,i) or '').startswith('wall_')}
bean_ids = set(ids.tolist())
gate_id = mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_GEOM,'gate_geom')
mujoco.mj_forward(m,d)

def state():
    return (d.xpos[ids].copy()*1000, d.xmat[ids].copy().reshape(-1,3,3), float(d.mocap_pos[0,0])*1000)

snapshots = {0:state()}
passed = np.zeros(50,dtype=bool)
counts_at = {0:0}
times, counts = [0.], [0]
max_pen = 0.
escaped = {}
diag, best = None, -1
prev = d.xipos[ids].copy()
for step in range(1,round(5/DT)+1):
    t = (step-1)*DT
    # Prescribed linear slide: starts at 1.000 s, fully clear at 1.150 s.
    d.mocap_pos[0,0] = .055*np.clip((t-1)/.15,0,1)
    mujoco.mj_step(m,d)
    # Forward makes snapshots and contact forces refer to the same post-step state.
    mujoco.mj_forward(m,d)
    now = d.xipos[ids].copy()
    crossing = (prev[:,2]>=.049)&(now[:,2]<.049)&(~passed)
    for i in np.flatnonzero(crossing):
        f = (prev[i,2]-.049)/(prev[i,2]-now[i,2])
        point = prev[i]+f*(now[i]-prev[i])
        if np.linalg.norm(point[:2]) <= .009:
            passed[i] = True
    prev = now
    outside = (np.abs(now[:,0])>.108)|(np.abs(now[:,1])>.094)|(now[:,2]<-.010)|(now[:,2]>.17)
    for i in np.flatnonzero(outside):
        escaped.setdefault(int(i),float(d.time))
    for c in d.contact:
        if ((int(c.geom1) in wall_ids and int(m.geom_bodyid[c.geom2]) in bean_ids) or
            (int(c.geom2) in wall_ids and int(m.geom_bodyid[c.geom1]) in bean_ids)):
            max_pen = max(max_pen, -float(c.dist))
    if step%20==0:
        times.append(float(d.time)); counts.append(int(passed.sum()))
    if step in [2000,4000,10000]:
        key = round(step*DT)
        snapshots[key] = state(); counts_at[key] = int(passed.sum())
    if 1.05 <= d.time <= 1.8 and step%20==0:
        contacts = []
        for k,c in enumerate(d.contact):
            if .043 < c.pos[2] < .073 and abs(c.pos[0])<.030 and abs(c.pos[1])<.003:
                if int(m.geom_bodyid[c.geom1]) not in bean_ids and int(m.geom_bodyid[c.geom2]) not in bean_ids:
                    continue
                force = np.zeros(6)
                mujoco.mj_contactForce(m,d,k,force)
                if force[0]>.00003:
                    contacts.append((c.pos.copy()*1000,c.frame.reshape(3,3).T@force[:3]))
        score = len(contacts)
        if score > best:
            best=score; diag=(float(d.time),state(),contacts)

print('MuJoCo',mujoco.__version__, '| 50 free bodies; 100 overlapping ellipsoid geoms; seed',SEED)
print('Bean envelope: 10 x 6.5 x 4.55 mm; mass 0.130 g. Underside is flattened, not exactly planar.')
print('Friction [sliding, torsional m, rolling m]: beans [0.48, 0.00015, 0.00003]; walls [0.32, 0.0001, 0.00002]. condim=4 (rolling inactive).')
print(f'Solver: Newton, 60 iterations, tol 1e-10; elliptic cone; implicitfast; dt={DT:g} s; solref=[0.003,1]; solimp=[0.95,0.99,0.0001].')
print(f'Maximum bean–hopper-wall contact penetration, all 5 s: {max_pen*1000:.4f} mm')
for t in [0,1,2,5]: print(f'Throat count at {t} s: {counts_at[t]}/50 (first downward COM crossing z=49 mm within r=9 mm)')
print('Beans that left model containment:', ', '.join(f'bean_{i:02d} at {t:.4f} s' for i,t in escaped.items()) if escaped else 'none')
print('MJCF written to',path,'and retained at /work/model.xml when running in the harness.')

# Plot actual simulation geometry with a cutaway shell; SI -> millimetres only for display.
BG='#f4f1ea'; INK='#223b40'; MUTED='#627477'; TEAL='#087e83'; COPPER='#ae663d'; RED='#c64e38'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':INK,
                     'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED})
fig = plt.figure(figsize=(16,11),facecolor=BG)
fig.text(.045,.951,'GRAVITY / GRANULAR FLOW',fontsize=11,color=TEAL,weight='bold',va='top')
fig.text(.045,.916,'Fifty beans. One 18 mm throat.',fontsize=28,weight='bold',va='top')
fig.text(.045,.865,'MuJoCo 3.13  /  5 s physical simulation  /  front cutaway · orthographic projection',fontsize=11,color=MUTED)
fig.text(.955,.939,'COFFEE LAB\n01 / HOPPER RELEASE',ha='right',va='top',fontsize=10,color=MUTED,linespacing=1.6)
# Bean surfaces are tessellated only for drawing, never for collision detection.
u=np.linspace(0,2*np.pi,17); v=np.linspace(0,np.pi,10)
unit=np.stack([np.outer(np.cos(u),np.sin(v)),np.outer(np.sin(u),np.sin(v)),np.outer(np.ones_like(u),np.cos(v))],axis=-1)
faces=[]
for i in range(len(u)-1):
    for j in range(len(v)-1): faces.append([(i,j),(i+1,j),(i+1,j+1),(i,j+1)])
light=np.array([-.5,-.7,.6]); light/=np.linalg.norm(light)

def draw_beans(ax,s,zoom=False):
    pos,rots,gx=s
    polygons=[]; colors=[]; depths=[]
    for n,(p,R) in enumerate(zip(pos,rots)):
        if zoom and not (30<p[2]<89): continue
        base=np.array([.39,.205,.112])*(.86+.25*((n*7)%13)/12)
        for off,size,mass in PARTS:
            xyz=(unit*size)@R.T*1000+(p+(R@off)*1000)
            for face in faces:
                pts=np.array([xyz[i,j] for i,j in face])
                mid=np.mean([unit[i,j] for i,j in face],axis=0)
                normal=(mid/size)@R.T; normal/=max(np.linalg.norm(normal),1e-12)
                shade=.55+.45*max(0,np.dot(normal,light))
                polygons.append(pts[:,[0,2]]); colors.append(np.clip(base*shade+0.03,0,1)); depths.append(pts[:,1].mean())
    order=np.argsort(depths)[::-1]
    ax.add_collection(PolyCollection([polygons[i] for i in order],facecolors=[colors[i] for i in order],edgecolors='none',zorder=3))

def shell(ax,s,zoom=False):
    # The visible side outline is the true internal cone plus 2.5 mm wall thickness.
    for sign in [-1,1]:
        pp=np.array([[9,49],[9,55],[38,115],[40.5,115],[11.5,55],[11.5,49]])
        pp[:,0]*=sign
        ax.add_patch(Polygon(pp,fc='#ccd9d6',ec='#65827e',lw=1.1,zorder=4))
    if not zoom:
        ax.add_patch(Polygon([[-38,115],[-9,55],[9,55],[38,115]],fc='#dce6df',alpha=.35,ec='none',zorder=0))
        ax.plot([-38,38],[115,115],color='#91a7a1',lw=.8,ls=(0,(3,3)))
        ax.add_patch(Rectangle((-102,-2),204,4,fc='#bbc9c4',ec='#65827e',lw=1,zorder=2))
        for x in [-102,100]: ax.add_patch(Rectangle((x,-2),2,18,fc='#bbc9c4',ec='#65827e',lw=1,zorder=4))
    gx=s[2]
    ax.add_patch(Rectangle((gx-22,46.6),44,2.4,fc=TEAL,ec=INK,lw=.5,zorder=5))
    ax.plot([-9,9],[49,49],color=RED,lw=1,ls=(0,(3,2)),zorder=6)

axes=[]
for k,t in enumerate([0,1,2,5]):
    ax=fig.add_axes([.045+k*.238,.47,.222,.34])
    axes.append(ax)
    ax.set_facecolor(BG); shell(ax,snapshots[t]); draw_beans(ax,snapshots[t])
    ax.set_xlim(-106,106); ax.set_ylim(-8,125); ax.set_aspect('equal'); ax.axis('off')
    ax.text(0,1.17,f'{t:.0f}.00 s',transform=ax.transAxes,fontsize=18,weight='bold')
    status=['Loaded · gate closed','Settled · opening begins','Gate fully open','End of run'][k]
    ax.text(0,1.055,status,transform=ax.transAxes,fontsize=10,color=MUTED)
    ax.text(0,-.13,f'{counts_at[t]:02d} / 50',transform=ax.transAxes,fontsize=19,color=TEAL,weight='bold')
    ax.text(.45,-.115,'through throat',transform=ax.transAxes,fontsize=10,color=MUTED)
# Dimension marks in the first physical snapshot.
a=axes[0]
a.plot([-9,9],[39,39],color=INK,lw=.8)
a.plot([-9,-9],[37,41],color=INK,lw=.8)
a.plot([9,9],[37,41],color=INK,lw=.8)
a.text(0,30,'18 mm',ha='center',fontsize=8)
a.text(-95,4,'tray',fontsize=8,color=MUTED,va='bottom')
a.plot([-95,-75],[23,23],color=INK,lw=1.5); a.text(-85,26,'20 mm',ha='center',fontsize=7,color=MUTED)

# Bottom row: close-up contact audit, cumulative first-passage count, assumptions.
fig.text(.045,.434,'01  /  CONTACT AUDIT',fontsize=11,color=TEAL,weight='bold')
fig.text(.365,.434,'02  /  THROUGHPUT',fontsize=11,color=TEAL,weight='bold')
fig.text(.72,.434,'03  /  MODEL CARD',fontsize=11,color=TEAL,weight='bold')
ax=fig.add_axes([.045,.163,.28,.235]); ax.set_facecolor('#e7ebe4')
tdiag,s,contacts=diag
shell(ax,s,True); draw_beans(ax,s,True)
# Force acts on geom2; physical N -> graphical mm, identical scale for all vectors.
for p,f in contacts:
    ax.plot(p[0],p[2],'.',color='#08a8b0',ms=4,zorder=7)
    ff=f[[0,2]]*800
    ax.annotate('',xy=p[[0,2]]+ff,xytext=p[[0,2]],arrowprops={'arrowstyle':'-|>','color':RED,'lw':.75,'mutation_scale':7},zorder=8)
ax.set_xlim(-28,28); ax.set_ylim(39,79); ax.set_aspect('equal')
ax.set_xticks([-20,0,20]); ax.set_yticks([40,60,80]); ax.tick_params(labelsize=8,length=2)
for sp in ax.spines.values(): sp.set_color('#c1ccc4')
ax.set_xlabel('x / mm',fontsize=9,labelpad=2); ax.set_ylabel('z / mm',fontsize=9,labelpad=2)
ax.text(.03,.96,f't = {tdiag:.2f} s  ·  {len(contacts)} contacts',transform=ax.transAxes,fontsize=9,va='top',zorder=20,bbox={'fc':BG,'ec':'none','alpha':.95})
fig.text(.045,.113,'● contact point',fontsize=9,color=TEAL)
fig.text(.135,.113,'→ force on geom 2',fontsize=9,color=RED)
fig.text(.045,.089,'6 mm depth slice; x–z forces. Scale: 5 mN = 4 mm.',fontsize=8,color=MUTED)

ax=fig.add_axes([.365,.184,.302,.207],facecolor=BG)
ax.axvspan(1,1.15,color=TEAL,alpha=.12,lw=0)
ax.step(times,counts,where='post',color=TEAL,lw=2.2)
ax.axvline(1,color=TEAL,lw=.8,ls='--')
for t in [0,1,2,5]:
    ax.plot(t,counts_at[t],'o',ms=5,color=TEAL,clip_on=False)
    ax.annotate(str(counts_at[t]),(t,counts_at[t]),xytext=(5,8 if counts_at[t]<45 else -17),textcoords='offset points',fontsize=9,color=TEAL)
ax.set_xlim(0,5); ax.set_ylim(0,53); ax.set_xticks(range(6)); ax.set_yticks([0,10,20,30,40,50]); ax.tick_params(length=0,labelsize=9)
ax.set_xlabel('Time / s',fontsize=10); ax.set_ylabel('Unique beans',fontsize=10)
ax.grid(axis='y',color='#d9ded6',lw=.7); ax.set_axisbelow(True)
for sp in ['top','right']: ax.spines[sp].set_visible(False)
for sp in ['left','bottom']: ax.spines[sp].set_color('#b8c5bd')
ax.text(1.13,7,'gate opens',rotation=90,fontsize=8,color=MUTED)
fig.text(.365,.113,'First downward COM crossing of z = 49 mm, r ≤ 9 mm.',fontsize=8,color=MUTED)
fig.text(.365,.089,'Each bean counted once; no reset on rebound.',fontsize=8,color=MUTED)

text=(f'50 free bodies · 2 ellipsoids each\n'
      '10 × 6.5 × 4.55 mm · 0.130 g / bean\n'
      'Shallow underside + domed upper lobe¹\n\n'
      'Friction μ: bean 0.48 / wall 0.32\n'
      'Newton 60 · elliptic cone · implicitfast\n'
      'Δt 0.5 ms · solref (3 ms, 1)\n'
      '40 wall sectors · 76 mm top diameter\n'
      'Gate slides 55 mm from 1.00–1.15 s')
fig.text(.72,.394,text,fontsize=10,va='top',linespacing=1.55)
fig.text(.72,.157,f'{max_pen*1000:.3f} mm',fontsize=21,color=TEAL,weight='bold')
fig.text(.72,.135,'maximum wall penetration over 5 s',fontsize=9,color=MUTED)
fig.text(.72,.105,f'Escaped beans: {len(escaped)}  /  Remaining above throat: {50-counts_at[5]}',fontsize=9,color=INK)
fig.add_artist(plt.Line2D([.045,.955],[.064,.064],transform=fig.transFigure,color='#c8d0c7',lw=1))
fig.text(.045,.042,'¹ A two-ellipsoid approximation has a flattened, not perfectly planar, face. Shell cut away for visibility; tray shown edge-on.',fontsize=8,color=MUTED)
fig.text(.955,.023,'SI physics  •  deterministic seed 41  •  model.xml',ha='right',fontsize=8,color=MUTED)
fig.savefig(os.environ.get('OUT','hopper.png'),dpi=180,facecolor=BG)
plt.close(fig)
