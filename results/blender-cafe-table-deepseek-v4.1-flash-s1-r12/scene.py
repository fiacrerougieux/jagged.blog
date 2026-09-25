"""Cafe table scene built only from Blender primitive meshes."""

import bpy
import bmesh
import math
from mathutils import Vector, Euler

# ---------------------------------------------------------------- clean scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
              bpy.data.cameras):
    for item in list(block):
        block.remove(item)


# ---------------------------------------------------------------- materials
def make_material(name, color, roughness=0.5, metallic=0.0, specular=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = specular
    # keep a recognisable viewport colour too
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


MAT = {
    "porcelain": make_material("Porcelain", (0.88, 0.87, 0.82), 0.18, 0.0, 0.6),
    "table":     make_material("Table", (0.16, 0.075, 0.028), 0.55),
    "metal":     make_material("Metal", (0.72, 0.72, 0.74), 0.45, 1.0),
    "coffee":    make_material("Coffee", (0.23, 0.095, 0.025), 0.4),
    "crema":     make_material("Crema", (0.29, 0.140, 0.042), 0.5),
    "sugar":     make_material("Sugar", (0.88, 0.87, 0.83), 0.7),
    "croissant": make_material("Croissant", (0.24, 0.095, 0.016), 0.72),
    "floor":     make_material("Floor", (0.30, 0.28, 0.26), 0.75),
}


def add(obj, material, smooth=True, name=None):
    if name:
        obj.name = name
    obj.data.materials.append(material)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


# ---------------------------------------------------------------- table
bpy.ops.mesh.primitive_cylinder_add(radius=0.34, depth=0.028, location=(0, 0, -0.014))
add(bpy.context.active_object, MAT["table"], smooth=False, name="TableTop")

bpy.ops.mesh.primitive_cylinder_add(radius=0.030, depth=0.44, location=(0, 0, -0.248))
add(bpy.context.active_object, MAT["table"], name="TableColumn")

bpy.ops.mesh.primitive_cylinder_add(radius=0.135, depth=0.022, location=(0, 0, -0.468))
add(bpy.context.active_object, MAT["table"], smooth=False, name="TableBase")

# floor
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, -0.480))
floor = bpy.context.active_object
floor.scale = (1.0, 1.0, 0.01)
add(floor, MAT["floor"], smooth=False, name="Floor")

TOP = 0.0  # table surface height


# ---------------------------------------------------------------- saucer
SAUCER = Vector((-0.055, 0.005, 0.0))
bpy.ops.mesh.primitive_cylinder_add(radius=0.063, depth=0.006,
                                    location=SAUCER + Vector((0, 0, 0.003)))
add(bpy.context.active_object, MAT["porcelain"], smooth=False, name="SaucerBase")
bpy.ops.mesh.primitive_cone_add(radius1=0.055, radius2=0.064, depth=0.008,
                                location=SAUCER + Vector((0, 0, 0.009)))
add(bpy.context.active_object, MAT["porcelain"], name="SaucerLip")
bpy.ops.mesh.primitive_torus_add(major_radius=0.060, minor_radius=0.0035,
                                 major_segments=64, minor_segments=12,
                                 location=SAUCER + Vector((0, 0, 0.014)))
add(bpy.context.active_object, MAT["porcelain"], name="SaucerRim")

# ---------------------------------------------------------------- cup
CUP_R1 = 0.023   # bottom
CUP_R2 = 0.030   # top
CUP_H = 0.063
cup_base_z = 0.010
bpy.ops.mesh.primitive_cone_add(radius1=CUP_R1, radius2=CUP_R2, depth=CUP_H,
                                vertices=64, end_fill_type='NOTHING',
                                location=SAUCER + Vector((0, 0, cup_base_z + CUP_H / 2)))
add(bpy.context.active_object, MAT["porcelain"], name="CupBody")

# coffee fill
cup_top = cup_base_z + CUP_H
bpy.ops.mesh.primitive_cylinder_add(radius=CUP_R2 * 0.86, depth=0.006, vertices=64,
                                    location=SAUCER + Vector((0, 0, cup_top - 0.006)))
add(bpy.context.active_object, MAT["crema"], smooth=False, name="Coffee")

# rolled rim gives the ceramic rim some thickness
bpy.ops.mesh.primitive_torus_add(major_radius=CUP_R2 - 0.0015, minor_radius=0.0022,
                                 major_segments=64, minor_segments=12,
                                 location=SAUCER + Vector((0, 0, cup_top)))
add(bpy.context.active_object, MAT["porcelain"], name="CupRim")

# handle
HANDLE = Euler((math.radians(90), 0, math.radians(15)), 'XYZ')
bpy.ops.mesh.primitive_torus_add(major_radius=0.0105, minor_radius=0.0028,
                                 major_segments=48, minor_segments=12,
                                 location=SAUCER + Vector((0.0295, 0.0, 0.038)),
                                 rotation=HANDLE)
add(bpy.context.active_object, MAT["porcelain"], name="CupHandle")


