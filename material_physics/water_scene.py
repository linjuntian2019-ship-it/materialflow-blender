"""Build a separate one-metre wood-box / Mantaflow demonstration scene."""
import bpy, json, math
from pathlib import Path
from mathutils import Vector
from .water_motion import simulate, rotation

def material(name,color,metallic=0.,roughness=.35):
    m=bpy.data.materials.new(name); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=roughness
    p.inputs['Metallic'].default_value=metallic
    return m

def box(name,location,dimensions,mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    o=bpy.context.object; o.name=name; o.dimensions=dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if mat: o.data.materials.append(mat)
    return o

def build(source, output_dir, density=600., resolution=80, fps=24, seconds=10., height=1.8):
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    # The current milestone is deliberately restricted to the tested 1 m box.
    dimensions=tuple(source.dimensions)
    if max(abs(d-1) for d in dimensions)>.001:
        raise ValueError('此落水测试目前仅支持 1 m × 1 m × 1 m 木块')
    if any(abs(v-1)>.001 for v in source.scale):
        raise ValueError('请先应用木块缩放，再创建落水测试')
    records,metrics=simulate(density=density,height=height,seconds=seconds,fps=fps)
    if min(r['position'][2]-sum(abs(v) for v in rotation(r['quaternion'])[2])*.5 for r in records)<-1.9:
        raise ValueError('这些参数会让木块碰到池底；当前未实现池底碰撞，请减小落差或密度')
    (out/'motion.json').write_text(json.dumps({'metrics':metrics,'frames':records},ensure_ascii=False,indent=2),encoding='utf-8')
    scene=bpy.data.scenes.new('Wood Drop · Water Physics')
    bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1.
    scene.gravity=(0,0,-9.81)
    scene.render.fps=fps; scene.frame_start=1; scene.frame_end=len(records)
    scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
    try:
        pref=bpy.context.preferences.addons['cycles'].preferences
        pref.compute_device_type='OPTIX'; pref.get_devices()
        for d in pref.devices: d.use=d.type=='OPTIX'
        if any(d.use for d in pref.devices): scene.cycles.device='GPU'
    except Exception: pass
    scene.render.resolution_x=960; scene.render.resolution_y=720; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    world=bpy.data.worlds.new('Water Studio'); world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.3,.38,.5,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.45
    scene.world=world
    wood=source.copy(); wood.data=source.data.copy(); wood.animation_data_clear()
    scene.collection.objects.link(wood); wood.name=f'Wood · {density:g} kg demonstration'
    # Source cube is one metre and unscaled; duplicate only its shape and shader.
    wood.parent=None; wood.constraints.clear(); wood.rotation_mode='QUATERNION'; wood.scale=(1,1,1)
    if wood.rigid_body:
        bpy.context.view_layer.objects.active=wood; wood.select_set(True)
        bpy.ops.rigidbody.object_remove()
    for record in records:
        wood.location=record['position']; wood.rotation_quaternion=record['quaternion']
        wood.keyframe_insert(data_path='location',frame=record['frame'])
        wood.keyframe_insert(data_path='rotation_quaternion',frame=record['frame'])
    action=wood.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for key in fc.keyframe_points: key.interpolation='LINEAR'
    wood['physics_method']='Approximate hydrostatics + drag; baked motion drives liquid, no fluid feedback'
    wood['confirmed_density_kg_m3']=density
    wood['mass_kg']=density
    # Small geometric edge highlight; collision stays essentially the same box.
    bevel=wood.modifiers.new('Small edge highlights','BEVEL'); bevel.width=.008; bevel.segments=2
    eff=wood.modifiers.new('Moving liquid collider','FLUID'); eff.fluid_type='EFFECTOR'
    eff.effector_settings.surface_distance=.001
    eff.effector_settings.subframes=4
    wood['motion_baked']=True
    water=material('Water · clear fresh water',(.75,.94,.97),roughness=.08)
    p=water.node_tree.nodes.get('Principled BSDF')
    p.inputs['Transmission Weight'].default_value=1.; p.inputs['IOR'].default_value=1.333
    absorption=water.node_tree.nodes.new('ShaderNodeVolumeAbsorption')
    absorption.inputs['Color'].default_value=(.18,.65,.73,1)
    absorption.inputs['Density'].default_value=.13
    water.node_tree.links.new(absorption.outputs['Volume'],water.node_tree.nodes['Material Output'].inputs['Volume'])
    domain=box('WATER · baked Mantaflow',(0,0,1.25),(6,6,6.5),water)
    fluid=domain.modifiers.new('Liquid domain','FLUID'); fluid.fluid_type='DOMAIN'
    d=fluid.domain_settings; d.domain_type='LIQUID'; d.resolution_max=resolution
    d.cache_type='ALL'; d.cache_directory=str(out/'liquid_cache_v2')
    d.cache_frame_start=1; d.cache_frame_end=scene.frame_end
    d.use_mesh=True; d.mesh_scale=2; d.mesh_particle_radius=1.6
    d.mesh_smoothen_pos=2; d.mesh_smoothen_neg=2
    d.flip_ratio=.95; d.timesteps_min=1; d.timesteps_max=8; d.cfl_condition=2.
    d.use_collision_border_top=False
    d.use_spray_particles=True; d.use_foam_particles=True
    d.sndparticle_life_min=8; d.sndparticle_life_max=35
    bpy.context.view_layer.update()
    for face in domain.data.polygons: face.use_smooth=True
    fill=box('Initial water volume · hidden',(0,0,-.99),(5.98,5.98,1.98))
    flow=fill.modifiers.new('Initial water','FLUID'); flow.fluid_type='FLOW'
    flow.flow_settings.flow_type='LIQUID'; flow.flow_settings.flow_behavior='GEOMETRY'
    fill.hide_render=True; fill.display_type='WIRE'
    # Static box-domain borders form the water container; visible architecture
    # sits just outside, so thin mesh walls cannot leak at the preview resolution.
    stone=material('Pool · pale stone',(.18,.22,.25),roughness=.32)
    trim=material('Pool · brushed rim',(.45,.5,.52),metallic=.65,roughness=.25)
    floor=box('Pool floor',(0,0,-2.1),(6.35,6.35,.2),stone)
    for loc,dim in [((0,3.13,-.96),(6.5,.26,2.25)),((0,-3.13,-.96),(6.5,.26,2.25)),
                    ((3.13,0,-.96),(.26,6,2.25)),((-3.13,0,-.96),(.26,6,2.25))]:
        wall=box('Pool wall',loc,dim,stone)
        b=wall.modifiers.new('Edge','BEVEL'); b.width=.025; b.segments=3
        rimloc=(loc[0],loc[1],.19)
        box('Rim',rimloc,(dim[0],dim[1],.035),trim)
    # Floor grid gives transparent water a depth reference.
    grout=material('Tile joints',(.075,.11,.13),roughness=.45)
    for a in range(-5,6):
        box('Tile line X',(a*.5,0,-1.991),(.008,6,.008),grout)
        box('Tile line Y',(0,a*.5,-1.991),(6,.008,.008),grout)
    ground=material('Studio ground',(.025,.035,.05),roughness=.45)
    box('Studio plinth',(0,0,-2.28),(200,200,.15),ground)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(0,0,-100))
    droplet=bpy.context.object; droplet.name='Spray droplet instance'; droplet.data.materials.append(water)
    for poly in droplet.data.polygons: poly.use_smooth=True
    bpy.context.view_layer.update()
    for system in domain.particle_systems:
        # FLIP carrier particles must not be rendered on top of the water mesh.
        if system.settings.type=='SPRAY':
            system.settings.render_type='OBJECT'; system.settings.instance_object=droplet
            system.settings.particle_size=.025; system.settings.size_random=.65
        else: system.settings.render_type='NONE'
    for name,loc,power,size in [('Key',(0,-3,8),2300,5),('Rim',(-4,3,5),2800,4),('Fill',(5,1,5),1800,3)]:
        ld=bpy.data.lights.new(name,'AREA'); lo=bpy.data.objects.new(name,ld); scene.collection.objects.link(lo)
        lo.location=loc; ld.energy=power; ld.shape='DISK'; ld.size=size; ld.specular_factor=.18
        lo.visible_glossy=False
        lo.rotation_euler=(Vector((0,0,0))-lo.location).to_track_quat('-Z','Y').to_euler()
    cd=bpy.data.cameras.new('Camera'); camera=bpy.data.objects.new('Camera',cd); scene.collection.objects.link(camera)
    camera.location=(8,-10,7.5); camera.rotation_euler=(Vector((0,0,.25))-camera.location).to_track_quat('-Z','Y').to_euler()
    cd.type='PERSP'; cd.lens=48; scene.camera=camera
    for frame,name in [(1,'Release'),(16,'Entry'),(28,'Submerged'),(60,'Resurface'),(180,'Settling')]:
        scene.timeline_markers.new(name,frame=frame)
    scene['material_physics_notes']='Uniform gravity 9.81 m/s2; water 1000 kg/m3; motion approximation -> Mantaflow one-way coupling.'
    scene['density_kg_m3']=density
    scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT'); wood.select_set(True); bpy.context.view_layer.objects.active=wood
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.overlay.show_overlays=False
    return scene,wood,domain,metrics

def bake(scene,domain,path):
    bpy.context.window.scene=scene
    bpy.ops.object.select_all(action='DESELECT'); domain.select_set(True); bpy.context.view_layer.objects.active=domain
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    result=bpy.ops.fluid.bake_all()
    if 'FINISHED' not in result: raise RuntimeError('液体烘焙未完成')
    bpy.ops.wm.save_as_mainfile(filepath=str(path))

