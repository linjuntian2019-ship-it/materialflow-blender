bl_info = {'name':'MaterialFlow · 材料物理助手','author':'MaterialFlow contributors','version':(0,3,1),'blender':(5,2,0),'location':'3D View > N > 材料物理','description':'本地 DMS 材料建议、自动体积、手动质量与密度','category':'Physics'}

import bpy, json, subprocess, time, uuid, importlib
from pathlib import Path
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty, PointerProperty
from bpy.app.handlers import persistent
from . import geometry, material_types
importlib.reload(geometry)
importlib.reload(material_types)
from .geometry import measure, recognition_signature
from .material_types import TYPE_ITEMS, TYPE_LABELS, suggest_type

ROOT=Path(__file__).resolve().parent
try: CONFIG=json.loads((ROOT/'local_config.json').read_text(encoding='utf-8'))
except Exception: CONFIG={}
JOB=None
LAST_OBJ=None
PRESETS=[('CUSTOM','手动输入',''),('WOOD','通用木材：600 kg/m³（示例）','仿真初始值，不代表具体木种'),('METAL','普通金属：7800 kg/m³（示例）','不代表所有金属'),('PLASTIC','塑料：950 kg/m³（示例）','不同聚合物差异很大'),('STONE','石材：2600 kg/m³（示例）',''),('GLASS','玻璃：2500 kg/m³（示例）','')]
PRESET_VALUES={'WOOD':600.0,'METAL':7800.0,'PLASTIC':950.0,'STONE':2600.0,'GLASS':2500.0}
TRANSLATE={'Wood':'木材','Wood, tree':'树木木质','Metal':'金属','Fabric/cloth':'布料','Wicker':'藤编','Paint/plaster/enamel':'涂层／石膏／瓷釉','Plastic, clear':'透明塑料','Plastic, non-clear':'不透明塑料','Stone, natural':'天然石材','Stone, polished':'抛光石材','Glass':'玻璃','Cardboard':'纸板','Paper':'纸','Cork/corkboard':'软木'}
def label(name): return TRANSLATE.get(name,name)
TRANSLATE.update({'Water':'水','Liquid, non-water':'其他液体','Ice':'冰'})
def read_result(obj):
    try: return json.loads(obj.material_physics.result_json)
    except Exception: return {}
def redraw():
    for wm in bpy.data.window_managers:
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type=='VIEW_3D': area.tag_redraw()
def prefs(context): return context.preferences.addons[__package__].preferences
def refresh(obj,context):
    p=obj.material_physics
    try:
        volume,signature=measure(obj,context.evaluated_depsgraph_get(),context.scene.unit_settings.scale_length)
        if p.volume != volume: p.volume=volume
        if p.geometry_error: p.geometry_error=''
        if p.geometry_signature != signature:
            if p.result_json and p.geometry_signature:
                p.result_stale=True
            p.geometry_signature=signature
        if p.applied and p.physical_type=='LIQUID':
            p.density=p.active_value
            p.mass=0  # A liquid surface/domain is not necessarily its fill volume.
        elif p.applied:
            if p.active_mode=='DENSITY':
                density,mass=p.active_value,p.active_value*volume
            else:
                mass,density=p.active_value,p.active_value/volume
            if p.density != density: p.density=density
            if p.mass != mass: p.mass=mass
            if obj.rigid_body and obj.rigid_body.mass != mass: obj.rigid_body.mass=mass
        return volume,signature
    except Exception as exc:
        p.geometry_error=str(exc)
        p.volume=0
        if p.applied and p.physical_type=='LIQUID':
            p.density=p.active_value
            p.mass=0
        if p.result_json: p.result_stale=True
        raise
