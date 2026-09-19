import bpy, time
from pathlib import Path
from bpy.props import StringProperty, FloatProperty, IntProperty

class MP_OT_water_demo(bpy.types.Operator):
    bl_idname='material_physics.water_demo'
    bl_label='创建木块落水场景'
    bl_description='从已确认密度创建独立演示场景；运动已生成，液体需烘焙'
    output_dir:StringProperty(name='缓存与运动数据目录',subtype='DIR_PATH')
    height:FloatProperty(name='木块底部离水高度 (m)',default=1.8,min=.1,max=2.5)
    resolution:IntProperty(name='液体分辨率',default=80,min=48,max=192)
    @classmethod
    def poll(cls,context):
        o=context.object
        return o is not None and o.type=='MESH' and o.material_physics.applied and o.material_physics.physical_type=='SOLID' and context.mode=='OBJECT'
    def invoke(self,context,event):
        base=Path(bpy.data.filepath).parent if bpy.data.filepath else Path(bpy.app.tempdir)
        self.output_dir=str(base/('water_demo_'+time.strftime('%Y%m%d_%H%M%S')))
        return context.window_manager.invoke_props_dialog(self,width=540,confirm_text='创建场景')
    def draw(self,context):
        l=self.layout
        l.label(text='当前阶段：1 m 实心木块、静水、均匀重力')
        l.label(text=f'使用已确认密度：{context.object.material_physics.density:.5g} kg/m³')
        l.prop(self,'height'); l.prop(self,'resolution'); l.prop(self,'output_dir')
        l.label(text='生成10秒运动；水花需点击「烘焙液体与水花」。')
        l.label(text='近似水动力驱动物体，水体不会反向修正物体运动。')
    def execute(self,context):
        try:
            from . import refresh
            from .water_scene import build
            source=context.object
            if source.material_physics.physical_type!='SOLID':
                raise ValueError('落水木块必须设置为固体')
            volume,_=refresh(source,context)
            if abs(volume-1)>.002 or len(source.data.vertices)!=8:
                raise ValueError('此测试仅支持单个封闭的 1 m 实心方块')
            scene,wood,domain,metrics=build(source,bpy.path.abspath(self.output_dir),density=source.material_physics.density,height=self.height,resolution=self.resolution)
            self.report({'INFO'},'木块运动已生成；保存文件后可烘焙液体与水花')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}

class MP_OT_bake_water(bpy.types.Operator):
    bl_idname='material_physics.bake_water'
    bl_label='烘焙液体与水花'
    bl_description='烘焙当前落水场景；计算可能需要数分钟，可用 Esc 取消'
    def execute(self,context):
        domains=[o for o in context.scene.objects if any(m.type=='FLUID' and m.fluid_type=='DOMAIN' for m in o.modifiers)]
        if len(domains)!=1:
            self.report({'ERROR'},'当前场景必须包含一个液体域'); return {'CANCELLED'}
        if not bpy.data.filepath:
            self.report({'ERROR'},'请先保存 .blend 文件，再进行液体烘焙'); return {'CANCELLED'}
        bpy.ops.object.select_all(action='DESELECT')
        domains[0].select_set(True); context.view_layer.objects.active=domains[0]
        result=bpy.ops.fluid.bake_all('INVOKE_DEFAULT')
        return {'CANCELLED'} if 'CANCELLED' in result else {'FINISHED'}

class MP_PT_water(bpy.types.Panel):
    bl_label='落水演示 · 近似水动力'
    bl_idname='MP_PT_water'
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='材料物理'
    def draw(self,context):
        l=self.layout
        l.operator('material_physics.water_demo',icon='MOD_FLUIDSIM')
        if 'material_physics_notes' in context.scene:
            l.label(text='10秒：自由落体 → 入水 → 浮起')
            l.label(text='重力 9.81 m/s² · 水 1000 kg/m³')
            l.label(text='木块运动已生成，可直接播放。')
            domains=[m.domain_settings for o in context.scene.objects for m in o.modifiers
                     if m.type=='FLUID' and m.fluid_type=='DOMAIN']
            ready=bool(domains) and all(d.has_cache_baked_data and d.has_cache_baked_mesh and d.has_cache_baked_particles for d in domains)
            if ready:
                l.label(text='液体与水花已烘焙，可直接播放。',icon='CHECKMARK')
            elif any(d.is_cache_baking_any for d in domains):
                l.label(text='液体正在烘焙中……',icon='TIME')
            else:
                l.operator('material_physics.bake_water',icon='MOD_FLUIDSIM')
                l.label(text='完整水面与水花需要烘焙缓存。')
            l.label(text='结果采用单向耦合近似。')

CLASSES=[MP_OT_water_demo,MP_OT_bake_water,MP_PT_water]
