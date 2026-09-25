"""Café table scene built only from primitive meshes.

espresso cup + saucer, spoon, sugar cubes, croissant.
"""
import bpy
import math
import mathutils

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)


def mat(name, color, rough=0.5, metal=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if "Specular" in b.inputs:
        b.inputs["Specular"].default_value = spec
    return m


def setup(obj, material, name, smooth=True, angle=math.radians(40)):
    obj.name = name
    if material:
        obj.data.materials.append(material)
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = angle
    return obj


def cube(name, loc, scale, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = scale
    return setup(o, material, name, smooth=False)


def cyl(name, loc, radius, depth, material, rot=(0, 0, 0), verts=64):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot
    )
    return setup(bpy.context.object, material, name)


def cone(name, loc, r1, r2, depth, material, rot=(0, 0, 0), verts=64,
         caps='NGON'):
    bpy.ops.mesh.primitive_cone_add(
        vertices=verts, radius1=r1, radius2=r2, depth=depth,
        location=loc, rotation=rot, end_fill_type=caps,
    )
    return setup(bpy.context.object, material, name)


def sphere(name, loc, scale, material, rot=(0, 0, 0), segs=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segs, ring_count=rings, radius=1.0, location=loc, rotation=rot
    )
    o = bpy.context.object
    o.scale = scale
    return setup(o, material, name)


def torus(name, loc, major, minor, material, rot=(0, 0, 0), mseg=48, miseg=16):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major, minor_radius=minor, location=loc, rotation=rot,
        major_segments=mseg, minor_segments=miseg,
    )
    return setup(bpy.context.object, material, name)


# ----------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------
M_TABLE = mat("Table", (0.30, 0.17, 0.09), rough=0.45)
M_PORCELAIN = mat("Porcelain", (0.95, 0.94, 0.90), rough=0.18, spec=0.7)
M_COFFEE = mat("Coffee", (0.045, 0.018, 0.008), rough=0.12, spec=0.9)
M_CREMA = mat("Crema", (0.30, 0.165, 0.075), rough=0.55)
M_METAL = mat("Metal", (0.85, 0.86, 0.88), rough=0.30, metal=1.0)
M_SUGAR = mat("Sugar", (0.97, 0.96, 0.93), rough=0.55)
M_PASTRY = mat("Pastry", (0.52, 0.27, 0.085), rough=0.65)

# ----------------------------------------------------------------------------
# table
# ----------------------------------------------------------------------------
cube("Table", (0, 0, -0.02), (0.9, 0.9, 0.04), M_TABLE)

# ----------------------------------------------------------------------------
# saucer: wide dish + rim
# ----------------------------------------------------------------------------
SAUCER_TOP = 0.011
cyl("SaucerBase", (0, 0, 0.0055), 0.092, 0.011, M_PORCELAIN)
torus("SaucerRim", (0, 0, SAUCER_TOP - 0.001), 0.085, 0.0055, M_PORCELAIN)
torus("SaucerWellRing", (0, 0, SAUCER_TOP - 0.0005), 0.048, 0.0035, M_PORCELAIN)

# ----------------------------------------------------------------------------
# espresso cup
# ----------------------------------------------------------------------------
CUP_BOT = SAUCER_TOP - 0.001
CUP_H = 0.052
CUP_TOP = CUP_BOT + CUP_H
CUP_CZ = CUP_BOT + CUP_H / 2
cone("CupWall", (0, 0, CUP_CZ), 0.026, 0.038, CUP_H, M_PORCELAIN, caps='NOTHING')
torus("CupRim", (0, 0, CUP_TOP), 0.038, 0.0032, M_PORCELAIN)
cyl("CupFoot", (0, 0, CUP_BOT + 0.002), 0.021, 0.006, M_PORCELAIN)
cyl("CupBase", (0, 0, CUP_BOT + 0.006), 0.026, 0.004, M_PORCELAIN)

# coffee surface just below the rim, with a lighter crema disc
cyl("Coffee", (0, 0, CUP_TOP - 0.012), 0.0335, 0.008, M_COFFEE)
cyl("Crema", (0, 0, CUP_TOP - 0.0085), 0.0255, 0.0025, M_CREMA)

# handle
torus("CupHandle", (0.053, 0.0, CUP_CZ + 0.002), 0.021, 0.0055,
      M_PORCELAIN, rot=(math.pi / 2, 0, 0))

# ----------------------------------------------------------------------------
# spoon on the table to the right of the saucer (bowl + handle)
# ----------------------------------------------------------------------------
SP_Y = -0.052
sphere("SpoonBowl", (0.132, SP_Y, 0.0075), (0.024, 0.015, 0.0048), M_METAL,
       rot=(0, 0, math.radians(4)))
cube("SpoonHandle", (0.196, SP_Y - 0.003, 0.0085),
     (0.082, 0.009, 0.0038), M_METAL, rot=(0, 0, math.radians(-4)))

# ----------------------------------------------------------------------------
# sugar cubes
# ----------------------------------------------------------------------------
for i, (x, y, z) in enumerate([
    (-0.128, 0.050, 0.010),
    (-0.150, 0.050, 0.010),
    (-0.128, 0.028, 0.010),
    (-0.150, 0.028, 0.010),
    (-0.139, 0.039, 0.030),
]):
    cube("Sugar%d" % i, (x, y, z), (0.020, 0.020, 0.020), M_SUGAR,
         rot=(0, 0, math.radians((i % 3 - 1) * 4)))

# ----------------------------------------------------------------------------
# croissant: spheres swept along a tapering crescent arc
# ----------------------------------------------------------------------------
CROT_C = (-0.030, -0.135)
AMAX = 1.15
N = 11
R = 0.052
rotz = math.radians(25)


def rot2(x, y):
    c, s = math.cos(rotz), math.sin(rotz)
    return (x * c - y * s + CROT_C[0], x * s + y * c + CROT_C[1])


for i in range(N):
    a = -AMAX + 2 * AMAX * i / (N - 1)
    t = abs(a) / AMAX
    px = R * math.sin(a)
    py = R * math.cos(a) - R
    # taper towards the horns, bulge in the middle
    r = 0.024 * (1.0 - 0.72 * t ** 1.6) + 0.002
    x, y = rot2(px, py)
    sphere("Croissant%d" % i, (x, y, r * 0.72),
           (r, r, r * 0.72), M_PASTRY, segs=24, rings=12)

# ----------------------------------------------------------------------------
# camera + lights
# ----------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 60
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = mathutils.Vector((0.20, -0.52, 0.40))
look = mathutils.Vector((0.0, -0.03, 0.015))
cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam


def area(name, loc, energy, size, target=(0, 0, 0)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (mathutils.Vector(target) - mathutils.Vector(loc)) \
        .to_track_quat('-Z', 'Y').to_euler()
    return o


area("Key", (-0.32, -0.38, 0.55), 8, 0.5, (0, 0, 0.03))
area("Fill", (0.45, -0.12, 0.35), 2.5, 0.6, (0, 0, 0.03))
area("Rim", (0.10, 0.45, 0.40), 5, 0.6, (0, 0, 0.03))

world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.07, 0.07, 0.09, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
scn = bpy.context.scene
scn.view_settings.exposure = -0.7

# render settings (harness overrides engine/res but keep sensible values)
scn = bpy.context.scene
scn.render.film_transparent = False
scn.view_settings.look = 'Medium High Contrast' if 'Medium High Contrast' in \
    [l.name for l in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items] else 'None'