def apply_parameters(obj,context,mode,value,material,physical_type='SOLID',viscosity=.001,surface_tension=.072):
    if value<=0: raise ValueError('质量或密度必须大于零')
    if physical_type not in TYPE_LABELS: raise ValueError('请选择固体或液体')
    if physical_type=='LIQUID':
        if mode!='DENSITY': raise ValueError('液体请直接输入密度')
        if viscosity<0 or surface_tension<0: raise ValueError('黏度和表面张力不能为负数')
        p=obj.material_physics
        p.physical_type='LIQUID'; p.active_mode='DENSITY'; p.mode='DENSITY'
        p.active_value=value; p.density=value; p.input_density=value; p.mass=0
        p.viscosity=viscosity; p.surface_tension=surface_tension
        p.material_name=material or '用户指定的液体'; p.applied=True
        try: refresh(obj,context)
        except ValueError: pass
        p.status='液体参数已保存；已有动画不会自动重算'
        redraw()
        return
    volume,_=refresh(obj,context)
    p=obj.material_physics
    p.physical_type='SOLID'
    p.active_mode=mode
    p.active_value=value
    p.material_name=material or '用户指定，材料未知'
    p.applied=True
    p.mode=mode
    p.input_density=value if mode=='DENSITY' else value/volume
    p.input_mass=value if mode=='MASS' else value*volume
    refresh(obj,context)
    p.status='参数已确认并保存到物体'

class MPPreferences(bpy.types.AddonPreferences):
    bl_idname=__package__
    python_path:StringProperty(name='独立 Python',subtype='FILE_PATH',default=CONFIG.get('python',''))
    model_path:StringProperty(name='Apple DMS 模型',subtype='FILE_PATH',default=CONFIG.get('model',''))
    taxonomy_path:StringProperty(name='类别文件',subtype='FILE_PATH',default=CONFIG.get('taxonomy',''))
    cache_dir:StringProperty(name='本地结果目录',subtype='DIR_PATH',default=CONFIG.get('cache',str(Path(bpy.utils.user_resource('CONFIG'))/'materialflow'/'cache')))
    def draw(self,context):
        for field in ['python_path','model_path','taxonomy_path','cache_dir']: self.layout.prop(self,field)
        self.layout.label(text='全部在本地运行，不需要 API 账号。')

class MPProperties(bpy.types.PropertyGroup):
    physical_type:EnumProperty(name='物理类型',items=TYPE_ITEMS,default='SOLID')
    viscosity:FloatProperty(name='动力黏度 (Pa·s)',default=.001,min=0,max=1e8,precision=6)
    surface_tension:FloatProperty(name='表面张力 (N/m)',default=.072,min=0,max=1e6,precision=6)
    mode:EnumProperty(name='输入方式',items=[('DENSITY','输入密度',''),('MASS','输入质量','')],default='DENSITY')
    input_density:FloatProperty(name='密度 (kg/m³)',default=1000,min=0.000001,max=1e15,precision=4)
    input_mass:FloatProperty(name='质量 (kg)',default=1,min=0.000001,max=1e20,precision=4)
    material_name:StringProperty(name='物理材料',default='')
    volume:FloatProperty(name='自动体积 (m³)',precision=6)
    mass:FloatProperty(name='已确认质量 (kg)',precision=6)
    density:FloatProperty(name='已确认平均密度 (kg/m³)',precision=6)
    applied:BoolProperty(default=False)
    active_mode:StringProperty(default='DENSITY')
    active_value:FloatProperty(default=1000,max=1e20)
    geometry_signature:StringProperty()
    geometry_error:StringProperty()
    result_json:StringProperty()
    result_dir:StringProperty(subtype='DIR_PATH')
    result_stale:BoolProperty(default=False)
    status:StringProperty(default='请选择识别或手动设置')

