# -*- coding: utf-8 -*-
"""
Cafe table scene, built ONLY from primitive meshes
(cube, cylinder, cone, sphere, torus) placed with transforms.

Contents: round bistro table, espresso cup on a saucer, a spoon,
three sugar cubes, a croissant (plus a few crumbs).
"""

import bpy
import math
from mathutils import Vector

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _clear():
    """Start from an empty scene (factory startup gives objects we don't want)."""
    bpy.ops.object.select_all(action='SELECT')
    if bpy.context.selected_objects:
        bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras):
        for d in list(block):
            if d.users == 0:
                block.remove(d)


_clear()

COLLECTION = bpy.context.scene.collection


def _finish(obj, name, loc, rot, scale, mat):
    """The primitive ops bake the size into the mesh, so the object scale here
    is taken verbatim as the world scale."""
    obj.name = name
    obj.location = Vector(loc)
    obj.rotation_euler = rot
    obj.scale = Vector((obj.scale.x * scale[0],
                        obj.scale.y * scale[1],
                        obj.scale.z * scale[2]))
    if mat is not None:
        obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = False
    return obj


def box(name="Cube", size=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
        mat=None):
    """scale = the three full edge lengths of the box."""
    bpy.ops.mesh.primitive_cube_add(size=size, location=(0, 0, 0))
    return _finish(bpy.context.active_object, name, loc, rot, scale, mat)


def cyl(name="Cylinder", r=1.0, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0),
        scale=(1, 1, 1), mat=None, verts=64, cap='NGON', smooth=False):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=(0, 0, 0), end_fill_type=cap)
    return _smooth(_finish(bpy.context.active_object, name, loc, rot, scale,
                           mat), smooth)


def cone(name="Cone", r1=1.0, r2=0.0, depth=1.0, loc=(0, 0, 0), rot=(0, 0, 0),
         scale=(1, 1, 1), mat=None, verts=64, cap='NGON', smooth=False,
         direction=None):
    if direction is not None:
        rot = Vector(direction).normalized().to_track_quat('Z', 'Y').to_euler()
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2,
                                    depth=depth, location=(0, 0, 0),
                                    end_fill_type=cap)
    return _smooth(_finish(bpy.context.active_object, name, loc, rot, scale,
                           mat), smooth)


def sph(name="Sphere", r=1.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
        mat=None, segs=32, rings=16, smooth=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings,
                                         radius=r, location=(0, 0, 0))
    return _smooth(_finish(bpy.context.active_object, name, loc, rot, scale,
                           mat), smooth)


def tor(name="Torus", R=1.0, r=0.1, loc=(0, 0, 0), rot=(0, 0, 0),
        scale=(1, 1, 1), mat=None, smooth=True, major_seg=48, minor_seg=16):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r,
                                     major_segments=major_seg,
                                     minor_segments=minor_seg,
                                     location=(0, 0, 0))
    return _smooth(_finish(bpy.context.active_object, name, loc, rot, scale,
                           mat), smooth)


def _smooth(o, on):
    if on:
        for p in o.data.polygons:
            p.use_smooth = True
        if hasattr(o.data, "use_auto_smooth"):
            o.data.use_auto_smooth = True
            o.data.auto_smooth_angle = math.radians(60)
    return o


