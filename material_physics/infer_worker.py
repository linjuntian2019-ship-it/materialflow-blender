"""Local Apple DMS worker. No object names or material metadata enter the model."""
import sys,json,time,traceback
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import torch

IDS = [1,2,3,4,5,6,7,8,9,10,11,12,13,15,16,17,18,19,20,21,23,24,26,27,29,30,32,33,34,35,36,37,38,39,41,43,44,46,47,48,49,50,51,52,53,56]
job = Path(sys.argv[1])
def write(name,data):
    p=job/name
    temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    # Retry the short Windows sharing violation while the UI reads progress.
    for attempt in range(40):
        try:
            temp.replace(p)
            return
        except PermissionError:
            if attempt == 39: raise
            time.sleep(0.025)
def run():
    config=json.loads((job/'job.json').read_text(encoding='utf-8'))
    taxonomy=json.loads(Path(config['taxonomy']).read_text(encoding='utf-8'))
    names=[taxonomy['names'][i] for i in IDS]
    colors=np.array([taxonomy['srgb_colormap'][i] for i in IDS],dtype=np.uint8)
    if not torch.cuda.is_available(): raise RuntimeError('未检测到可用 CUDA，请检查独立 Python 环境')
    model=torch.jit.load(config['model'],map_location='cuda').eval()
    mean=torch.tensor([0.485,0.456,0.406],device='cuda').view(1,3,1,1)*255
    std=torch.tensor([0.229,0.224,0.225],device='cuda').view(1,3,1,1)*255
    views=json.loads((job/'views.json').read_text(encoding='utf-8'))
    results=[]
    scores=[]
    votes=np.zeros(46,dtype=int)
    sheet=Image.new('RGB',(1536,4*315),'#f4f4f4')
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',15) if Path('C:/Windows/Fonts/msyh.ttc').exists() else ImageFont.load_default()
    for i,v in enumerate(views):
        write('progress.json',{'stage':'infer','fraction':0.8+0.2*i/len(views),'message':f'本地识别 {i+1}/{len(views)}：{v["label"]}'})
        rgba=Image.open(job/v['image']).convert('RGBA')
        rgb=Image.alpha_composite(Image.new('RGBA',rgba.size,(190,190,190,255)),rgba).convert('RGB')
        mask=np.asarray(Image.open(job/v['mask']).convert('RGBA').getchannel('A'))>=250
        if mask.sum()<32:
            results.append({'label':v['label'],'top':'不可见','share':0.,'ranked':[],'seconds':0.})
            x,y=i%3*512,i//3*315
            draw=ImageDraw.Draw(sheet)
            draw.text((x+8,y+4),v['label']+' | 此视角可见面积不足',font=font,fill='black')
            continue
        tensor=torch.from_numpy(np.asarray(rgb).copy().transpose(2,0,1)).float().unsqueeze(0).cuda()
        tensor=(tensor-mean)/std
        with torch.inference_mode():
            torch.cuda.synchronize()
            start=time.perf_counter()
            output=model(tensor)
            torch.cuda.synchronize()
            seconds=time.perf_counter()-start
            labels=output[0].cpu()[0,0].numpy().astype(np.int64)
        counts=np.bincount(labels[mask],minlength=46)
        shares=counts/counts.sum()*100
        top=int(shares.argmax())
        votes[top]+=1
        scores.append(shares)
        rank=[{'name':names[k],'share':float(shares[k])} for k in np.argsort(-shares)[:5] if shares[k]>0]
        results.append({'label':v['label'],'top':names[top],'share':float(shares[top]),'ranked':rank,'seconds':seconds})
        rgb.save(job/(v['name']+'_input.png'))
        seg=colors[labels].copy()
        seg[~mask]=(235,235,235)
        segimage=Image.fromarray(seg)
        segimage.save(job/(v['name']+'_segmentation.png'))
        np.save(job/(v['name']+'_labels.npy'),labels.astype('uint8'))
        x,y=i%3*512,i//3*315
        sheet.paste(rgb.resize((256,256)),(x,y+28))
        sheet.paste(segimage.resize((256,256),Image.Resampling.NEAREST),(x+256,y+28))
        draw=ImageDraw.Draw(sheet)
        draw.text((x+8,y+4),v['label']+' | 原图 / 分割',font=font,fill='black')
        draw.text((x+8,y+288),f'{names[top]}: {shares[top]:.1f}% 可见像素',font=font,fill='black')
    if not scores: raise RuntimeError('所有视角可见面积均不足，请检查网格')
    mean_scores=np.mean(scores,axis=0)
    candidates=[{'name':names[k],'share':float(mean_scores[k]),'votes':int(votes[k])} for k in np.argsort(-mean_scores)[:5] if mean_scores[k]>0]
    winner=candidates[0]
    supported={'Wood','Wood, tree','Metal','Plastic, clear','Plastic, non-clear','Stone, natural','Stone, polished','Glass','Cork/corkboard','Water'}
    ambiguous=winner['votes']<9 or winner['share']<60 or winner['name'] not in supported
    write('result.json',{'candidates':candidates,'views':results,'valid_views':len(scores),'ambiguous':ambiguous,'reason':'视角结果存在分歧或无法对应可靠物理材料，请手动确认。' if ambiguous else 'AI 结果仅供参考，请确认材料并输入物理参数。','method':'12个视角中有效视角的像素占比等权平均；不是置信度、准确率或体积比例。','gpu':torch.cuda.get_device_name(),'geometry_signature':config['geometry_signature']})
    sheet.save(job/'contact_sheet.png')
    write('progress.json',{'stage':'done','fraction':1,'message':'识别完成，等待用户确认'})
try:
    run()
except Exception as exc:
    write('error.json',{'error':str(exc),'traceback':traceback.format_exc()})
    raise
