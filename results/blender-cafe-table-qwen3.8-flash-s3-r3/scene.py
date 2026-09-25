# Cafe table scene: espresso cup on saucer, spoon, sugar cubes, croissant.
# Built only from primitive meshes (cube, cylinder, cone, sphere, torus).
# Meters, real-world scale: table top surface at z = 0.

import math
from math import radians, sin, cos, pi

import bpy

D = bpy.data


# ---------------------------------------------------------------- utilities
def wipe_scene():
    for o in list(D.objects):
        D.objects.remove(o, do_unlink=True)
    for block in (D.meshes, D.materials, D.lights, D.cameras):
        for b in list(block):
            block.remove(b)


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def smooth(obj, auto=True, angle=radians(35)):
    for p in obj.data.polygons:
        p.use_smooth = True
    if auto and hasattr(obj.data, "use_auto_smooth"):
        obj.data.use_auto_smooth = True
        obj.data.auto_smooth_angle = angle
    return obj


def setmat(obj, mat):
    if mat is not None:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    return obj


def new_material(name):
    m = D.materials.new(name)
    m.use_nodes = True
    return m


def bsdf_of(m):
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None


def set_in(node, name, value):
    if name in node.inputs:
        node.inputs[name].default_value = value
        return True
    return False


def simple_material(name, color, rough=0.5, metal=0.0, transmission=0.0,
                    ior=1.45, coat=0.0, subsurface=0.0):
    m = new_material(name)
    b = bsdf_of(m)
    set_in(b, "Base Color", (color[0], color[1], color[2], 1.0))
    set_in(b, "Roughness", rough)
    set_in(b, "Metallic", metal)
    set_in(b, "Transmission Weight", transmission)
    set_in(b, "IOR", ior)
    set_in(b, "Coat Weight", coat) or set_in(b, "Clearcoat", coat)
    set_in(b, "Subsurface Weight", subsurface) or set_in(b, "Subsurface", subsurface)
    if subsurface:
        set_in(b, "Subsurface Radius", (0.01, 0.01, 0.01))
    return m


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    r = bpy.context.active_object
    r.name = name
    # bake everything into world space so later moves/rotations behave
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return r


def place(obj, x, y, rot_deg=0.0, z=0.0):
    """Move obj so its bounding-box centre lands on (x, y) after a Z rotation."""
    bb = [tuple(c) for c in obj.bound_box]
    cx = sum(v[0] for v in bb) / 8.0
    cy = sum(v[1] for v in bb) / 8.0
    cz = sum(v[2] for v in bb) / 8.0
    r = radians(rot_deg)
    px = cos(r) * cx - sin(r) * cy
    py = sin(r) * cx + cos(r) * cy
    obj.rotation_euler = (0, 0, r)
    obj.location = (x - px, y - py, z - cz)
    return obj


def aim_z(obj, direction, up=(0, 0, 1)):
    """Rotate obj so its local +Z points along `direction`."""
    import mathutils
    q = mathutils.Vector(direction).to_track_quat('Z', 'Y')
    obj.rotation_euler = q.to_euler()
    return obj


# ------------------------------------------------------------- primitives
def cube(name, size=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), mat=None, smooth_=False):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    setmat(o, mat)
    if smooth_:
        smooth(o, auto=False)
    return o


def cylinder(name, r=1.0, d=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
             mat=None, verts=64, fill='NGON'):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d,
                                        location=loc, rotation=rot, end_fill_type=fill)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    setmat(o, mat)
    smooth(o)
    return o


def cone(name, r1=1.0, r2=0.0, d=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
         mat=None, verts=64, fill='NGON'):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=d,
                                    location=loc, rotation=rot, end_fill_type=fill)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    setmat(o, mat)
    smooth(o)
    return o