# ---------------------------------------------------------------- spoon
def make_spoon(center, phi):
    rot = (0, 0, phi)
    d = Vector((math.cos(phi), math.sin(phi), 0))
    parts = []
    # bowl (shallow flattened ellipsoid)
    bowl_loc = Vector(center) + d * 0.036 + Vector((0, 0, 0.0050))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=1.0,
                                         location=bowl_loc, rotation=rot)
    bowl = bpy.context.active_object
    bowl.scale = (0.0210, 0.0135, 0.0050)
    parts.append(add(bowl, MAT["metal"], name="SpoonBowl"))
    # neck joins bowl to handle
    neck_loc = Vector(center) + d * 0.008 + Vector((0, 0, 0.0042))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=neck_loc, rotation=rot)
    neck = bpy.context.active_object
    neck.scale = (0.0200, 0.0055, 0.0030)
    parts.append(add(neck, MAT["metal"], smooth=False, name="SpoonNeck"))
    # handle
    handle_loc = Vector(center) - d * 0.026 + Vector((0, 0, 0.0038))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=handle_loc, rotation=rot)
    handle = bpy.context.active_object
    handle.scale = (0.0480, 0.0048, 0.0030)
    parts.append(add(handle, MAT["metal"], smooth=False, name="SpoonHandle"))
    # unify into one object so it reads as a single utensil
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()


make_spoon(Vector((-0.010, -0.080, 0.0)), math.radians(207))


# ---------------------------------------------------------------- sugar cubes
def make_sugar_cube(loc, size=0.016, zrot=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc,
                                    rotation=(0, 0, zrot))
    cube = bpy.context.active_object
    cube.scale = (size, size, size)
    # bevel-ish: use a slightly smaller top? keep simple
    add(cube, MAT["sugar"], smooth=False, name="SugarCube")
    return cube


make_sugar_cube(Vector((-0.152, 0.090, 0.0080)), zrot=math.radians(5))
make_sugar_cube(Vector((-0.136, 0.090, 0.0080)), zrot=math.radians(-8))
make_sugar_cube(Vector((-0.144, 0.090, 0.0242)), zrot=math.radians(19))
make_sugar_cube(Vector((-0.168, 0.070, 0.0080)), zrot=math.radians(12))


# ---------------------------------------------------------------- croissant
def make_croissant(center, zrot=0.0, major=0.055, minor=0.021):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=96, minor_segments=20,
                                     location=(0, 0, 0))
    obj = bpy.context.active_object
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)

    keep_limit = math.radians(148.0)

    # delete the "back" arc to open the crescent
    doomed = []
    for v in bm.verts:
        ang = math.atan2(v.co.y, v.co.x)
        if abs(ang) > keep_limit:
            doomed.append(v)
    bmesh.ops.delete(bm, geom=doomed, context='VERTS')

    # taper the arms, arch the body, add baked ridges
    for v in bm.verts:
        ang = math.atan2(v.co.y, v.co.x)
        t = max(-1.0, min(1.0, ang / keep_limit))
        taper = 0.13 + 0.87 * (math.cos(t * math.pi / 2) ** 0.95)
        phase = t * math.pi * 6.0
        ridge = 1.0 + 0.16 * math.cos(phase)
        ring = Vector((major * math.cos(ang), major * math.sin(ang), 0.0))
        arch = 0.018 * (1.0 - t * t)
        offset = v.co - ring
        v.co = ring + offset * (taper * ridge)
        v.co.z += arch

    # close the open ends
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bm.to_mesh(me)
    bm.free()

    # sit on the table and place it
    min_z = min((obj.matrix_world @ v.co).z for v in me.vertices)
    obj.location = Vector(center) - Vector((0, 0, min_z))
    obj.rotation_euler = (0, 0, zrot)
    add(obj, MAT["croissant"], name="Croissant")


make_croissant(Vector((0.118, 0.050, 0.0)), zrot=math.radians(28),
               major=0.048, minor=0.019)


# ---------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 52
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = Vector((0.045, -0.50, 0.245))
target = Vector((-0.02, 0.02, 0.03))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam


# ---------------------------------------------------------------- lights
def make_area(name, loc, energy, size, rot, color=(1.0, 1.0, 1.0)):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = rot
    bpy.context.collection.objects.link(obj)
    return obj


make_area("KeyLight", (-0.42, -0.38, 0.52), 18.0, 0.35,
          (math.radians(52), 0, math.radians(-42)), (1.0, 0.90, 0.78))
make_area("FillLight", (0.48, -0.22, 0.34), 6.0, 0.45,
          (math.radians(62), 0, math.radians(58)), (0.92, 0.95, 1.0))
make_area("RimLight", (0.18, 0.50, 0.40), 7.0, 0.30,
          (math.radians(118), 0, math.radians(200)), (1.0, 0.85, 0.7))

world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.09, 0.075, 0.055, 1.0)
bg.inputs["Strength"].default_value = 0.4
bpy.context.scene.view_settings.exposure = -0.5

# nice filmic output if available
try:
    bpy.context.scene.view_settings.view_transform = 'Filmic'
except Exception:
    pass