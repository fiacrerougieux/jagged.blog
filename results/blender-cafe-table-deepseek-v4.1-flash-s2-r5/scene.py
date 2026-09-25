"""Cafe table scene: espresso cup on a saucer, spoon, sugar cubes, croissant.

Built only from primitive meshes (cube, cylinder, cone, sphere, torus).
"""

import bpy
import bmesh
import math
from mathutils import Vector

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras):
        for item in list(block):
            block.remove(item)


def make_material(name, color, roughness=0.5, metallic=0.0, specular=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = specular
    return mat


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def remove_top_face(obj):
    """Delete the up-facing cap of a primitive so it becomes an open shell."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    doomed = [f for f in bm.faces
              if f.normal.z > 0.85 and f.calc_center_median().z > 0.0]
    bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bm.to_mesh(me)
    bm.free()
    me.update()


def add_cube(name, size, location, rotation=(0, 0, 0), scale=(1, 1, 1), mat=None):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location,
                                    rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        assign(obj, mat)
    return obj


def add_cylinder(name, radius, depth, location, rotation=(0, 0, 0),
                 scale=(1, 1, 1), vertices=48, mat=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth,
                                        location=location, rotation=rotation,
                                        vertices=vertices)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        assign(obj, mat)
    return obj


def add_cone(name, r1, r2, depth, location, rotation=(0, 0, 0),
             scale=(1, 1, 1), vertices=48, mat=None):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=depth,
                                    location=location, rotation=rotation,
                                    vertices=vertices)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        assign(obj, mat)
    return obj


def add_sphere(name, radius, location, rotation=(0, 0, 0), scale=(1, 1, 1),
               segments=32, rings=16, mat=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location,
                                         rotation=rotation, segments=segments,
                                         ring_count=rings)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        assign(obj, mat)
    return obj


def add_torus(name, major, minor, location, rotation=(0, 0, 0),
              scale=(1, 1, 1), mat=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     location=location, rotation=rotation,
                                     major_segments=48, minor_segments=16)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        assign(obj, mat)
    return obj


# ----------------------------------------------------------------------------
# Scene setup
# ----------------------------------------------------------------------------

clear_scene()

# Materials
MAT_TABLE = make_material("Table", (0.16, 0.075, 0.030), roughness=0.45)
MAT_PORCELAIN = make_material("Porcelain", (0.90, 0.89, 0.85), roughness=0.18,
                              specular=0.65)
MAT_COFFEE = make_material("Espresso", (0.030, 0.012, 0.005), roughness=0.06,
                           specular=0.9)
MAT_CREMA = make_material("Crema", (0.34, 0.16, 0.055), roughness=0.45)
MAT_METAL = make_material("Silver", (0.80, 0.81, 0.84), roughness=0.25,
                          metallic=0.9)
MAT_SUGAR = make_material("Sugar", (0.90, 0.89, 0.86), roughness=0.4,
                          specular=0.3)
MAT_CROISSANT = make_material("Croissant", (0.34, 0.15, 0.032), roughness=0.62)
MAT_CROISSANT2 = make_material("CroissantDark", (0.22, 0.085, 0.018),
                               roughness=0.68)
MAT_LEG = make_material("TableLeg", (0.10, 0.10, 0.11), roughness=0.4,
                        metallic=0.7)

# -- Table ------------------------------------------------------------------
add_cylinder("TableTop", 0.30, 0.030, (0.0, 0.0, -0.015), vertices=96,
             mat=MAT_TABLE)
add_torus("TableEdge", 0.30, 0.010, (0.0, 0.0, -0.015), mat=MAT_TABLE)
add_cylinder("TableLeg", 0.028, 0.42, (0.0, 0.0, -0.24), vertices=32,
             mat=MAT_LEG)
add_cylinder("TableFoot", 0.11, 0.018, (0.0, 0.0, -0.451), vertices=48,
             mat=MAT_LEG)

# -- Saucer -----------------------------------------------------------------
SAUCER_Z = 0.012
add_cylinder("SaucerBase", 0.082, 0.008, (0.0, 0.0, SAUCER_Z),
             vertices=64, mat=MAT_PORCELAIN)
add_cone("SaucerRim", 0.082, 0.058, 0.014, (0.0, 0.0, SAUCER_Z + 0.011),
         vertices=64, mat=MAT_PORCELAIN)
add_torus("SaucerLip", 0.080, 0.006, (0.0, 0.0, SAUCER_Z + 0.017),
          scale=(1.0, 1.0, 0.6), mat=MAT_PORCELAIN)
add_cylinder("SaucerWell", 0.055, 0.004, (0.0, 0.0, SAUCER_Z + 0.006),
             vertices=48, mat=MAT_PORCELAIN)

# -- Espresso cup -----------------------------------------------------------
CUP_BASE = SAUCER_Z + 0.020
CUP_R = 0.034
CUP_H = 0.062
CUP_CZ = CUP_BASE + CUP_H / 2.0
cup = add_cone("CupBody", CUP_R * 0.80, CUP_R, CUP_H, (0.0, 0.0, CUP_CZ),
               vertices=64, mat=MAT_PORCELAIN)
remove_top_face(cup)
# rim lip
add_torus("CupRim", CUP_R, 0.0035, (0.0, 0.0, CUP_BASE + CUP_H),
          mat=MAT_PORCELAIN)
# espresso surface just below the rim
add_cylinder("Espresso", CUP_R * 0.90, 0.005,
             (0.0, 0.0, CUP_BASE + CUP_H - 0.010), vertices=48, mat=MAT_COFFEE)
add_cylinder("Crema", CUP_R * 0.62, 0.004,
             (0.0, 0.0, CUP_BASE + CUP_H - 0.008), vertices=48, mat=MAT_CREMA)
# handle
add_torus("CupHandle", 0.019, 0.0048, (CUP_R + 0.005, 0.0, CUP_CZ),
          rotation=(math.pi / 2.0, 0.0, 0.0), mat=MAT_PORCELAIN)
# small foot
add_cylinder("CupFoot", CUP_R * 0.78, 0.006, (0.0, 0.0, CUP_BASE),
             vertices=48, mat=MAT_PORCELAIN)

# -- Spoon (resting on the saucer, angled) ---------------------------------
SPOON_ANG = math.radians(60.0)
handle_len = 0.075
handle_cx = -0.052
bowl_cx = handle_cx + handle_len / 2.0 + 0.016
sp_x, sp_y = -0.042, -0.026
cos_a, sin_a = math.cos(SPOON_ANG), math.sin(SPOON_ANG)


def rot_pt(lx, ly):
    return (sp_x + lx * cos_a - ly * sin_a, sp_y + lx * sin_a + ly * cos_a)


hx, hy = rot_pt(handle_cx, 0.0)
add_cylinder("SpoonHandle", 0.0045, handle_len, (hx, hy, SAUCER_Z + 0.028),
             rotation=(math.pi / 2.0, 0.0, SPOON_ANG), vertices=16,
             mat=MAT_METAL)
bx, by = rot_pt(bowl_cx, 0.0)
bowl = add_sphere("SpoonBowl", 0.020, (bx, by, SAUCER_Z + 0.026),
                  scale=(1.0, 0.62, 0.16), segments=32, rings=16,
                  mat=MAT_METAL)
bowl.rotation_euler = (0.0, 0.0, SPOON_ANG)
nx, ny = rot_pt(handle_cx - handle_len / 2.0 + 0.004, 0.0)
add_sphere("SpoonTip", 0.0055, (nx, ny, SAUCER_Z + 0.028),
           scale=(1.0, 1.0, 0.8), mat=MAT_METAL)

# -- Sugar cubes ------------------------------------------------------------
SUG = 0.017
for i, (sx, sy, layers, ang) in enumerate([
        (0.140, 0.078, 0.0, 0.12),
        (0.140, 0.078, 1.0, 0.55),
        (0.113, 0.100, 0.0, -0.35)]):
    add_cube("SugarCube_%d" % i, SUG,
             (sx, sy, SUG / 2.0 + layers * SUG), rotation=(0, 0, ang),
             scale=(1.0, 1.0, 0.86), mat=MAT_SUGAR)

# -- Croissant --------------------------------------------------------------
# A crescent built from many overlapping tapered spheres along a circular arc:
# fat in the middle, pointed at the tips, with a few narrower darker rings
# standing in for the rolled pastry folds.
CX, CY = 0.118, -0.062
R_ARC = 0.058
N = 15

def croissant_pt(i):
    t = i / (N - 1.0)
    theta = math.radians(200.0 + t * 140.0)   # 200 -> 340 deg
    taper = 0.06 + 0.94 * math.sin(math.pi * t) ** 1.05
    r = 0.0165 * taper
    px = CX + R_ARC * math.cos(theta)
    py = CY + R_ARC * math.sin(theta)
    return t, theta, r, px, py

# smooth body
for i in range(N):
    t, theta, r, px, py = croissant_pt(i)
    seg = add_sphere("Croissant_%d" % i, r, (px, py, r * 0.70),
                     scale=(1.18, 1.18, 0.82), segments=24, rings=14,
                     mat=MAT_CROISSANT)
    seg.rotation_euler = (0.0, 0.0, theta + math.pi / 2.0)

# raised segment ridges wrapped around the tube (classic croissant folds)
for i in range(2, N - 1, 2):
    t, theta, r, px, py = croissant_pt(i)
    phi = theta + math.pi / 2.0
    add_torus("CroissantRidge_%d" % i, r * 0.86, 0.0032,
              (px, py, r * 0.70), rotation=(math.pi / 2.0, 0.0, phi + math.pi / 2.0),
              mat=MAT_CROISSANT2)

# ----------------------------------------------------------------------------
# Camera
# ----------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 52.0
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = Vector((0.25, -0.56, 0.44))
target = Vector((0.030, -0.03, 0.045))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = cam

# ----------------------------------------------------------------------------
# Lighting
# ----------------------------------------------------------------------------

def add_area_light(name, location, energy, size, target_pt, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = location
    d = Vector(target_pt) - Vector(location)
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return lo


add_area_light("KeyLight", (0.45, -0.40, 0.62), 20.0, 0.5,
               (0.06, -0.02, 0.05), color=(1.0, 0.95, 0.88))
add_area_light("FillLight", (-0.55, -0.35, 0.32), 8.0, 0.7,
               (0.0, 0.0, 0.04), color=(0.90, 0.94, 1.0))
add_area_light("RimLight", (-0.10, 0.55, 0.45), 12.0, 0.45,
               (0.05, 0.0, 0.06), color=(1.0, 0.96, 0.90))

# world ambient
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.50, 0.55, 0.63, 1.0)
bg.inputs[1].default_value = 0.09

# tone mapping
bpy.context.scene.view_settings.view_transform = "Filmic"
bpy.context.scene.view_settings.look = "Medium Contrast"
bpy.context.scene.view_settings.exposure = -0.6