def prepare_job(context,obj):
    try: volume,_=refresh(obj,context)
    except ValueError: volume=0.
    signature=recognition_signature(obj,context.evaluated_depsgraph_get(),context.scene.unit_settings.scale_length)
    pr=prefs(context)
    for value,title in [(pr.python_path,'独立 Python'),(pr.model_path,'DMS 模型'),(pr.taxonomy_path,'类别文件')]:
        if not Path(bpy.path.abspath(value)).is_file(): raise ValueError(title+' 路径不存在，请在插件设置中配置')
    if not pr.cache_dir: raise ValueError('请先设置本地结果目录')
    directory=Path(bpy.path.abspath(pr.cache_dir))/('job_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    directory.mkdir(parents=True,exist_ok=False)
    evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
    mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=context.evaluated_depsgraph_get())
    snapshot=bpy.data.objects.new('MP_Snapshot',mesh)
    snapshot.matrix_world=evaluated.matrix_world.copy()
    snapshot_name=snapshot.name
    try:
        bpy.data.libraries.write(str(directory/'snapshot.blend'),{snapshot},path_remap='ABSOLUTE',fake_user=True,compress=True)
    finally:
        bpy.data.objects.remove(snapshot)
        bpy.data.meshes.remove(mesh)
    config={'snapshot_object':snapshot_name,'geometry_signature':signature,'volume_m3':volume,'model':bpy.path.abspath(pr.model_path),'taxonomy':bpy.path.abspath(pr.taxonomy_path)}
    (directory/'job.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'target':obj,'directory':directory,'python':bpy.path.abspath(pr.python_path),'stage':'render','fraction':0,'message':'准备渲染','signature':signature,'process':None,'log':None}

def launch(job,stage):
    job['stage']=stage
    command=[bpy.app.binary_path,'--background','--factory-startup','--python',str(ROOT/'render_worker.py'),'--',str(job['directory'])] if stage=='render' else [job['python'],str(ROOT/'infer_worker.py'),str(job['directory'])]
    job['log']=open(job['directory']/(stage+'.log'),'w',encoding='utf-8')
    try:
        job['process']=subprocess.Popen(command,stdout=job['log'],stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except Exception:
        job['log'].close()
        raise

def cancel_job(message='已取消识别，物理参数未改变'):
    global JOB
    if JOB:
        process=JOB.get('process')
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=0.3)
            except subprocess.TimeoutExpired: process.kill()
        log=JOB.get('log')
        if log: log.close()
        try: JOB['target'].material_physics.status=message
        except ReferenceError: pass
    JOB=None
    redraw()

class MP_OT_identify(bpy.types.Operator):
    bl_idname='material_physics.identify'
    bl_label='识别材料 · 12 视角'
    bl_description='后台渲染并运行本地 Apple DMS；不自动修改物理参数'
    _timer=None
    @classmethod
    def poll(cls,context): return JOB is None and context.object is not None and context.object.type=='MESH' and context.mode=='OBJECT'
    def execute(self,context):
        global JOB
        try:
            JOB=prepare_job(context,context.object)
            launch(JOB,'render')
            context.object.material_physics.status='后台渲染中'
            self._timer=context.window_manager.event_timer_add(0.25,window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        except Exception as exc:
            cancel_job(str(exc))
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}
    def cleanup(self,context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer=None
    def modal(self,context,event):
        global JOB
        if JOB is None:
            self.cleanup(context)
            return {'CANCELLED'}
        if event.type!='TIMER': return {'PASS_THROUGH'}
        try:
            directory=JOB['directory']
            target=JOB['target']
            if target.name not in context.scene.objects:
                raise ValueError('目标物体已删除或离开当前场景')
            progress=directory/'progress.json'
            if progress.exists():
                try:
                    info=json.loads(progress.read_text(encoding='utf-8'))
                    JOB['fraction']=info.get('fraction',0)
                    JOB['message']=info.get('message','运行中')
                except (OSError,ValueError): pass
            redraw()
            code=JOB['process'].poll()
            if code is None: return {'PASS_THROUGH'}
            JOB['log'].close()
            JOB['log']=None
            error_file=directory/'error.json'
            if error_file.exists(): raise RuntimeError(json.loads(error_file.read_text(encoding='utf-8'))['error'])
            if code!=0: raise RuntimeError('后台任务失败，请查看本地日志：'+str(directory))
            if JOB['stage']=='render':
                if not (directory/'views.json').exists(): raise RuntimeError('后台未生成视角清单')
                launch(JOB,'infer')
                return {'PASS_THROUGH'}
            result=json.loads((directory/'result.json').read_text(encoding='utf-8'))
            try: refresh(target,context)
            except ValueError: pass
            current_signature=recognition_signature(target,context.evaluated_depsgraph_get(),context.scene.unit_settings.scale_length)
            if current_signature!=JOB['signature']:
                raise ValueError('识别期间模型几何发生变化，请重新识别')
            p=target.material_physics
            p.result_json=json.dumps(result,ensure_ascii=False)
            p.result_dir=str(directory)
            p.result_stale=False
            p.status='识别完成，等待确认物理参数'
            target_name=target.name
            JOB=None
            self.cleanup(context)
            redraw()
            bpy.ops.material_physics.parameters('INVOKE_DEFAULT',target_name=target_name,reason=result['reason'],type_hint=suggest_type(result) or '')
            return {'FINISHED'}
        except Exception as exc:
            cancel_job(str(exc))
            self.cleanup(context)
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}
    def cancel(self,context):
        cancel_job()
        self.cleanup(context)

class MP_OT_cancel(bpy.types.Operator):
    bl_idname='material_physics.cancel'
    bl_label='取消后台任务'
    def execute(self,context):
        cancel_job()
        return {'FINISHED'}

def preset_changed(self,context):
    if self.preset in PRESET_VALUES:
        self.density=PRESET_VALUES[self.preset]
        self.mode='DENSITY'
        self.material=dict((i[0],i[1].split('：')[0]) for i in PRESETS)[self.preset]

class MP_OT_parameters(bpy.types.Operator):
    bl_idname='material_physics.parameters'
    bl_label='确认物理参数'
    bl_options={'REGISTER','UNDO'}
    target_name:StringProperty(options={'HIDDEN'})
    type_hint:StringProperty(options={'HIDDEN'})
    physical_type:EnumProperty(name='物理类型',items=TYPE_ITEMS,default='SOLID')
    viscosity:FloatProperty(name='动力黏度 (Pa·s)',default=.001,min=0,max=1e8,precision=6)
    surface_tension:FloatProperty(name='表面张力 (N/m)',default=.072,min=0,max=1e6,precision=6)
    reason:StringProperty(options={'HIDDEN'},default='体积自动计算；材料和物理参数由你确认。')
    mode:EnumProperty(name='输入方式',items=[('DENSITY','输入密度',''),('MASS','输入质量','')],default='DENSITY')
    density:FloatProperty(name='密度 (kg/m³)',default=1000,min=0.000001,max=1e15,precision=4)
    mass:FloatProperty(name='质量 (kg)',default=1,min=0.000001,max=1e20,precision=4)
    material:StringProperty(name='物理材料',default='用户指定，材料未知')
    preset:EnumProperty(name='可选示例预设',items=PRESETS,default='CUSTOM',update=preset_changed)
    def invoke(self,context,event):
        obj=bpy.data.objects.get(self.target_name) if self.target_name else context.object
        if not obj or obj.type!='MESH': return {'CANCELLED'}
        self.target_name=obj.name
        try: refresh(obj,context)
        except ValueError: pass
        p=obj.material_physics
        self.physical_type=self.type_hint if self.type_hint in TYPE_LABELS else (p.physical_type if p.applied else suggest_type(read_result(obj)) or 'SOLID')
        self.viscosity=p.viscosity
        self.surface_tension=p.surface_tension
        self.mode=p.mode
        self.density=p.input_density
        self.mass=p.input_mass
        self.material=p.material_name or '用户指定，材料未知'
        return context.window_manager.invoke_props_dialog(self,width=500,confirm_text='应用物理参数')
    def draw(self,context):
        obj=bpy.data.objects.get(self.target_name)
        if not obj:
            self.layout.label(text='目标物体已不存在')
            return
        l=self.layout
        p=obj.material_physics
        l.label(text=obj.name,icon='MESH_CUBE')
        l.label(text=self.reason,icon='INFO')
        result=read_result(obj)
        suggestion=suggest_type(result) if not p.result_stale else None
        l.label(text='类型建议：'+TYPE_LABELS[suggestion]+'（待确认）' if suggestion else '无法确定类型，请手动选择固体或液体。')
        l.prop(self,'physical_type',expand=True)
        if result and not p.result_stale:
            box=l.box()
            box.label(text='AI 材料建议（不会自动应用密度）')
            for c in result.get('candidates',[])[:3]:
                box.label(text=f'{label(c["name"])}  ·  {c["share"]:.1f}% 可见像素  ·  {c["votes"]}/12 视角首位')
        l.prop(self,'material')
        if self.physical_type=='LIQUID':
            l.prop(self,'density')
            l.prop(self,'viscosity')
            l.prop(self,'surface_tension')
            l.label(text='黏度和表面张力默认值为水的示例值，请确认。')
            l.label(text='保存环境参数；已有落水动画不会自动重算。')
        else:
            if p.geometry_error: l.label(text='固体体积无效，请先修复封闭网格。',icon='ERROR')
            else: l.label(text=f'自动体积：{p.volume:.8g} m³')
            l.prop(self,'preset')
            l.prop(self,'mode',expand=True)
            if self.mode=='DENSITY':
                l.prop(self,'density')
                l.label(text=f'计算质量：{self.density*p.volume:.8g} kg')
            else:
                l.prop(self,'mass')
                l.label(text=f'计算平均密度：{self.mass/p.volume:.8g} kg/m³' if p.volume>0 else '体积无效')
        l.label(text='材料名称仅为标签；密度以你确认的数值为准。')
    def execute(self,context):
        obj=bpy.data.objects.get(self.target_name) if self.target_name else context.object
        try:
            mode='DENSITY' if self.physical_type=='LIQUID' else self.mode
            apply_parameters(obj,context,mode,self.density if mode=='DENSITY' else self.mass,self.material,self.physical_type,self.viscosity,self.surface_tension)
            self.report({'INFO'},'物理参数已应用')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}

