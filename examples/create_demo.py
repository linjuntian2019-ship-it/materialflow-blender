"""Build the demonstration; intentionally does not bake or render."""
import sys, argparse
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import material_physics as addon

def create_wood():
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0.5))
    cube = bpy.context.object
    cube.name = 'TestCube_1m_Detailed'
    mat = bpy.data.materials.new('Continuous growth rings and fine wood pores')
    mat.use_nodes = True
    ns, ls = mat.node_tree.nodes, mat.node_tree.links
    ns.clear()
    def node(typ, name):
        n = ns.new(typ)
        n.label = n.name = name
        return n
    def link(a, out, b, inp):
        ls.new(a.outputs[out], b.inputs[inp])
    def mathnode(op, name, source=None, value=None):
        n = node('ShaderNodeMath', name)
        n.operation = op
        if source is not None: ls.new(source, n.inputs[0])
        if value is not None: n.inputs[1].default_value = value
        return n
    def ramp(name, source, stops):
        n = node('ShaderNodeValToRGB', name)
        nsr = n.color_ramp
        nsr.elements.remove(nsr.elements[1])
        for i,(p,c) in enumerate(stops):
            el = nsr.elements[0] if i == 0 else nsr.elements.new(p)
            el.position, el.color = p,c
        ls.new(source,n.inputs[0])
        return n

    coord = node('ShaderNodeTexCoord','Object coordinates')
    center = node('ShaderNodeVectorMath','Growth center offset')
    center.operation = 'SUBTRACT'
    center.inputs[1].default_value = (0.24,0.63,0)
    link(coord,'Generated',center,0)
    warp = node('ShaderNodeTexNoise','Slow irregular growth')
    warp.inputs['Scale'].default_value = 2.4
    warp.inputs['Detail'].default_value = 3
    warp.inputs['Roughness'].default_value = 0.6
    link(coord,'Generated',warp,'Vector')
    warpcenter = node('ShaderNodeVectorMath','Centered distortion')
    warpcenter.operation = 'SUBTRACT'
    warpcenter.inputs[1].default_value = (0.5,0.5,0.5)
    link(warp,'Color',warpcenter,0)
    warpscale = node('ShaderNodeVectorMath','Small radial warp')
    warpscale.operation = 'MULTIPLY'
    warpscale.inputs[1].default_value = (0.09,0.09,0)
    link(warpcenter,'Vector',warpscale,0)
    warped = node('ShaderNodeVectorMath','Warped growth coordinates')
    warped.operation = 'ADD'
    link(center,'Vector',warped,0)
    link(warpscale,'Vector',warped,1)
    radial = node('ShaderNodeVectorMath','Radial cross section')
    radial.operation = 'MULTIPLY'
    radial.inputs[1].default_value = (1,1,0)
    link(warped,'Vector',radial,0)
    radius = node('ShaderNodeVectorMath','Distance from growth center')
    radius.operation = 'LENGTH'
    link(radial,'Vector',radius,0)
    frequency = mathnode('MULTIPLY','Annual ring frequency',radius.outputs['Value'],30)
    phase = mathnode('FRACT','Annual growth phase',frequency.outputs[0])
    growth = ramp('Earlywood and latewood',phase.outputs[0],[
        (0,(0.20,0.071,0.018,1)), (0.09,(0.43,0.21,0.071,1)),
        (0.43,(0.55,0.31,0.13,1)), (0.75,(0.43,0.205,0.066,1)),
        (0.91,(0.21,0.075,0.020,1)), (0.98,(0.13,0.040,0.009,1))])
    finevec = node('ShaderNodeVectorMath','Longitudinal pore coordinates')
    finevec.operation = 'MULTIPLY'
    finevec.inputs[1].default_value = (190,190,3)
    link(coord,'Generated',finevec,0)
    pores = node('ShaderNodeTexNoise','Fine pores and fibers')
    pores.inputs['Scale'].default_value = 1
    pores.inputs['Detail'].default_value = 2
    pores.inputs['Roughness'].default_value = 0.7
    link(finevec,'Vector',pores,'Vector')
    porecolor = ramp('Pore shading',pores.outputs['Fac'],[(0.2,(0.18,0.12,0.06,1)),(0.4,(0.65,0.54,0.41,1)),(0.55,(1,0.92,0.8,1)),(0.8,(0.87,0.78,0.63,1))])
    mix = node('ShaderNodeMixRGB','Layer grain and pores')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 0.65
    link(growth,'Color',mix,1)
    link(porecolor,'Color',mix,2)
    bump = node('ShaderNodeBump','Microscopic grain relief')
    bump.inputs['Strength'].default_value = 0.22
    bump.inputs['Distance'].default_value = 0.0007
    link(pores,'Fac',bump,'Height')
    rough = node('ShaderNodeMapRange','Roughness variation')
    rough.inputs['To Min'].default_value = 0.38
    rough.inputs['To Max'].default_value = 0.62
    link(pores,'Fac',rough,'Value')
    bsdf = node('ShaderNodeBsdfPrincipled','Wood surface')
    link(mix,'Color',bsdf,'Base Color')
    link(rough,'Result',bsdf,'Roughness')
    link(bump,'Normal',bsdf,'Normal')
    output = node('ShaderNodeOutputMaterial','Material output')
    link(bsdf,'BSDF',output,'Surface')
    for i,n in enumerate(ns): n.location = ((i%6)*230, -(i//6)*220)
    cube.data.materials.append(mat)
    return cube

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='generated/wood-drop')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out=Path(args.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    addon.register()
    source=create_wood()
    addon.apply_parameters(source,bpy.context,'DENSITY',600.,'Wood','SOLID')
    from material_physics.water_scene import build
    scene,wood,domain,metrics=build(source,str(out/'liquid_cache'),density=600.)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Wood_Falling_Into_Water.blend'))
    print('DEMO_BUILD_OK',metrics['final_submerged_fraction'])

if __name__=='__main__': main()
