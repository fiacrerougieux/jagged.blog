"""Café table scene built only from primitive meshes:
espresso cup on a saucer, a spoon, sugar cubes and a croissant.
"""

import bpy
import math
from mathutils import Vector

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def make_material(name, color, rough=0.4, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return mat


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def smooth(obj, angle=40.0):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    obj.data.use_auto_smooth = True
    obj.data.auto_smooth_angle = math.radians(angle)


def boolean_diff(target, cutter):
    m = target.modifiers.new(name="bool", type='BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.solver = 'EXACT'
    m.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def add_cylinder(r, depth, loc, verts=48, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=loc, rotation=rot)
    return bpy.context.object


def add_cone(r1, r2, depth, loc, verts=48, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2,
                                    depth=depth, location=loc, rotation=rot)
    return bpy.context.object


def add_sphere(radius, loc, segs=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings,
                                         radius=radius, location=loc)
    return bpy.context.object


def add_cube(size, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc, rotation=rot)
    return bpy.context.object


def add_torus(major, minor, loc, rot=(0, 0, 0), maj_seg=48, min_seg=16):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=maj_seg,
                                     minor_segments=min_seg,
                                     location=loc, rotation=rot)
    return bpy.context.object


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


# ----------------------------------------------------------------------------
# Scene reset
# ----------------------------------------------------------------------------
clear_scene()

# Materials
MAT_WOOD = make_material("Wood", (0.19, 0.085, 0.032), rough=0.5)
MAT_CERAMIC = make_material("Ceramic", (0.93, 0.92, 0.88), rough=0.14)
MAT_COFFEE = make_material("Coffee", (0.045, 0.018, 0.006), rough=0.08)
MAT_CREMA = make_material("Crema", (0.34, 0.17, 0.06), rough=0.35)
MAT_METAL = make_material("Metal", (0.86, 0.86, 0.88), rough=0.18, metal=1.0)
MAT_SUGAR = make_material("Sugar", (0.95, 0.95, 0.94), rough=0.5)
MAT_CROISSANT = make_material("Croissant", (0.60, 0.32, 0.10), rough=0.38)

# ----------------------------------------------------------------------------
# Table top
# ----------------------------------------------------------------------------
table = add_cylinder(0.42, 0.03, (0.0, 0.0, -0.015), verts=64)
assign(table, MAT_WOOD)
smooth(table, 30)

# ----------------------------------------------------------------------------
# Saucer
#   plate disc + raised outer rim + shallow well carved in the middle
# ----------------------------------------------------------------------------
saucer = add_cylinder(0.062, 0.006, (0.0, 0.0, 0.003), verts=64)
assign(saucer, MAT_CERAMIC)

rim = add_torus(0.056, 0.0045, (0.0, 0.0, 0.005), maj_seg=64, min_seg=16)
assign(rim, MAT_CERAMIC)
# join rim into saucer
bpy.ops.object.select_all(action='DESELECT')
rim.select_set(True)
saucer.select_set(True)
bpy.context.view_layer.objects.active = saucer
bpy.ops.object.join()

# carve shallow well
well = add_sphere(0.202, (0.0, 0.0, 0.204), segs=64, rings=32)
boolean_diff(saucer, well)
smooth(saucer, 30)

# ----------------------------------------------------------------------------
# Espresso cup (tapered body with hollow interior) + handle
# ----------------------------------------------------------------------------
CUP_BASE = 0.004
cup = add_cone(0.020, 0.030, 0.060, (0.0, 0.0, CUP_BASE + 0.030), verts=64)
assign(cup, MAT_CERAMIC)

inner = add_cone(0.016, 0.026, 0.062, (0.0, 0.0, CUP_BASE + 0.006 + 0.031),
                 verts=48)
boolean_diff(cup, inner)
smooth(cup, 32)

handle = add_torus(0.0115, 0.0033, (0.035, 0.0, 0.046),
                   rot=(math.pi / 2.0, 0.0, 0.0), maj_seg=40, min_seg=14)
assign(handle, MAT_CERAMIC)
smooth(handle, 40)

# Coffee surface + crema edge
coffee = add_cylinder(0.0225, 0.0025, (0.0, 0.0, 0.0555), verts=48)
assign(coffee, MAT_COFFEE)
crema = add_torus(0.0215, 0.0016, (0.0, 0.0, 0.0558), maj_seg=48, min_seg=12)
assign(crema, MAT_CREMA)
smooth(crema, 40)

# ----------------------------------------------------------------------------
# Spoon  (flattened handle + oval bowl)
# ----------------------------------------------------------------------------
spoon_rot = math.radians(-40.0)
spoon_c = Vector((0.140, -0.045, 0.0))

# handle: thin flat box
handle_len = 0.090
sp = add_cube(1.0, (0, 0, 0))
sp.scale = (handle_len / 2.0, 0.0042, 0.0015)
sp.rotation_euler = (0, 0, spoon_rot)
# local +x axis direction
d = Vector((math.cos(spoon_rot), math.sin(spoon_rot), 0.0))
sp.location = spoon_c + d * (handle_len / 2.0)
sp.location.z = 0.006
assign(sp, MAT_METAL)
smooth(sp, 30)

# bowl: squashed sphere at the inner end of the handle
bowl = add_sphere(0.014, (0, 0, 0), segs=32, rings=16)
bowl.scale = (1.30, 0.90, 0.20)
bowl.rotation_euler = (0, 0, spoon_rot)
bowl.location = spoon_c + d * (-0.006)
bowl.location.z = 0.0055
assign(bowl, MAT_METAL)
smooth(bowl, 40)

# ----------------------------------------------------------------------------
# Sugar cubes
# ----------------------------------------------------------------------------
sugar_specs = [
    ((0.098, 0.045, 0.0), math.radians(14.0)),
    ((0.112, 0.026, 0.0), math.radians(-22.0)),
]
for i, (loc, rz) in enumerate(sugar_specs):
    sz = 0.017
    c = add_cube(sz, (loc[0], loc[1], 0.0085 + loc[2]), rot=(0, 0, rz))
    assign(c, MAT_SUGAR)
    bev = c.modifiers.new("bev", 'BEVEL')
    bev.width = 0.0012
    bev.segments = 2
    bpy.context.view_layer.objects.active = c
    bpy.ops.object.modifier_apply(modifier=bev.name)
    smooth(c, 50)

# ----------------------------------------------------------------------------
# Croissant  (crescent of overlapping ellipsoids)
# ----------------------------------------------------------------------------
croissant_parts = []
cx, cy = -0.055, -0.005
R = 0.050
n = 13
span = math.radians(82.0)
crot = math.pi  # crescent sits left of saucer, opening toward the cup
for i in range(n):
    a = -span + (2.0 * span) * i / (n - 1) + crot
    t = abs((-span + (2.0 * span) * i / (n - 1))) / span
    px = cx + R * math.cos(a)
    py = cy + R * math.sin(a)
    length = 0.015 * (1.0 - 0.50 * t)
    width = 0.0155 * (1.0 - 0.42 * t)
    height = 0.016 * (1.0 - 0.36 * t)
    pz = height + 0.011 * t * t
    e = add_sphere(1.0, (px, py, pz), segs=24, rings=14)
    e.scale = (length, width, height)
    e.rotation_euler = (0, 0, a + math.pi / 2.0)
    croissant_parts.append(e)

# join
bpy.ops.object.select_all(action='DESELECT')
for e in croissant_parts:
    e.select_set(True)
bpy.context.view_layer.objects.active = croissant_parts[0]
bpy.ops.object.join()
croissant = bpy.context.object
assign(croissant, MAT_CROISSANT)
smooth(croissant, 45)

# ----------------------------------------------------------------------------
# Camera
# ----------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 48.0
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (0.29, -0.40, 0.25)
look_at(cam, (0.0, -0.005, 0.030))
bpy.context.scene.camera = cam

# ----------------------------------------------------------------------------
# Lights
# ----------------------------------------------------------------------------
def add_area(name, loc, energy, size, target=(0, 0, 0.03)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    look_at(o, target)
    return o

add_area("Key", (0.38, -0.30, 0.52), 22, 0.45)
add_area("Fill", (-0.42, -0.22, 0.28), 9, 0.65)
add_area("Rim", (-0.08, 0.42, 0.38), 14, 0.45)

# world
world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.50, 0.58, 0.70, 1.0)
bg.inputs[1].default_value = 0.25

print("Scene built with primitives only.")