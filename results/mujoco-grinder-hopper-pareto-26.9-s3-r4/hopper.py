"""50-bean hopper: actual MuJoCo dynamics, Matplotlib projection of recorded states.
Run with OUT=/path/to/figure.png python hopper.py (mujoco, numpy, matplotlib).
SI units throughout. A shallow lower ellipsoid approximates, not literally makes,
a planar bean face. Cone walls are a closed 48-sided convex-mesh assembly.
"""
from pathlib import Path
import os
import numpy as np
import mujoco as mj
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import FancyArrowPatch

HERE = Path(__file__).resolve().parent
N, DT, T, ZTH = 50, 0.0005, 5.0, 0.080
rng = np.random.default_rng(24)
# Non-overlapping seeded lattice, deliberately loose at t=0; no hidden settling.
starts = []
for z in [0.113, 0.128, 0.143, 0.158]:
    candidates = [(x,y) for x in np.arange(-.036,.037,.013)
                  for y in np.arange(-.036,.037,.013)
                  if np.hypot(x,y) < .009+(z-.080)*(.039/.090)-.007]
    rng.shuffle(candidates)
    for x,y in candidates:
        starts.append((x,y,z))
starts = starts[:N]
assert len(starts) == N
asset, walls = [], []
# Each wedge has an inner planar face tangent to the specified cone.
ns = 48
for i in range(ns):
    a, b = 2*np.pi*np.array([i,i+1])/ns
    vertices=[]
    for z, r in [(.080,.009),(.170,.048)]:
        for rr in [r/np.cos(np.pi/ns),(r+.002)/np.cos(np.pi/ns)]:
            for th in [a,b]: vertices.append((rr*np.cos(th),rr*np.sin(th),z))
    asset.append(f'<mesh name="wallmesh{i}" vertex="'+ ' '.join(f'{v:.9f}' for p in vertices for v in p)+'"/>')
    walls.append(f'<geom name="wall{i}" type="mesh" mesh="wallmesh{i}" rgba="0.5 0.6 0.6 0.25"/>')
beans=[]
for i, (x,y,z) in enumerate(starts):
    # Random yaw only avoids initial overlaps; full 6-DoF motion thereafter.
    yaw=rng.uniform(-np.pi,np.pi)
    beans.append(f'''<body name="bean_{i:02d}" pos="{x} {y} {z}" quat="{np.cos(yaw/2)} 0 0 {np.sin(yaw/2)}">
      <freejoint/>
      <geom name="bean_{i:02d}_dome" type="ellipsoid" size=".0049 .0030 .0018" pos="0 0 .0009" mass=".00011" rgba=".28 .12 .055 1"/>
      <geom name="bean_{i:02d}_face" type="ellipsoid" size=".005 .0032 .0007" pos="0 0 -.0006" mass=".00004" rgba=".36 .18 .08 1"/>
    </body>''')
xml=f'''<mujoco model="Roasted coffee / 18 mm gated hopper">
 <compiler angle="radian" autolimits="true"/>
 <option timestep="{DT}" gravity="0 0 -9.81" integrator="implicitfast" solver="Newton" iterations="80" tolerance="1e-10" cone="elliptic" impratio="5"/>
 <size nconmax="8000" njmax="24000"/>
 <default><geom friction=".25 .0001 .00002" condim="6" solref=".0012 1" solimp=".95 .99 .0002" margin="0"/></default>
 <asset>{''.join(asset)}</asset>
 <worldbody>
  {''.join(walls)}
  <geom name="tray" type="box" pos="0 0 -.002" size=".095 .075 .002" rgba=".5 .6 .6 1"/>
  <geom name="tray_xp" type="box" pos=".096 0 .008" size=".001 .076 .010"/>
  <geom name="tray_xn" type="box" pos="-.096 0 .008" size=".001 .076 .010"/>
  <geom name="tray_yp" type="box" pos="0 .076 .008" size=".095 .001 .010"/>
  <geom name="tray_yn" type="box" pos="0 -.076 .008" size=".095 .001 .010"/>
  <body name="gate" pos="0 0 .0792" gravcomp="1">
   <joint name="gate_slide" type="slide" axis="1 0 0" range="0 .037" damping="1"/>
   <geom name="gate_plate" type="box" size=".014 .015 .0008" mass=".02" friction=".25 .0001 .00002" rgba=".1 .6 .6 1"/>
  </body>
  {''.join(beans)}
 </worldbody>
 <!-- Gate runs in an ideal guide; suppress gate/world contact at the flush seam. -->
 <contact><exclude body1="world" body2="gate"/></contact>
 <actuator><position name="open_gate" joint="gate_slide" kp="300" kv="4" ctrlrange="0 .037"/></actuator>
</mujoco>'''
(HERE/'model.xml').write_text(xml)
# The render harness copies this script into a scratch directory; also deliver
# the MJCF beside the submitted source when running in that harness.
if HERE != Path('/work') and Path('/work/hopper.py').exists():
    Path('/work/model.xml').write_text(xml)
