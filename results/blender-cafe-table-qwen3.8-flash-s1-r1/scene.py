# -*- coding: utf-8 -*-
"""
Cafe table scene, built entirely from primitive meshes
(cube / cylinder / cone / sphere / torus).

Contents: wooden table, porcelain espresso cup with handle standing in a
saucer, a shot of espresso, a steel spoon, three sugar cubes and a
croissant made from a chain of flattened ellipsoids.

Everything is modelled at real-world scale in metres (table top at z = 0).
"""

import bpy
import math
from math import cos, sin, radians, sqrt

C = bpy.context
SCENE = C.scene

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras, bpy.data.textures, bpy.data.node_groups):
        for b in list(block):
            if b.users == 0:
                block.remove(b)


def shade(ob, smooth=True, angle=38.0):
    try:
        for p in ob.data.polygons:
            p.use_smooth = smooth
        ob.data.use_auto_smooth = True
        ob.data.auto_smooth_angle = radians(angle)
    except Exception:
        pass


def set_in(node, names, value):
    """set the first input of `node` whose name is in `names`"""
    for nm in names:
        if nm in node.inputs:
            try:
                node.inputs[nm].default_value = value
            except Exception:
                pass
            return True
    return False


def make_mat(name, color, rough=0.5, metal=0.0, sss=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    set_in(b, ["Base Color"], color)
    set_in(b, ["Roughness"], rough)
    set_in(b, ["Metallic"], metal)
    set_in(b, ["Subsurface Weight", "Subsurface"], sss)
    set_in(b, ["IOR"], ior)
    try:
        m.node_tree.nodes["Material Output"].location = (300, 0)
    except Exception:
        pass
    return m


def give(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0


# ---- primitive factories (the ONLY geometry sources in this file) --------

def cube(sx, sy, sz, loc, rot=(0, 0, 0), name="cube", mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    ob = C.active_object
    ob.name = name
    ob.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    if mat:
        give(ob, mat)
    return ob


def cylinder(r, d, loc, rot=(0, 0, 0), verts=96, name="cylinder", mat=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d,
                                        location=loc, rotation=rot)
    ob = C.active_object
    ob.name = name
    shade(ob)
    if mat:
        give(ob, mat)
    return ob


def cone(r1, r2, d, loc, rot=(0, 0, 0), verts=96, name="cone", mat=None):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2,
                                    depth=d, location=loc, rotation=rot)
    ob = C.active_object
    ob.name = name
    shade(ob)
    if mat:
        give(ob, mat)
    return ob


def sphere(r, loc, scale=(1, 1, 1), rot=(0, 0, 0), seg=32, ring=16,
           name="sphere", mat=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=ring,
                                         radius=r, location=loc, rotation=rot)
    ob = C.active_object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    shade(ob)
    if mat:
        give(ob, mat)
    return ob


def torus(R, r, loc, rot=(0, 0, 0), maj=48, mino=16, name="torus", mat=None):
    bpy.ops.mesh.primitive_torus_add(major_segments=maj, minor_segments=mino,
                                     major_radius=R, minor_radius=r,
                                     location=loc, rotation=rot)
    ob = C.active_object
    ob.name = name
    shade(ob)
    if mat:
        give(ob, mat)
    return ob


def boolean(target, cutter, op='DIFFERENCE'):
    bpy.ops.object.select_all(action='DESELECT')
    target.select_set(True)
    C.view_layer.objects.active = target
    mod = target.modifiers.new("cut", 'BOOLEAN')
    mod.operation = op
    mod.object = cutter
    try:
        mod.solver = 'EXACT'
    except Exception:
        pass
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def join(parts, name):
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    C.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = C.active_object
    ob.name = name
    return ob


# --------------------------------------------------------------------------
# scene set-up
# --------------------------------------------------------------------------
clear_scene()

# ---- materials -----------------------------------------------------------
porcelain = make_mat("porcelain", (0.90, 0.895, 0.875), rough=0.10, sss=0.06)
porcelain_warm = make_mat("porcelain_inner", (0.88, 0.87, 0.845), rough=0.14)
crema = make_mat("espresso", (0.36, 0.175, 0.062), rough=0.30)
steel = make_mat("steel", (0.90, 0.905, 0.92), rough=0.14, metal=1.0)
sugar = make_mat("sugar", (0.93, 0.93, 0.92), rough=0.55, sss=0.30)


def tinted_mat(name, col_a, col_b, scale_a, scale_b, contrast,
               rough=0.45, bump=0.05):
    """two tone material driven by a wave texture -> wood grain / baked crust"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    try:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs['Scale'].default_value = scale_b[:3]
        wv = nt.nodes.new("ShaderNodeTexWave")
        wv.wave_type = 'BANDS'
        wv.inputs['Scale'].default_value = scale_a
        wv.inputs['Distortion'].default_value = contrast
        wv.inputs['Detail'].default_value = 2.0
        rp = nt.nodes.new("ShaderNodeValToRGB")
        rp.color_ramp.elements[0].color = (col_a[0], col_a[1], col_a[2], 1.0)
        rp.color_ramp.elements[1].color = (col_b[0], col_b[1], col_b[2], 1.0)
        rp.color_ramp.elements[0].position = 0.28
        rp.color_ramp.elements[1].position = 0.78
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], wv.inputs['Vector'])
        nt.links.new(wv.outputs['Color'], rp.inputs['Fac'])
        nt.links.new(rp.outputs['Color'], b.inputs['Base Color'])
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs['Strength'].default_value = bump
        nt.links.new(wv.outputs['Color'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    except Exception as e:
        print("texture skipped:", e)
        set_in(b, ["Base Color"], col_b)
    set_in(b, ["Roughness"], rough)
    return m


wood = tinted_mat("wood", (0.145, 0.066, 0.028), (0.30, 0.152, 0.068),
                  3.0, (1.0, 16.0, 16.0), 5.0, rough=0.38, bump=0.04)
crust = tinted_mat("croissant", (0.335, 0.135, 0.038), (0.615, 0.300, 0.075),
                   14.0, (1.0, 1.0, 1.0), 3.0, rough=0.42, bump=0.12)
crust_dark = make_mat("croissant_tip", (0.30, 0.115, 0.033), rough=0.45)

# ---- the table -----------------------------------------------------------
TABLE = cube(1.10, 0.85, 0.045, (0, 0, -0.0225), name="table_top", mat=wood)
for sx in (-1, 1):
    for sy in (-1, 1):
        cube(0.06, 0.06, 0.70, (sx * 0.48, sy * 0.35, -0.3725),
             name="leg", mat=wood)

# ---- saucer (thin flared shell, hollowed with a boolean) -----------------
SR_OUT, SR_IN0, SH = 0.066, 0.030, 0.016      # rim radius, foot radius, height
k = (SR_OUT - SR_IN0) / SH                    # side slope of the flare
floor = 0.0035                                # thickness of the saucer floor

saucer = cone(SR_IN0, SR_OUT, SH, (0, 0, SH / 2.0), name="saucer", mat=porcelain)
cut_r1 = (SR_IN0 + k * floor) - 0.0022
cut_h = (SH + 0.006) - floor
cutter = cone(cut_r1, cut_r1 + k * cut_h, cut_h, (0, 0, floor + cut_h / 2.0),
              verts=96, name="saucer_cutter")
boolean(saucer, cutter)
rim = torus(SR_OUT, 0.0011, (0, 0, SH), maj=96, mino=12, name="saucer_lip",
            mat=porcelain)
saucer = join([saucer, rim], "saucer")

# ---- espresso cup --------------------------------------------------------
CZ = floor                     # cup rests on the floor of the saucer
CH = 0.056                     # cup height
CR_BOT, CR_TOP = 0.0275, 0.0335
ck = (CR_TOP - CR_BOT) / CH

cup = cone(CR_BOT, CR_TOP, CH, (0, 0, CZ + CH / 2.0), name="cup", mat=porcelain)
wall = 0.0030
ic = CZ + 0.0045                              # inside floor level
cru1 = (CR_BOT + ck * (ic - CZ)) - wall
ch = (CZ + CH + 0.008) - ic
cup_cutter = cone(cru1, cru1 + ck * ch, ch, (0, 0, ic + ch / 2.0), verts=96,
                  name="cup_cutter")
boolean(cup, cup_cutter)

cup_rim = torus((CR_BOT + ck * (CZ + CH - CZ)) - wall / 2.0, wall / 2.0,
                (0, 0, CZ + CH), maj=96, mino=12, name="cup_rim", mat=porcelain)

# handle: a torus in the vertical plane, trimmed where it would poke into
# the inside of the cup
h_major, h_minor, h_x, h_z = 0.0165, 0.0034, CR_TOP - 0.001, CZ + 0.031
handle = torus(h_major, h_minor, (h_x, 0, h_z), rot=(0, radians(90), 0),
               maj=64, mino=16, name="handle", mat=porcelain)
# trim the handle with a tapered cutter that follows the cup's inner wall,
# so it stays buried in the wall and never pokes into the cavity
zc0, zc1 = CZ - 0.004, CZ + CH + 0.010
hcut = cone(cru1 + ck * (zc0 - ic) - 0.0015,
            cru1 + ck * (zc1 - ic) - 0.0015,
            zc1 - zc0, (0, 0, (zc0 + zc1) / 2.0), verts=96,
            name="handle_cutter")
boolean(handle, hcut)

cup = join([cup, cup_rim, handle], "cup")
give(cup, porcelain)

# espresso, 6 mm below the rim
cz_coffee = CZ + CH - 0.007
r_coffee = cru1 + ck * (cz_coffee - ic)
coffee = cylinder(r_coffee + 0.0006, 0.004, (0, 0, cz_coffee - 0.002),
                  verts=96, name="espresso", mat=crema)

# ---- spoon ---------------------------------------------------------------
sp_x, sp_y = 0.086, -0.096
sp_az = radians(-20.0)                       # direction the handle points to
dx, dy = -sin(sp_az), cos(sp_az)             # local +Y maps to this vector
# local +Y of the spoon should point along (dx,dy): rotate about Z by az
bowl = sphere(0.0105, (sp_x, sp_y, 0.0034), scale=(1.05, 1.45, 0.42),
              rot=(0, 0, sp_az), seg=32, ring=16, name="spoon_bowl", mat=steel)
neck = sphere(0.0055, (sp_x + dx * 0.020, sp_y + dy * 0.020, 0.0024),
              scale=(0.8, 1.6, 0.4), rot=(0, 0, sp_az), seg=24, ring=12,
              name="spoon_neck", mat=steel)
handle_len = 0.088
hx0 = sp_x + dx * (0.026 + handle_len / 2.0)
hy0 = sp_y + dy * (0.026 + handle_len / 2.0)
sh = cube(0.0085, handle_len, 0.0020, (hx0, hy0, 0.0018),
          rot=(0, 0, sp_az), name="spoon_handle", mat=steel)
tip = sphere(0.0048, (sp_x + dx * (0.026 + handle_len), sp_y + dy * (0.026 + handle_len),
                      0.0018), scale=(0.85, 1.0, 0.4), rot=(0, 0, sp_az),
             seg=24, ring=12, name="spoon_tip", mat=steel)
spoon = join([bowl, neck, sh, tip], "spoon")
give(spoon, steel)

# ---- sugar cubes ---------------------------------------------------------
sug_positions = [(-0.122, -0.030, 0.0095, 14),
                 (-0.094, -0.058, 0.0095, -28),
                 (-0.120, -0.031, 0.0285, 41)]
for i, (x, y, z, a) in enumerate(sug_positions):
    s = 0.0190
    c = cube(s, s, s, (x, y, z), rot=(radians(2), radians(-3), radians(a)),
             name="sugar_%d" % i, mat=sugar)
    c.data.use_auto_smooth = True

# ---- croissant -----------------------------------------------------------
cx, cy = 0.100, 0.082           # centre of curvature
R = 0.046
a_lo, a_hi = -12.0, 138.0       # arc ends (degrees, in the croissant's frame)
parts = []
N = 11
for i in range(N):
    t = i / (N - 1.0)
    a = radians(a_lo + (a_hi - a_lo) * t)
    m = cos(math.pi * (t - 0.5))          # 0 at the ends, 1 in the middle
    r = 0.0072 + 0.0150 * (m ** 0.75)
    zs = 0.60
    px = cx + R * cos(a)
    py = cy + R * sin(a)
    pz = r * zs * 0.97 + 0.0012 * (1.0 - m)
    lob = sphere(r, (px, py, pz), scale=(1.0, 1.28, zs),
                 rot=(0, 0, a), seg=28, ring=14,
                 name="cr_%d" % i,
                 mat=crust if 0.13 < t < 0.87 else crust_dark)
    parts.append(lob)
croissant = join(parts, "croissant")
give(croissant, crust)
try:
    for p in croissant.data.polygons:
        p.use_smooth = True
    croissant.data.use_auto_smooth = True
    croissant.data.auto_smooth_angle = radians(50)
except Exception:
    pass

# a few crumbs
for i, (px, py) in enumerate([(0.157, 0.038), (0.172, 0.092),
                              (0.058, 0.132), (0.043, -0.116)]):
    sphere(0.0022, (px, py, 0.0012), scale=(1.0, 1.3, 0.6), seg=14, ring=8,
           name="crumb_%d" % i, mat=crust_dark)

# ---- camera --------------------------------------------------------------
target = bpy.data.objects.new("cam_target", None)
SCENE.collection.objects.link(target)
target.location = (0.020, 0.000, 0.028)

cam_data = bpy.data.cameras.new("camera")
cam_data.lens = 55.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.01
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = 8.0
cam = bpy.data.objects.new("camera", cam_data)
SCENE.collection.objects.link(cam)
az, el, dist = radians(20.0), radians(27.0), 0.60
cam.location = (target.location.x + dist * cos(el) * sin(az),
                target.location.y - dist * cos(el) * cos(az),
                target.location.z + dist * sin(el))
cam.constraints.new('TRACK_TO')
cam.constraints[0].target = target
cam.constraints[0].track_axis = 'TRACK_NEGATIVE_Z'
cam.constraints[0].up_axis = 'UP_Y'
SCENE.camera = cam
try:
    cam_data.dof.focus_object = cup
except Exception:
    cam_data.dof.focus_distance = (sqrt((cam.location.x) ** 2 +
                                        (cam.location.y + 0.0) ** 2))

# ---- lights --------------------------------------------------------------
def area_light(name, loc, power, size, color, aim_to):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.size = size
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    SCENE.collection.objects.link(ob)
    ob.location = loc
    d = (aim_to[0] - loc[0], aim_to[1] - loc[1], aim_to[2] - loc[2])
    L = sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
    import mathutils
    ob.rotation_euler = mathutils.Vector(d).to_track_quat('-Z', 'Y').to_euler()
    return ob


aim = (0.02, 0.0, 0.03)
area_light("key", (0.42, -0.30, 0.62), 55.0, 0.70, (1.00, 0.96, 0.89), aim)
area_light("fill", (-0.60, -0.45, 0.30), 14.0, 0.80, (0.84, 0.90, 1.00), aim)
area_light("rim", (-0.18, 0.55, 0.35), 22.0, 0.35, (1.00, 0.93, 0.80), aim)

# ---- world / render settings --------------------------------------------
world = bpy.data.worlds.get("world") or bpy.data.worlds.new("world")
SCENE.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
set_in(bg, ["Color"], (0.30, 0.33, 0.38))
set_in(bg, ["Strength"], 0.35)

SCENE.render.engine = 'CYCLES'
try:
    SCENE.cycles.device = 'CPU'
except Exception:
    pass
SCENE.cycles.samples = 128
try:
    SCENE.view_settings.view_transform = 'Filmic'
    SCENE.view_settings.look = 'Medium High Contrast'
except Exception:
    pass
SCENE.cycles.use_adaptive_sampling = True