def sphere(name, r=1.0, loc=(0, 0, 0), scale=(1, 1, 1), mat=None, seg=32, ring=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=ring, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    setmat(o, mat)
    smooth(o)
    return o


def torus(name, R=1.0, r=0.1, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
          mat=None, maj=64, mino=24):
    bpy.ops.mesh.primitive_torus_add(major_segments=maj, minor_segments=mino,
                                     major_radius=R, minor_radius=r, location=loc,
                                     rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    setmat(o, mat)
    smooth(o, angle=radians(45))
    return o


# ---------------------------------------------------------------- materials
def wood_material():
    m = new_material("TableWood")
    nt = m.node_tree
    n, l = nt.nodes, nt.links
    b = bsdf_of(m)
    tex = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 6.0, 6.0)
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Z'
    wave.inputs["Scale"].default_value = 0.55
    wave.inputs["Distortion"].default_value = 5.5
    wave.inputs["Detail"].default_value = 2.0
    wave.inputs["Detail Scale"].default_value = 1.4
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 6.0
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.155, 0.062, 0.026, 1)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (0.335, 0.150, 0.062, 1)
    mix = n.new("ShaderNodeMixRGB")
    mix.blend_type = 'MULTIPLY'
    mix.inputs["Fac"].default_value = 0.35
    l.new(tex.outputs["Object"], mapping.inputs["Vector"])
    l.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    l.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    l.new(wave.outputs["Color"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], mix.inputs["Color1"])
    l.new(noise.outputs["Color"], mix.inputs["Color2"])
    l.new(mix.outputs["Color"], b.inputs["Base Color"])
    set_in(b, "Roughness", 0.28)
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    l.new(wave.outputs["Color"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def dough_material():
    m = new_material("CroissantDough")
    nt = m.node_tree
    n, l = nt.nodes, nt.links
    b = bsdf_of(m)
    tex = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 26.0
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.62
    ramp = n.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.30
    cr.elements[0].color = (0.30, 0.115, 0.026, 1)
    cr.elements[1].position = 0.62
    cr.elements[1].color = (0.63, 0.30, 0.075, 1)
    e = cr.elements.new(0.85)
    e.color = (0.80, 0.47, 0.16, 1)
    l.new(tex.outputs["Object"], noise.inputs["Vector"])
    l.new(noise.outputs["Color"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    set_in(b, "Roughness", 0.42)
    set_in(b, "Specular IOR Level", 0.35) or set_in(b, "Specular", 0.35)
    set_in(b, "Sheen Weight", 0.25) or set_in(b, "Sheen", 0.25)
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.0012
    l.new(noise.outputs["Color"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def sugar_material():
    m = new_material("Sugar")
    b = bsdf_of(m)
    set_in(b, "Base Color", (0.86, 0.86, 0.84, 1))
    set_in(b, "Roughness", 0.42)
    set_in(b, "Transmission Weight", 0.12) or set_in(b, "Transmission", 0.12)
    set_in(b, "IOR", 1.55)
    return m


# -------------------------------------------------------------------- build
wipe_scene()
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'

porcelain = simple_material("Porcelain", (0.78, 0.775, 0.765), rough=0.06, coat=0.35, ior=1.5)
porcelain_warm = simple_material("PorcelainWarm", (0.76, 0.755, 0.74), rough=0.08, coat=0.3)
crema = simple_material("EspressoCrema", (0.28, 0.135, 0.045), rough=0.22, coat=0.15)
steel = simple_material("Steel", (0.72, 0.73, 0.75), rough=0.11, metal=1.0)
wood = wood_material()
dough = dough_material()
sugar = sugar_material()
crumb_mat = simple_material("Crumb", (0.55, 0.30, 0.10), rough=0.6)
dark = simple_material("Dark", (0.02, 0.02, 0.02), rough=0.6)

# ---- table (round cafe table top, its edge stays out of frame)
table_top = cylinder("TableTop", r=0.45, d=0.035, loc=(0, 0, -0.0175), mat=wood, verts=128)
torus("TableEdge", R=0.4495, r=0.004, loc=(0, 0, -0.004), mat=wood)
cylinder("TablePedestal", r=0.045, d=0.70, loc=(0, 0, -0.385), mat=dark, verts=48)
cylinder("TableFoot", r=0.17, d=0.02, loc=(0, 0, -0.735), mat=dark, verts=64)

# room beyond the table edge (visible at the top of the frame)
cube("Floor", size=1.0, loc=(0, 0, -0.755), scale=(4, 4, 0.05),
     mat=simple_material("Floor", (0.13, 0.12, 0.115), rough=0.7))
cube("Wall", size=1.0, loc=(0, 0.95, 0.55), scale=(4, 0.06, 1.9),
     mat=simple_material("Wall", (0.34, 0.285, 0.235), rough=0.85))
cube("WallTrim", size=1.0, loc=(0, 0.93, -0.10), scale=(4, 0.05, 0.16),
     mat=simple_material("Trim", (0.16, 0.12, 0.085), rough=0.6))

# ---- saucer
saucer_top = 0.0065           # z of the well floor the cup stands on
parts = []
parts.append(cylinder("SaucerFoot", r=0.0455, d=0.0045, loc=(0, 0, 0.00225),
                      mat=porcelain_warm))
parts.append(cylinder("SaucerWell", r=0.047, d=0.0025, loc=(0, 0, saucer_top - 0.00125),
                      mat=porcelain_warm))
parts.append(cone("SaucerRim", r1=0.045, r2=0.0755, d=0.0125,
                  loc=(0, 0, saucer_top + 0.0035), mat=porcelain_warm,
                  fill='NOTHING', verts=96))
parts.append(torus("SaucerLip", R=0.0755, r=0.0022, loc=(0, 0, saucer_top + 0.0097),
                   mat=porcelain_warm))
saucer = join(parts, "Saucer")
smooth(saucer)


def move(obj, dx, dy, dz=0.0):
    obj.location.x += dx
    obj.location.y += dy
    obj.location.z += dz
    return obj

# ---- espresso cup (hollow shell: outer wall, inner wall, floor, rim torus)
z0 = saucer_top + 0.0005
H = 0.052
Ro_b, Ro_t = 0.0235, 0.0325        # outer radius bottom / top
Ri_b, Ri_t = 0.0205, 0.0295        # inner radius bottom / top
cparts = []
cparts.append(cone("CupOuter", r1=Ro_b, r2=Ro_t, d=H, loc=(0, 0, z0 + H / 2),
                   mat=porcelain, fill='NOTHING', verts=96))
cparts.append(cone("CupInner", r1=Ri_b, r2=Ri_t, d=H - 0.005,
                   loc=(0, 0, z0 + 0.005 + (H - 0.005) / 2),
                   mat=porcelain, fill='NOTHING', verts=96))
cparts.append(cone("CupFloor", r1=Ri_b, r2=Ri_b - 0.001, d=0.005,
                   loc=(0, 0, z0 + 0.0025), mat=porcelain, verts=96))
cparts.append(cylinder("CupBase", r=Ro_b + 0.0015, d=0.004, loc=(0, 0, z0 + 0.002),
                       mat=porcelain, verts=96))
rim_mid = 0.5 * (Ro_t + Ri_t)
rim_minor = 0.5 * (Ro_t - Ri_t)
cparts.append(torus("CupRim", R=rim_mid, r=rim_minor, loc=(0, 0, z0 + H), mat=porcelain))
# handle: torus ring in the XZ plane, biting into the outer wall
hx = Ro_t - 0.005
cparts.append(torus("CupHandle", R=0.0165, r=0.0046, loc=(hx, 0, z0 + 0.027),
                    rot=(radians(90), 0, 0), scale=(1.0, 1.18, 1.0)))
cup = join(cparts, "EspressoCup")
smooth(cup)

# ---- group placement on the table
CUP_POS = (0.030, -0.028)
move(saucer, *CUP_POS)
move(cup, *CUP_POS)

# espresso surface, a little below the rim
z_liq = z0 + H - 0.010
slope = (Ri_t - Ri_b) / (H - 0.005)
r_liq = Ri_b + slope * (z_liq - (z0 + 0.005)) + 0.0008
liquid = cylinder("Espresso", r=r_liq, d=0.0025, loc=(0, 0, z_liq), mat=crema, verts=96)
move(liquid, *CUP_POS)

# ---- spoon, lying on the table to the right of the saucer
sp_parts = []
sp_parts.append(sphere("SpoonBowl", r=1.0, loc=(0.0, 0, 0.0046),
                       scale=(0.0210, 0.0142, 0.0040), mat=steel, seg=32, ring=16))
sp_parts.append(cube("SpoonNeck", size=1.0, loc=(0.030, 0, 0.0024),
                     scale=(0.022, 0.0055, 0.0011), mat=steel))
sp_parts.append(cube("SpoonHandle", size=1.0, loc=(0.085, 0, 0.0022),
                     scale=(0.055, 0.0068, 0.0011), mat=steel))
sp_parts.append(sphere("SpoonTip", r=1.0, loc=(0.140, 0, 0.0022),
                       scale=(0.0075, 0.0055, 0.0012), mat=steel))
spoon = join(sp_parts, "Spoon")
place(spoon, 0.135, -0.030, rot_deg=-52)
smooth(spoon)

# ---- sugar cubes, left-front of the saucer
cube_s = 0.0135
sugar_positions = [(-0.098, -0.104, 0, 14),
                   (-0.121, -0.088, 0, -22),
                   (-0.110, -0.099, 1, 34)]
for i, (sx, sy, lvl, rot) in enumerate(sugar_positions):
    z = cube_s / 2 + lvl * cube_s
    c = cube("SugarCube%d" % i, size=cube_s, loc=(sx, sy, z + (0.0008 if lvl else 0.0)),
             rot=(0, 0, radians(rot)), mat=sugar)
    smooth(c, auto=False)
# a few sugar grains
for i, (gx, gy) in enumerate([(-0.082, -0.118), (-0.134, -0.076), (-0.090, -0.075),
                              (-0.128, -0.112)]):
    sphere("SugarGrain%d" % i, r=0.0011, loc=(gx, gy, 0.0009), mat=sugar, seg=12, ring=8)

# ---- croissant: chain of squashed spheres along an arc + two cone tips
arc_R = 0.042
a0, a1 = 208, 332
prof = [0.30, 0.52, 0.72, 0.88, 1.00, 1.00, 0.88, 0.72, 0.52, 0.30]
r_max = 0.0185
cp = []
n = len(prof)
for i, f in enumerate(prof):
    t = a0 + (a1 - a0) * (i / (n - 1))
    th = radians(t)
    r = r_max * (0.42 + 0.58 * f)
    x = arc_R * cos(th)
    y = arc_R * sin(th)
    squash = 0.70 + 0.10 * f
    cp.append(sphere("CroissantSeg%d" % i, r=r, loc=(x, y, r * squash * 0.98),
                     scale=(1.0, 1.0, squash), mat=dough, seg=28, ring=16))
for side, i in ((1, 0), (-1, n - 1)):
    t = a0 if side == 1 else a1
    th = radians(t)
    tang = (-sin(th), cos(th))                 # direction of increasing angle
    out = (tang[0] * side, tang[1] * side)     # outward along the crescent
    base = (arc_R * cos(th), arc_R * sin(th))
    r_end = r_max * (0.42 + 0.58 * prof[i])
    L = 0.024
    c = cone("CroissantTip%d" % i, r1=r_end * 0.95, r2=0.0014, d=L,
             loc=(0, 0, 0), mat=dough, verts=32)
    aim_z(c, (out[0], out[1], -0.35))
    c.location = (base[0] + out[0] * (L * 0.42),
                  base[1] + out[1] * (L * 0.42), r_end * 0.72)
    cp.append(c)
croissant = join(cp, "Croissant")
place(croissant, -0.120, 0.062, rot_deg=196)
smooth(croissant)

# crumbs
for i, (cx, cy, cr) in enumerate([(-0.062, 0.014, 0.0022), (-0.042, 0.042, 0.0016),
                                  (-0.075, -0.006, 0.0019), (-0.028, 0.068, 0.0013),
                                  (-0.150, 0.014, 0.0017)]):
    sphere("Crumb%d" % i, r=cr, loc=(cx, cy, cr * 0.7), mat=crumb_mat, seg=14, ring=10)

# --------------------------------------------------------------- camera etc.
cam_data = D.cameras.new("Camera")
cam_data.lens = 50
cam_data.sensor_width = 36
cam_data.dof.use_dof = True
cam_data.dof.focus_distance = 0.50
cam_data.dof.aperture_fstop = 8.0
cam = bpy.data.objects.new("Camera", cam_data)
link(cam)
scene.camera = cam
import mathutils
target = mathutils.Vector((-0.005, 0.005, 0.026))
cam.location = (0.275, -0.360, 0.235)
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()

world = D.worlds.new("World") if not D.worlds else D.worlds[0]
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.28, 0.30, 0.34, 1)
bg.inputs[1].default_value = 0.12


def add_light(name, kind, loc, energy, color=(1, 1, 1), size=0.3, target_pt=(0, 0, 0),
              rotation=None):
    ld = D.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        ld.shape = 'RECTANGLE'
        ld.size = size
        ld.size_y = size * 0.7
    elif kind == 'SUN':
        ld.angle = radians(3)
    o = bpy.data.objects.new(name, ld)
    link(o)
    o.location = loc
    if rotation is not None:
        o.rotation_euler = rotation
    else:
        d = mathutils.Vector(target_pt) - mathutils.Vector(loc)
        o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


add_light("Key", 'AREA', (0.38, -0.34, 0.46), 7.5, (1.0, 0.96, 0.90), size=0.45,
          target_pt=(0.0, 0.0, 0.02))
add_light("Fill", 'AREA', (-0.42, -0.15, 0.30), 2.2, (0.90, 0.94, 1.0), size=0.5,
          target_pt=(0.0, 0.02, 0.02))
add_light("Rim", 'AREA', (-0.18, 0.45, 0.30), 3.5, (1.0, 0.97, 0.92), size=0.35,
          target_pt=(-0.05, 0.05, 0.03))
add_light("Room", 'AREA', (0.05, 0.55, 0.45), 4.0, (1.0, 0.93, 0.85), size=0.6,
          target_pt=(0.0, 0.6, 0.2))

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
try:
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium High Contrast'
except Exception as ex:
    print("view transform:", ex)
scene.view_settings.exposure = 0.0
