"""Build an installable legacy Blender add-on ZIP from an explicit allowlist."""
from pathlib import Path
import zipfile, hashlib
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'dist'; out.mkdir(exist_ok=True)
target=out/'materialflow-blender-v0.3.1.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted((ROOT/'material_physics').glob('*.py')):
        z.write(p,p.relative_to(ROOT).as_posix())
    for name in ['LICENSE','THIRD_PARTY_NOTICES.md']:
        z.write(ROOT/name,'material_physics/'+name)
    z.write(ROOT/'docs/SETUP.md','material_physics/SETUP.md')
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(out/'SHA256SUMS.txt').write_text(f'{digest}  {target.name}\n',encoding='utf-8')
print(target)
print(digest)