class MP_OT_refresh(bpy.types.Operator):
    bl_idname='material_physics.refresh'
    bl_label='刷新体积'
    def execute(self,context):
        try: refresh(context.object,context)
        except Exception as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}

class MP_OT_view_result(bpy.types.Operator):
    bl_idname='material_physics.view_result'
    bl_label='查看12视角对比图'
    def execute(self,context):
        directory=Path(context.object.material_physics.result_dir)
        picture=directory/'contact_sheet.png'
        if picture.is_file():
            bpy.ops.wm.path_open(filepath=str(picture))
            return {'FINISHED'}
        self.report({'WARNING'},'本地图片已移动或删除，文字结果仍保存在物体上')
        return {'CANCELLED'}

class MP_PT_main(bpy.types.Panel):
    bl_label='材料物理 · 本地原型'
    bl_idname='MP_PT_main'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='材料物理'
    def draw(self,context):
        l=self.layout
        obj=context.object
        if not obj or obj.type!='MESH':
            l.label(text='请选择一个网格物体',icon='INFO')
            return
        p=obj.material_physics
        l.label(text=obj.name,icon='MESH_CUBE')
        suggestion=suggest_type(read_result(obj)) if not p.result_stale else None
        if p.applied: l.label(text='物理类型：'+TYPE_LABELS[p.physical_type],icon='CHECKMARK')
        elif suggestion: l.label(text='类型建议：'+TYPE_LABELS[suggestion]+'（待确认）')
        else: l.label(text='物理类型：待确认')
        l.label(text='Apple DMS · 本地运行 · 12 视角')
        if JOB:
            l.progress(factor=JOB['fraction'],type='BAR',text=JOB['message'])
            l.operator('material_physics.cancel',icon='CANCEL')
        else:
            l.operator('material_physics.identify',icon='VIEW_CAMERA')
        if context.mode!='OBJECT': l.label(text='请切换到物体模式进行识别')
        if not (p.applied and p.physical_type=='LIQUID'):
            box=l.box()
            box.label(text='自动体积')
            if p.geometry_error:
                box.label(text=p.geometry_error,icon='ERROR')
            else: box.label(text=f'{p.volume:.8g} m³')
            box.operator('material_physics.refresh',icon='FILE_REFRESH')
        if p.result_stale: l.label(text='几何已变化，请重新识别',icon='ERROR')
        result=read_result(obj)
        if result:
            box=l.box()
            box.label(text='材料建议 · 待人工确认')
            for c in result.get('candidates',[])[:3]:
                box.label(text=f'{label(c["name"])}：{c["share"]:.1f}%  ·  首位 {c["votes"]}/12')
            box.label(text='占比不是置信度或准确率',icon='INFO')
            box.operator('material_physics.view_result',icon='IMAGE_DATA')
        row=l.row()
        op=row.operator('material_physics.parameters',text='手动设置／确认参数',icon='PREFERENCES')
        op.target_name=obj.name
        if p.applied:
            box=l.box()
            box.label(text='已确认的物理参数',icon='CHECKMARK')
            box.label(text=p.material_name)
            box.label(text=f'密度：{p.density:.8g} kg/m³')
            if p.physical_type=='LIQUID':
                box.label(text=f'动力黏度：{p.viscosity:.6g} Pa·s')
                box.label(text=f'表面张力：{p.surface_tension:.6g} N/m')
                box.label(text='环境参数已保存；尚未接入通用求解器。')
            else:
                box.label(text=f'质量：{p.mass:.8g} kg')
                box.label(text='形状变化时保持'+('密度' if p.active_mode=='DENSITY' else '质量'))
        else: l.label(text='尚未应用物理参数')
        l.label(text=p.status)