model=mj.MjModel.from_xml_string(xml)
data=mj.MjData(model)
wallids={mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,f'wall{i}') for i in range(ns)}
bodyids=np.array([mj.mj_name2id(model,mj.mjtObj.mjOBJ_BODY,f'bean_{i:02d}') for i in range(N)])
geomids=np.array([[mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,f'bean_{i:02d}_{part}') for part in ['dome','face']] for i in range(N)]).ravel()
gateid=mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,'gate_plate')
frames={}; times=[]; counts=[]; passed=set(); escaped=set(); maxpen=0.; maxpentime=0.
mj.mj_forward(model,data)
previous=data.xipos[bodyids,2].copy()
def capture():
    contacts=[]
    for j in range(data.ncon):
        c=data.contact[j]; wrench=np.zeros(6)
        mj.mj_contactForce(model,data,j,wrench)
        if np.linalg.norm(wrench[:3])>1e-8:
            contacts.append((c.pos.copy(),c.frame.reshape(3,3).T @ wrench[:3]))
    return dict(pos=data.geom_xpos[geomids].copy(), rot=data.geom_xmat[geomids].reshape(-1,3,3).copy(),
                gate=data.geom_xpos[gateid].copy(), count=len(passed), contacts=contacts)
for step in range(round(T/DT)+1):
    t=step*DT
    if step:
        # 120 ms commanded withdrawal, starts exactly at 1 s.
        data.ctrl[0]=.037*np.clip((data.time-1.)/.120,0,1)
        mj.mj_step(model,data)
        # Synchronize derived positions/contacts to qpos at the reported time.
        mj.mj_forward(model,data)
    pos=data.xipos[bodyids]
    for i in np.where((previous>=ZTH)&(pos[:,2]<ZTH))[0]:
        if np.hypot(*pos[i,:2])<.009: passed.add(int(i))
    previous=pos[:,2].copy()
    for i in np.where((np.abs(pos[:,0])>.100)|(np.abs(pos[:,1])>.080)|(pos[:,2]<-.010)|(pos[:,2]>.200))[0]:
        escaped.add(int(i))
    for j in range(data.ncon):
        c=data.contact[j]
        if (c.geom1 in wallids or c.geom2 in wallids) and -c.dist>maxpen:
            maxpen=-c.dist; maxpentime=t
    if step%20==0: times.append(t); counts.append(len(passed))
    if step in [0,2000,4000,10000,2080]: frames[round(t,3)]=capture()
print(f'MuJoCo {mj.__version__}; {N} beans; timestep {DT:g} s; simulated {data.time:.3f} s')
print('Bean: 10 × 6.4 × 4.0 mm envelope; 0.150 g; overlapping dome + shallow-face ellipsoids.')
print('Friction (slide / torsion / roll): 0.25 / 0.0001 m / 0.00002 m; gate slide 0.25.')
print('Newton, 80 iterations, tolerance 1e-10; elliptic cone, condim 6; implicitfast; solref 0.0012 1.')
print(f'Maximum hopper-wall penetration: {maxpen*1000:.4f} mm at {maxpentime:.4f} s')
for t in [0.,1.,2.,5.]: print(f't={t:.0f} s: {frames[t]["count"]}/50 beans through throat')
print(f'Final gate withdrawal: {(data.geom_xpos[gateid,0])*1000:.2f} mm')
print('Beans that left the model envelope: '+(', '.join(f'bean_{i:02d}' for i in sorted(escaped)) if escaped else 'none'))

# All geometry below is projected from the simulated poses, not illustrative
# trajectories. xz oblique view: front shell is omitted only for visibility.
BG='#f5f2eb'; INK='#243536'; MUTED='#647475'; TEAL='#137e83'; ORANGE='#d45b35'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':INK,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,'axes.edgecolor':'#c5ccc6'})
fig=plt.figure(figsize=(16,11),facecolor=BG)
gs=fig.add_gridspec(2,4,left=.045,right=.97,bottom=.27,top=.815,hspace=.27,wspace=.13,height_ratios=[1.13,1])
P=np.array([[1,.36,0],[0,.17,1]])
view=np.cross(P[0],P[1]); view=view/np.linalg.norm(view)
def proj(v): return np.asarray(v)@P.T*1000
# Surface tessellation shared by all ellipsoids.
verts=[]
for a in np.linspace(0,np.pi,10):
    for b in np.linspace(0,2*np.pi,19)[:-1]: verts.append([np.sin(a)*np.cos(b),np.sin(a)*np.sin(b),np.cos(a)])
