"""Physical volume of one closed, consistently oriented evaluated solid mesh."""
import bmesh
import hashlib
import struct
from mathutils import Matrix, Vector

def recognition_signature(obj,depsgraph,unit_scale=1.):
    """Open surfaces can be classified even though their volume is undefined."""
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh()
    try:
        digest=hashlib.sha256(struct.pack('<d',unit_scale))
        for v in mesh.vertices:
            digest.update(struct.pack('<3d',*(evaluated.matrix_world@v.co)))
        for p in mesh.polygons:
            digest.update(struct.pack('<I',len(p.vertices)))
            for i in p.vertices: digest.update(struct.pack('<I',i))
        return digest.hexdigest()
    finally: evaluated.to_mesh_clear()

def measure(obj, depsgraph, unit_scale=1.0):
    if not obj or obj.type != 'MESH':
        raise ValueError('请选择一个网格物体')
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        if not bm.faces or not bm.edges:
            raise ValueError('网格没有封闭表面')
        if any(not e.is_manifold for e in bm.edges):
            raise ValueError('网格不封闭或存在非流形边，请先修复模型')
        if any(not e.is_contiguous for e in bm.edges):
            raise ValueError('表面法线方向不一致，请先重新计算外侧法线')
        if any(not v.link_faces for v in bm.verts):
            raise ValueError('网格包含孤立顶点，请先清理')
        pending = [next(iter(bm.verts))]
        seen = set(pending)
        while pending:
            for edge in pending.pop().link_edges:
                for v in edge.verts:
                    if v not in seen:
                        seen.add(v)
                        pending.append(v)
        if len(seen) != len(bm.verts):
            raise ValueError('原型仅支持单个连续实心网格；请拆分多个壳体')
        bm.transform(evaluated.matrix_world)
        center = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        digest = hashlib.sha256()
        digest.update(struct.pack('<d', unit_scale))
        bm.verts.index_update()
        for v in bm.verts:
            digest.update(struct.pack('<3d', *v.co))
        for f in bm.faces:
            digest.update(struct.pack('<I', len(f.verts)))
            for v in f.verts:
                digest.update(struct.pack('<I',v.index))
        bm.transform(Matrix.Translation(-center))
        volume = abs(bm.calc_volume(signed=True)) * unit_scale**3
        if not (1e-15 < volume < 1e30):
            raise ValueError('体积为零或无效，请检查尺寸和场景单位')
        return volume, digest.hexdigest()
    finally:
        bm.free()
        evaluated.to_mesh_clear()