def setin(node, names, value):
    """Set the first input that exists (Blender version proofing)."""
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def material(name, color, rough=0.5, metal=0.0, spec=0.5, sss=0.0,
             sss_radius=None, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    setin(b, ["Base Color"], (*color, 1.0))
    setin(b, ["Roughness"], rough)
    setin(b, ["Metallic"], metal)
    setin(b, ["Specular IOR Level", "Specular"], spec)
    if sss:
        setin(b, ["Subsurface Weight", "Subsurface"], sss)
        if sss_radius:
            setin(b, ["Subsurface Radius"], sss_radius)
    setin(b, ["IOR", "Index of Refraction"], ior)
    return m


def aim(obj, target):
    """Point an object's -Z axis at a world position."""
    d = Vector(target) - Vector(obj.location)
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def link_light(name, kind, loc, energy, color=(1, 1, 1), target=(0, 0, 0),
               **kw):
    ld = bpy.data.lights.new(name, kind)
    for k, v in kw.items():
        if hasattr(ld, k):
            setattr(ld, k, v)
    ld.energy = energy
    ld.color = color
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    COLLECTION.objects.link(o)
    aim(o, target)
    return o


def place_group(objs, offset, angle_z=0.0):
    """Rotate a locally-built group about Z, then move it into place."""
    c, s = math.cos(angle_z), math.sin(angle_z)
    for o in objs:
        p = Vector(o.location)
        p = Vector((p.x * c - p.y * s, p.x * s + p.y * c, p.z)) + Vector(offset)
        o.location = p
        o.rotation_euler = (o.rotation_euler[0], o.rotation_euler[1],
                            o.rotation_euler[2] + angle_z)


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
porcelain = material("Porcelain", (0.80, 0.795, 0.78), rough=0.15, spec=0.4)
porcelain_deep = material("PorcelainDeep", (0.62, 0.615, 0.605), rough=0.12)
coffee = material("Coffee", (0.085, 0.032, 0.013), rough=0.32, spec=0.35)
coffee_dark = material("CoffeeDark", (0.028, 0.010, 0.004), rough=0.26, spec=0.3)
crema = material("Crema", (0.42, 0.215, 0.09), rough=0.5, spec=0.25)
steel = material("Steel", (0.62, 0.63, 0.65), rough=0.18, metal=1.0, spec=0.9)
sugar = material("Sugar", (0.86, 0.855, 0.83), rough=0.40, sss=0.08,
                 sss_radius=(0.008, 0.006, 0.004))
crust_a = material("CrustA", (0.315, 0.125, 0.038), rough=0.45, spec=0.28)
crust_b = material("CrustB", (0.455, 0.205, 0.065), rough=0.40, spec=0.28)
crust_c = material("CrustC", (0.22, 0.082, 0.024), rough=0.50, spec=0.25)
floor_mat = material("Floor", (0.045, 0.040, 0.038), rough=0.9)

# wood with a soft procedural grain (material nodes only - geometry stays primitive)
wood = material("Wood", (0.20, 0.093, 0.042), rough=0.42, spec=0.30)
nt = wood.node_tree
bsdf = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (1.0, 16.0, 1.0)
wave = nt.nodes.new("ShaderNodeTexNoise")
wave.inputs["Scale"].default_value = 7.0
wave.inputs["Detail"].default_value = 6.0
wave.inputs["Roughness"].default_value = 0.55
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.34
ramp.color_ramp.elements[0].color = (0.088, 0.034, 0.013, 1)
ramp.color_ramp.elements[1].position = 0.72
ramp.color_ramp.elements[1].color = (0.215, 0.098, 0.042, 1)
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
nt.links.new(wave.outputs["Color"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

# --------------------------------------------------------------------------
# table (round bistro top, pedestal, base, floor)
# --------------------------------------------------------------------------
cyl("TableTop", r=0.36, depth=0.026, loc=(0, 0, -0.013), mat=wood, verts=128)
tor("TableEdge", R=0.355, r=0.0125, loc=(0, 0, -0.024), mat=wood)
cyl("Pedestal", r=0.026, depth=0.66, loc=(0, 0, -0.356), mat=porcelain_deep,
    verts=48)
cone("PedestalCollar", r1=0.058, r2=0.027, depth=0.055, loc=(0, 0, -0.064),
     mat=porcelain_deep, verts=48)
cone("TableFoot", r1=0.175, r2=0.055, depth=0.038, loc=(0, 0, -0.700),
     mat=porcelain_deep, verts=64)
box("Floor", loc=(0, 0, -0.7525), scale=(6, 6, 0.05), mat=floor_mat)

# --------------------------------------------------------------------------
# saucer + espresso cup  (built around the origin, then shifted as a unit)
# --------------------------------------------------------------------------
cup = []
# --- saucer: foot ring + flaring skirt + top + rolled rim
cup.append(cyl("SaucerFoot", r=0.0305, depth=0.0068, loc=(0, 0, 0.0034),
               mat=porcelain, verts=96))
cup.append(cone("SaucerSkirt", r1=0.0305, r2=0.0580, depth=0.0088,
                loc=(0, 0, 0.0096), mat=porcelain, verts=96, cap='NOTHING'))
cup.append(cyl("SaucerTop", r=0.0580, depth=0.0016, loc=(0, 0, 0.0130),
               mat=porcelain, verts=96))
cup.append(tor("SaucerRim", R=0.0580, r=0.0030, loc=(0, 0, 0.0138),
               mat=porcelain))
cup.append(tor("SaucerGroove", R=0.0400, r=0.0022, loc=(0, 0, 0.0140),
               mat=porcelain_deep))
# --- cup: one watertight truncated cone, so the handle can be buried in it
CZ0 = 0.0144                     # cup bottom, resting inside the saucer well
CH = 0.055
RIM = CZ0 + CH
cup.append(cone("CupBody", r1=0.0240, r2=0.0295, depth=CH,
                loc=(0, 0, CZ0 + CH / 2), mat=porcelain, verts=96))
cup.append(tor("CupRim", R=0.0276, r=0.0030, loc=(0, 0, RIM), mat=porcelain))
# --- espresso: a thin disc whose top face sits just under the rim crest
TOP = RIM + 0.0018
cup.append(cyl("Coffee", r=0.0270, depth=0.010, loc=(0, 0, TOP - 0.005),
               mat=coffee, verts=96))
cup.append(cyl("CoffeeHeart", r=0.0165, depth=0.0104,
               loc=(0, 0, TOP + 0.0002 - 0.0052), mat=coffee_dark, verts=64))
cup.append(tor("CoffeeEdge", R=0.0242, r=0.0014, loc=(0, 0, TOP - 0.0012),
               mat=crema))
# --- handle: a torus standing in a vertical plane that contains the cup axis.
#     Its inner half is buried in the convex (watertight) cup body, so it reads
#     as a handle joined to the wall at two points.
A = 34.0                         # azimuth the handle points at (in profile)
HA = math.radians(A)
HD, HR, HT = 0.0215, 0.0180, 0.0036
# after rot=(0, 90deg, ez) the ring's in-plane horizontal axis is
# (-sin ez, cos ez, 0); we want that to be the radial direction (cos HA, sin HA)
cup.append(tor("CupHandle", R=HR, r=HT,
               loc=(HD * math.cos(HA), HD * math.sin(HA), CZ0 + 0.56 * CH),
               rot=(0, math.radians(90), HA - math.radians(90)),
               mat=porcelain))

place_group(cup, (-0.030, 0.050, 0.0))

# --------------------------------------------------------------------------
# spoon, lying on the table at the front right
# --------------------------------------------------------------------------
spoon = []
spoon.append(sph("SpoonBowl", r=1.0, loc=(0, 0.0480, 0.0014),
                 scale=(0.0075, 0.0130, 0.0014), mat=steel))
spoon.append(box("SpoonNeck", loc=(0, 0.0255, 0.0012),
                 scale=(0.0055, 0.0260, 0.0012), mat=steel))
spoon.append(box("SpoonHandle", loc=(0, -0.0140, 0.0011),
                 scale=(0.0085, 0.0500, 0.0011), mat=steel))
spoon.append(sph("SpoonTip", r=1.0, loc=(0, -0.0430, 0.0010),
                 scale=(0.0058, 0.0085, 0.0010), mat=steel))
place_group(spoon, (0.108, -0.048, 0.0), math.radians(28))

# --------------------------------------------------------------------------
# sugar cubes: a stack of two plus one lying beside it (back right)
# --------------------------------------------------------------------------
SC = 0.0185
box("Sugar1", size=SC, loc=(0.086, 0.126, SC / 2),
    rot=(0, 0, math.radians(14)), mat=sugar)
box("Sugar2", size=SC, loc=(0.088, 0.128, SC * 1.5 - 0.0006),
    rot=(0, 0, math.radians(33)), mat=sugar)
box("Sugar3", size=SC, loc=(0.136, 0.101, SC / 2),
    rot=(0, 0, math.radians(-22)), mat=sugar)

# --------------------------------------------------------------------------
# croissant: spheres along an arc + two tapered horn tips (front left)
# --------------------------------------------------------------------------
cro = []
ARC_R = 0.047
SPAN = math.radians(150)
PROF = [0.0165, 0.0210, 0.0235, 0.0210, 0.0165]
MATS = [crust_a, crust_b, crust_b, crust_b, crust_a]
N = len(PROF)
for i in range(N):
    t = math.radians(90) - SPAN / 2 + SPAN * i / (N - 1)
    rr = PROF[i]
    x = ARC_R * math.cos(t)
    y = ARC_R * math.sin(t) - ARC_R          # centre the crescent on the origin
    cro.append(sph("Croissant%d" % i, r=rr, loc=(x, y, rr * 0.76),
                   rot=(0, 0, t), scale=(0.86, 0.98, 0.78), mat=MATS[i]))


def horn(idx, sign):
    t = math.radians(90) + sign * SPAN / 2
    dirv = Vector((-math.sin(t) * sign, math.cos(t) * sign, -0.34)).normalized()
    j = 0 if sign < 0 else N - 1
    base = Vector((ARC_R * math.cos(t), ARC_R * math.sin(t) - ARC_R,
                   PROF[j] * 0.72))
    length = 0.030
    c = cone("CroissantTip%d" % idx, r1=PROF[j] * 0.72, r2=0.0012, depth=length,
             loc=(base + dirv * (length / 2)), mat=crust_a, verts=32,
             direction=dirv)
    return c


cro.append(horn(0, -1))
cro.append(horn(1, 1))
place_group(cro, (-0.100, -0.052, 0.0), math.radians(-30))

# crumbs
for i, (cx, cy, cr) in enumerate([(0.010, -0.115, 0.0018), (-0.028, -0.140, 0.0014),
                                  (0.040, -0.020, 0.0015), (-0.005, -0.020, 0.0012),
                                  (0.052, -0.098, 0.0011)]):
    sph("Crumb%d" % i, r=cr, loc=(cx, cy, cr * 0.45), scale=(1, 1.4, 0.55),
        mat=crust_a, segs=12, rings=6)

# --------------------------------------------------------------------------
# camera + lights
# --------------------------------------------------------------------------
TARGET = (-0.004, 0.020, 0.026)
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 50
cam_data.sensor_width = 36
cam_data.clip_start = 0.008
cam = bpy.data.objects.new("Camera", cam_data)
cam.location = (0.40, -0.55, 0.42)
COLLECTION.objects.link(cam)
aim(cam, TARGET)
bpy.context.scene.camera = cam

link_light("Key", 'AREA', (0.50, -0.40, 0.62), 14.0,
           color=(1.0, 0.94, 0.85), size=0.24, target=TARGET)
link_light("Fill", 'AREA', (-0.60, -0.40, 0.35), 4.0,
           color=(0.85, 0.90, 1.0), size=1.2, target=TARGET)
link_light("Rim", 'SPOT', (-0.35, 0.62, 0.42), 10.0,
           color=(1.0, 0.90, 0.76), spot_size=math.radians(60), blend=0.5,
           target=(0.0, 0.03, 0.05))

world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.055, 0.05, 0.048, 1.0)
bg.inputs[1].default_value = 1.0

# --------------------------------------------------------------------------
# render settings (the harness overrides engine/samples/resolution)
# --------------------------------------------------------------------------
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 96
sc.cycles.use_denoising = False
for prop, val in (("sample_clamp_indirect", 6.0), ("max_bounces", 6),
                  ("diffuse_bounces", 2), ("glossy_bounces", 3),
                  ("transmission_bounces", 0), ("volume_bounces", 0),
                  ("caustics_reflective", False), ("caustics_refractive", False)):
    if hasattr(sc.cycles, prop):
        setattr(sc.cycles, prop, val)
if hasattr(sc.cycles, "pixel_filter_type"):
    sc.cycles.pixel_filter_type = 'GAUSSIAN'
if hasattr(sc.cycles, "pixel_filter_width"):
    sc.cycles.pixel_filter_width = 1.6
sc.view_settings.view_transform = 'Filmic'
try:
    sc.view_settings.look = 'Medium High Contrast'
except Exception:
    pass
sc.render.resolution_x = 960
sc.render.resolution_y = 640
sc.render.image_settings.file_format = 'PNG'
