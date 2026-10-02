"""Build scene-specific, inspectable color transforms and loss-preserving derivatives."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

JOB = Path(__file__).resolve().parent
CONFIG = json.loads((JOB/'grade_profiles.json').read_text(encoding='utf-8'))
SHOTS = json.loads((JOB/'shots.json').read_text(encoding='utf-8'))
FONT = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 18)
LUMA = np.array([.2126,.7152,.0722])


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def transform(rgb, profile):
    # Stronger v02 scene look, generated from ORIGINAL media; never stacked over v01.
    y = rgb @ LUMA
    mx=rgb.max(axis=-1);mn=rgb.min(axis=-1);delta=mx-mn
    safe=np.maximum(delta,1e-10)
    hue=np.where(mx==rgb[...,0],(rgb[...,1]-rgb[...,2])/safe,
        np.where(mx==rgb[...,1],2+(rgb[...,2]-rgb[...,0])/safe,4+(rgb[...,0]-rgb[...,1])/safe))
    hue=(hue*60)%360
    chroma=delta/np.maximum(mx,1e-10)
    def smooth(a,b,z):
        t=np.clip((z-a)/(b-a),0,1)
        return t*t*(3-2*t)
    skin=smooth(5,18,hue)*(1-smooth(42,60,hue))*smooth(.08,.20,chroma)*(1-smooth(.65,.90,chroma))
    skin*=smooth(.08,.23,y)*(1-smooth(.78,.94,y))
    target = np.interp(y, CONFIG['x'], profile['y'])
    target += profile['skin_lift']*skin
    out = rgb * (target / np.maximum(y,1e-10))[...,None]
    gains = np.array(profile['gains'])
    mask = np.clip(y/.12,0,1) * np.clip((1-y)/.16,0,1)
    balanced = out * (1 + (gains-1) * mask[...,None])
    new_y = balanced @ LUMA
    balanced *= (target / np.maximum(new_y,1e-10))[...,None]
    # Split tone has zero luminance contribution and fades at black/white and skin hues.
    low=smooth(.004,.065,y)*(1-smooth(.14,.56,y))*(1-.85*skin)
    high=smooth(.30,.75,y)*(1-smooth(.84,1,y))*(1-.85*skin)
    shadow=np.array(profile['shadows']);shadow-=shadow@LUMA
    highlight=np.array(profile['highlights']);highlight-=highlight@LUMA
    balanced+=low[...,None]*shadow+high[...,None]*highlight
    green = np.clip((rgb[...,1]-np.maximum(rgb[...,0],rgb[...,2]))/.10,0,1)
    blue=np.clip((rgb[...,2]-np.maximum(rgb[...,0],rgb[...,1]))/.12,0,1)
    saturation = profile['saturation'] * (1-green*(1-profile['green_sat']))*(1+blue*(profile['blue_sat']-1))
    saturation=saturation*(1-.9*skin)+1.025*(.9*skin)
    return np.clip(target[...,None] + (balanced-target[...,None])*saturation[...,None],0,1)


def make_lut(name, profile):
    directory = JOB/'实现参数'
    directory.mkdir(exist_ok=True)
    axis = np.linspace(0,1,33)
    rgb = np.array([(r,g,b) for b in axis for g in axis for r in axis])
    mapped = transform(rgb, profile)
    path = directory/(name+'.cube')
    header = f'TITLE "Xiaomo cinematic v02 {name}"\nLUT_3D_SIZE 33\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n'
    path.write_text(header + '\n'.join(' '.join(f'{v:.7f}' for v in row) for row in mapped)+'\n',encoding='ascii')
    return path


def filter_for(name):
    # Relative LUT paths keep the graph safe for Unicode Windows paths.
    p=CONFIG['profiles'][name]
    return (f"setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709,format=gbrp16le,"
            f"lut3d=file=实现参数/{name}.cube:interp=tetrahedral,scale=out_range=full:out_color_matrix=bt709,format=yuv444p,"
            f"unsharp=5:5:-0.12:5:5:0,vignette=angle=PI/{p['vignette']}:dither=1,"
            f"noise=c0s={p['grain']}:c0f=t+u:c0_seed=2709:c1s=0:c2s=0,"
            f"scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p")


def inspect_frames():
    for sub in ('原片709','调色'):
        (JOB/'审看'/sub).mkdir(parents=True,exist_ok=True)
    mapping = {n:name for name,p in CONFIG['profiles'].items() for n in p['shots']}
    def one(shot):
        n=shot['number']; name=mapping[n]
        common=['ffmpeg','-v','error','-threads','2','-ss',str(shot['sample_source_seconds']),'-i',shot['material']['path'],'-frames:v','1']
        for sub, graph in (
            ('原片709','setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709,scale=735:315'),
            ('调色',filter_for(name)+',scale=735:315'),
        ):
            data=subprocess.check_output(common+['-vf',graph,'-f','image2pipe','-c:v','png','-'],cwd=JOB)
            (JOB/'审看'/sub/f'{n:02d}.png').write_bytes(data)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one,SHOTS))
    for start in range(0,len(SHOTS),8):
        page=SHOTS[start:start+8]
        sheet=Image.new('RGB',(1500,850),'#17191a');draw=ImageDraw.Draw(sheet)
        for k,shot in enumerate(page):
            x=(k%2)*750;y=(k//2)*212;n=shot['number']
            for offset,sub in ((0,'原片709'),(375,'调色')):
                image=Image.open(JOB/'审看'/sub/f'{n:02d}.png').resize((367,157))
                sheet.paste(image,(x+offset+4,y+4))
            label=f"{n:02d}  左原片 / 右电影加强v02"
            draw.text((x+8,y+166),label,font=FONT,fill='white')
        sheet.save(JOB/'审看'/f'调色对照_{start//8+1}.jpg',quality=96)


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,start_time,sample_rate,channels:format=duration',
        '-of','json',str(path)],encoding='utf-8'))


def render_media():
    destination=JOB/'调色派生素材';destination.mkdir(exist_ok=True)
    mapping={n:name for name,p in CONFIG['profiles'].items() for n in p['shots']}
    jobs={}
    for shot in SHOTS:
        key=(shot['material']['path'],mapping[shot['number']])
        jobs.setdefault(key,[]).append(shot['number'])
    def one(job):
        (source,name),numbers=job
        recipe=filter_for(name)+json.dumps(CONFIG['profiles'][name],sort_keys=True)
        key=hashlib.sha256((source+'|'+name+'|'+recipe).encode()).hexdigest()[:10]
        output=destination/(name+'_'+key+'.mp4')
        if output.exists():
            raise FileExistsError(output)
        before=digest(source)
        command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n','-threads','2',
            '-i',source,'-map','0:v:0','-map','0:a?','-map_metadata','0',
            '-vf',filter_for(name),'-c:v','libx264','-preset','fast','-crf','16','-threads','3',
            '-fps_mode','passthrough','-c:a','copy','-color_primaries','bt709','-color_trc','bt709',
            '-colorspace','bt709','-color_range','tv','-movflags','+faststart',str(output)]
        subprocess.run(command,cwd=JOB,check=True)
        source_probe=probe(source); output_probe=probe(output)
        a=next(s for s in source_probe['streams'] if s['codec_type']=='video')
        b=next(s for s in output_probe['streams'] if s['codec_type']=='video')
        for field in ('width','height','avg_frame_rate','nb_frames'):
            assert a.get(field)==b.get(field),(name,field,a.get(field),b.get(field))
        assert abs(float(a['duration'])-float(b['duration'])) < .0001,(a,b)
        subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(output),'-f','null','-'],check=True)
        assert digest(source)==before,'Source changed during rendering'
        record={'source':source,'source_sha256':before,'profile':name,'shots':numbers,
                'output':str(output),'output_sha256':digest(output),'source_probe':source_probe,'output_probe':output_probe,
                'decode':'passed','timing_geometry':'matched','command':command}
        print(json.dumps({'profile':name,'shots':numbers,'status':'rendered_and_verified'},ensure_ascii=False),flush=True)
        return record
    with ThreadPoolExecutor(max_workers=2) as pool:
        records=list(pool.map(one,jobs.items()))
    (JOB/'派生链.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'derivatives':len(records),'graded_segments':len(SHOTS)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true');args=parser.parse_args()
    for name,profile in CONFIG['profiles'].items():make_lut(name,profile)
    if args.render:render_media()
    else:inspect_frames()
