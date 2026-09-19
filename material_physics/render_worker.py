"""Background Blender render: isolated snapshot, no changes to user's scene."""
import bpy, json, sys, traceback, time
from pathlib import Path
from mathutils import Vector, Matrix

job = Path(sys.argv[sys.argv.index('--')+1])
def write(name, data):
    path = job/name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    # Windows readers can temporarily prevent replacing the destination.
    for attempt in range(40):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 39: raise
            time.sleep(0.025)

def run():
    config = json.loads((job/'job.json').read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(job/'snapshot.blend'),link=False) as (src,dst):
        dst.objects = [config['snapshot_object']]
    obj = dst.objects[0]
    if obj is None:
        raise RuntimeError('快照物体加载失败')
    s = bpy.context.scene
    s.collection.objects.link(obj)
    bpy.context.view_layer.update()
    points = [obj.matrix_world@Vector(c) for c in obj.bound_box]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    extent = max(hi-lo)
    obj.matrix_world = Matrix.Scale(1/extent,4)@Matrix.Translation(-(lo+hi)/2)@obj.matrix_world
    s.render.engine = 'CYCLES'
    s.cycles.samples = 48
    s.cycles.use_denoising = True
    try:
        p = bpy.context.preferences.addons['cycles'].preferences
        p.compute_device_type = 'OPTIX'
        p.get_devices()
        for d in p.devices: d.use = d.type == 'OPTIX'
        if any(d.use for d in p.devices): s.cycles.device = 'GPU'
    except Exception: pass
    s.render.resolution_x = s.render.resolution_y = 512
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'
    s.render.image_settings.color_mode = 'RGBA'
    s.render.film_transparent = True
    s.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('Studio')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5,0.5,0.5,1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.65
    s.world = w
    def aim(ob): ob.rotation_euler = (-ob.location).to_track_quat('-Z','Y').to_euler()
    for name,loc,power,size in [('Key',(3,-4,4.5),450,4),('Fill',(-3,-1,2.5),220,3),('Rim',(1,3,3.5),300,3),('Lower',(-2,1,-3.5),250,4)]:
        data = bpy.data.lights.new(name,'AREA')
        data.energy,data.shape,data.size = power,'DISK',size
        ob = bpy.data.objects.new(name,data)
        s.collection.objects.link(ob)
        ob.location = loc
        aim(ob)
    data = bpy.data.cameras.new('Camera')
    data.type,data.ortho_scale = 'ORTHO',1.95
    cam = bpy.data.objects.new('Camera',data)
    s.collection.objects.link(cam)
    s.camera = cam
    maskmat = bpy.data.materials.new('Silhouette')
    maskmat.use_nodes = True
    nodes = maskmat.node_tree.nodes
    nodes.clear()
    emission = nodes.new('ShaderNodeEmission')
    output = nodes.new('ShaderNodeOutputMaterial')
    maskmat.node_tree.links.new(emission.outputs[0],output.inputs[0])
    dirs = [('正前',(0,-1,0)),('正后',(0,1,0)),('正左',(-1,0,0)),('正右',(1,0,0)),('正上',(0,0,1)),('正下',(0,0,-1)),('前左上',(-1,-1,1)),('前左下',(-1,-1,-1)),('前右上',(1,-1,1)),('前右下',(1,-1,-1)),('后左上',(-1,1,1)),('后右下',(1,1,-1))]
    views = []
    for i,(label,direction) in enumerate(dirs):
        write('progress.json',{'stage':'render','fraction':i/12*0.8,'message':f'渲染 {i+1}/12：{label}'})
        cam.location = Vector(direction).normalized()*4
        aim(cam)
        stem = f'view_{i+1:02}'
        s.view_layers[0].material_override = None
        s.cycles.samples = 48
        s.render.filepath = str(job/(stem+'.png'))
        bpy.ops.render.render(write_still=True)
        s.view_layers[0].material_override = maskmat
        s.cycles.samples = 1
        s.render.filepath = str(job/(stem+'_mask.png'))
        bpy.ops.render.render(write_still=True)
        views.append({'name':stem,'label':label,'image':stem+'.png','mask':stem+'_mask.png'})
    write('views.json',views)
    write('progress.json',{'stage':'render_done','fraction':0.8,'message':'12 个视角完成，准备本地识别'})

try:
    run()
except Exception as exc:
    write('error.json',{'error':str(exc),'traceback':traceback.format_exc()})
    raise
