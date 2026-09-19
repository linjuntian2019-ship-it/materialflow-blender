"""Conservative mapping from DMS appearance labels to editable physical types."""
TYPE_ITEMS=[('SOLID','固体','设置密度或质量'),('LIQUID','液体','设置密度、黏度和表面张力')]
TYPE_LABELS={'SOLID':'固体','LIQUID':'液体'}
SOLIDS={'Bone/teeth/horn','Brickwork','Cardboard','Carpet/rug','Ceiling tile','Ceramic',
        'Chalkboard/blackboard','Concrete','Cork/corkboard','Engineered stone','Fabric/cloth',
        'Fiberglass wool','Gemstone/quartz','Glass','Ice','Leather','Metal','Mirror',
        'Paper','Pearl','Photograph/painting','Plastic, clear','Plastic, non-clear',
        'Rubber/latex','Sponge','Stone, natural','Stone, polished','Styrofoam','Tile',
        'Wallpaper','Whiteboard','Wicker','Wood','Wood, tree','Asphalt'}
LIQUIDS={'Water','Liquid, non-water'}

def suggest_type(result):
    candidates=result.get('candidates',[])
    if not candidates: return None
    top=candidates[0]
    if top.get('share',0)<60 or top.get('votes',0)<9: return None
    if top['name'] in LIQUIDS: return 'LIQUID'
    if top['name'] in SOLIDS: return 'SOLID'
    return None