class MP_PT_views(bpy.types.Panel):
    bl_label='各视角识别结果'
    bl_idname='MP_PT_views'
    bl_parent_id='MP_PT_main'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='材料物理'
    bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        result=read_result(context.object) if context.object else {}
        for v in result.get('views',[]):
            self.layout.label(text=f'{v["label"]}：{label(v["top"])} {v["share"]:.1f}%')

def auto_refresh():
    try:
        context=bpy.context
        if context.object and context.object.type=='MESH' and context.mode=='OBJECT':
            refresh(context.object,context)
    except Exception: pass
    return 1.0

@persistent
def before_load(_): cancel_job('文件切换，后台识别已取消')
@persistent
def before_save(_):
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH' and obj.material_physics.applied:
            try: refresh(obj,bpy.context)
            except Exception: pass

from . import water_ui
importlib.reload(water_ui)
from .water_ui import CLASSES as WATER_CLASSES
CLASSES=[MPPreferences,MPProperties,MP_OT_identify,MP_OT_cancel,MP_OT_parameters,MP_OT_refresh,MP_OT_view_result,MP_PT_main,MP_PT_views]+WATER_CLASSES
def register():
    for cls in CLASSES: bpy.utils.register_class(cls)
    bpy.types.Object.material_physics=PointerProperty(type=MPProperties)
    bpy.app.handlers.load_pre.append(before_load)
    bpy.app.handlers.save_pre.append(before_save)
    if not bpy.app.background: bpy.app.timers.register(auto_refresh,first_interval=1,persistent=True)
def unregister():
    cancel_job()
    if bpy.app.timers.is_registered(auto_refresh): bpy.app.timers.unregister(auto_refresh)
    for handler,fn in [(bpy.app.handlers.load_pre,before_load),(bpy.app.handlers.save_pre,before_save)]:
        if fn in handler: handler.remove(fn)
    del bpy.types.Object.material_physics
    for cls in reversed(CLASSES): bpy.utils.unregister_class(cls)