verts=np.array(verts)
faces=np.array([[r*18+j,r*18+(j+1)%18,(r+1)*18+(j+1)%18,(r+1)*18+j] for r in range(9) for j in range(18)])
light=np.array([-.4,-.6,1.]); light/=np.linalg.norm(light)
def bean_art(ax,s):
    polys=[]; colors=[]; depths=[]
    for k,(p,R) in enumerate(zip(s['pos'],s['rot'])):
        sizes=model.geom_size[geomids[k]]
        vv=(verts*sizes)@R.T+p
        normal=(verts[faces].mean(axis=1)/sizes)@R.T
        normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-10)
        visible=normal@view>0
        shade=.57+.43*np.clip(normal@light,0,1)
        base=np.array([.43,.235,.12]) if k%2==0 else np.array([.50,.29,.15])
        for f in np.where(visible)[0]:
            polys.append(proj(vv[faces[f]])); colors.append(np.clip(base*shade[f],0,1)); depths.append(vv[faces[f]].mean(axis=0)@view)
    order=np.argsort(depths)
    ax.add_collection(PolyCollection([polys[i] for i in order],facecolors=[colors[i] for i in order],edgecolors='none',zorder=4))
def path(ax,xyz,**kw):
    p=proj(xyz); ax.plot(p[:,0],p[:,1],**kw)
def apparatus(ax,s,zoom=False):
    # back shell, physical 48-facet cone; full mouth/throat rings as outlines.
    for i in range(24):
        a,b=2*np.pi*np.array([i,i+1])/48
        xyz=[[r*np.cos(th),r*np.sin(th),z] for r,z,th in [(.009,.080,a),(.048,.170,a),(.048,.170,b),(.009,.080,b)]]
        ax.add_collection(PolyCollection([proj(xyz)],facecolors='#dfe5df',edgecolors='#d2dcd7',linewidths=.25,zorder=0))
    theta=np.linspace(0,2*np.pi,120)
    for r,z in [(.009,.080),(.048,.170)]: path(ax,np.c_[r*np.cos(theta),r*np.sin(theta),np.full(len(theta),z)],color='#809791',lw=.9,zorder=2)
    for x in [-1,1]: path(ax,[[x*.009,0,.080],[x*.048,0,.170]],color='#688780',lw=1.1,zorder=2)
    tray=np.array([[-.095,-.075,0],[.095,-.075,0],[.095,.075,0],[-.095,.075,0]])
    ax.add_collection(PolyCollection([proj(tray)],facecolors='#d7dfdc',edgecolors='#9bafaa',lw=1,zorder=0))
    for a,b in zip(tray,np.roll(tray,-1,axis=0)):
        path(ax,[a+[0,0,.018],b+[0,0,.018]],color='#a8b8b2',lw=.7,zorder=1)
    g=s['gate']; plate=np.array([[-.014,-.015,0],[.014,-.015,0],[.014,.015,0],[-.014,.015,0]])+g
    ax.add_collection(PolyCollection([proj(plate)],facecolors=TEAL,edgecolors='#076065',linewidths=.8,zorder=3))
    bean_art(ax,s)
    ax.set_aspect('equal'); ax.set_facecolor(BG)
    ax.set_xlim((-34,57) if zoom else (-125,125)); ax.set_ylim((65,122) if zoom else (-19,191))
    ax.axis('off')

labels=['Loose charge','Gate starts opening','Discharge','Tray / final state']
for j,t in enumerate([0.,1.,2.,5.]):
    ax=fig.add_subplot(gs[0,j]); apparatus(ax,frames[t])
    ax.set_title(f'{t:.0f} s  /  {labels[j]}',loc='left',fontsize=12,fontweight='bold',pad=15)
    ax.text(.02,-.06,f'{frames[t]["count"]:02d} / 50 passed',transform=ax.transAxes,fontsize=12,color=TEAL,fontweight='bold')
    if j==0:
        ax.annotate('Ø 18 mm',xy=(0,80),xytext=(-109,62),fontsize=9,color=MUTED,arrowprops={'arrowstyle':'-','color':MUTED,'lw':.7})
        ax.text(-110,26,'Catching tray',fontsize=9,color=MUTED)
        ax.plot([-107,-87],[176,176],color=INK,lw=2); ax.text(-97,182,'20 mm',ha='center',fontsize=8)
    if j==1:
        ax.annotate('slides 37 mm →',xy=(10,77),xytext=(9,55),fontsize=8,color=TEAL)

