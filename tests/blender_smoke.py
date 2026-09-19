import sys, math
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import material_physics as addon
addon.register()
bpy.ops.mesh.primitive_cube_add(size=1)
obj=bpy.context.object
addon.apply_parameters(obj,bpy.context,'DENSITY',600,'Wood')
assert math.isclose(obj.material_physics.volume,1)
assert math.isclose(obj.material_physics.mass,600)
obj.scale=(2,1,1); bpy.context.view_layer.update()
addon.apply_parameters(obj,bpy.context,'MASS',1000,'Wood')
assert math.isclose(obj.material_physics.volume,2)
assert math.isclose(obj.material_physics.density,500)
bpy.context.scene.unit_settings.scale_length=.1
addon.refresh(obj,bpy.context)
assert math.isclose(obj.material_physics.volume,.002,rel_tol=1e-6)
bpy.context.scene.unit_settings.scale_length=1
bpy.ops.mesh.primitive_plane_add(size=2)
plane=bpy.context.object
try: addon.apply_parameters(plane,bpy.context,'DENSITY',600,'Unknown')
except ValueError: pass
else: raise AssertionError('Open solid accepted')
addon.apply_parameters(plane,bpy.context,'DENSITY',1100,'Custom liquid','LIQUID',.02,.05)
assert plane.material_physics.density==1100
assert math.isclose(plane.material_physics.viscosity,.02,rel_tol=1e-6)
addon.unregister()
print('BLENDER_SMOKE_OK')