ax=fig.add_subplot(gs[1,:2]); diag=frames[1.04]; apparatus(ax,diag,zoom=True)
ax.set_title('CONTACT AUDIT  /  1.040 s',loc='left',fontsize=12,fontweight='bold',pad=16)
cs=[(p,f) for p,f in diag['contacts'] if 65<proj(p)[1]<122 and -34<proj(p)[0]<57]
# A common, quantitative scale for all displayed arrows; no unit vectors.
strong=sorted(cs,key=lambda c:np.linalg.norm(c[1]),reverse=True)[:30]
fmax=max([np.linalg.norm(f) for p,f in strong]+[.001])
fref=10**np.ceil(np.log10(fmax/2))
scale=.008/fref
for p,f in strong:
    a=proj(p); b=proj(p+scale*f)
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=7,lw=1,color=ORANGE,zorder=7))
if cs:
    pp=proj([p for p,f in cs]); ax.scatter(pp[:,0],pp[:,1],s=9,facecolor=BG,edgecolor=ORANGE,linewidth=.7,zorder=8)
ax.text(.01,-.10,f'{len(cs)} active contact points in crop · largest {len(strong)} resultants on geom 2\nForce scale: {fref*1000:g} mN → 8 mm; same oblique projection as geometry',transform=ax.transAxes,fontsize=9,color=MUTED,linespacing=1.6)

ax=fig.add_subplot(gs[1,2:]); ax.set_facecolor(BG)
ax.axvspan(1,1.12,color=TEAL,alpha=.09,lw=0)
ax.axvline(1,color=TEAL,lw=1,ls=(0,(3,3)))
ax.step(times,counts,where='post',color=TEAL,lw=2.4)
ax.fill_between(times,counts,step='post',color=TEAL,alpha=.07)
for t in [0.,1.,2.,5.]:
    c=frames[t]['count']; ax.plot(t,c,'o',mfc=BG,mec=TEAL,mew=1.5,ms=6,zorder=4)
    ax.annotate(str(c),(t,c),xytext=(-9 if t==5 else 7,9 if c<45 else -18),textcoords='offset points',fontsize=10,fontweight='bold',color=TEAL)
ax.text(1.35,36,'gate command\n1.00–1.12 s',color=TEAL,fontsize=9)
ax.set(xlim=(-.06,5.08),ylim=(-2,54),xticks=np.arange(6),yticks=np.arange(0,51,10),xlabel='Simulation time  /  s',ylabel='Unique beans through throat')
ax.set_title('CUMULATIVE DISCHARGE',loc='left',fontsize=12,fontweight='bold',pad=16)
ax.grid(axis='y',color='#dce0d8',lw=.7); ax.spines[['top','right']].set_visible(False)
ax.text(0,-.34,'First downward COM crossing at z = 80 mm, inside r < 9 mm.\nCounts are unique bean IDs, not contact events.',transform=ax.transAxes,color=MUTED,fontsize=9,linespacing=1.6)

fig.text(.045,.951,'GRANULAR FLOW  /  MUJOCO STUDY 01',color=TEAL,fontsize=11,fontweight='bold')
fig.text(.045,.904,'Fifty beans. One narrow throat.',fontsize=30,fontweight='bold')
fig.text(.045,.866,'18 mm outlet   /   sliding gate at 1 s   /   5 s simulation   /   oblique cutaway: front hopper wall hidden in drawing only',fontsize=11,color=MUTED)
fig.add_artist(plt.Line2D([.045,.97],[.176,.176],transform=fig.transFigure,color='#c4ccc5',lw=1))
fig.text(.045,.145,'PARTICLE & CONTACT',fontsize=10,fontweight='bold',color=TEAL)
fig.text(.045,.120,'50 free bodies · 2 overlapping ellipsoids each\n10 × 6.4 × 4.0 mm · 0.150 g per bean\nDomed top + shallow, near-flat underside',fontsize=10,linespacing=1.6,va='top')
fig.text(.37,.145,'DECLARED PHYSICS',fontsize=10,fontweight='bold',color=TEAL)
fig.text(.37,.120,'μ slide 0.25 · torsion 0.0001 m · roll 0.00002 m\nNewton 80 / tol 10⁻¹⁰ · elliptic / condim 6\nΔt 0.5 ms · implicitfast · solref (1.2 ms, 1)',fontsize=10,linespacing=1.6,va='top')
fig.text(.705,.145,'RUN CHECK',fontsize=10,fontweight='bold',color=TEAL)
fig.text(.705,.120,f'Max wall penetration  {maxpen*1000:.3f} mm\n{len(passed)} / 50 through · {len(escaped)} left model envelope\n48-facet closed cone · seed 24 · gravity 9.81 m/s²',fontsize=10,linespacing=1.6,va='top')
fig.text(.045,.028,'Measured states, not an animation sketch. Soft-contact overlap is reported across the complete run. MJCF: model.xml',fontsize=9,color=MUTED)
fig.savefig(os.environ['OUT'],dpi=170,facecolor=BG)
plt.close(fig)
