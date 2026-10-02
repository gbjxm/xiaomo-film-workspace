"""Compare original, light v01 and stronger v02 using actual encoded media."""
import io
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

JOB=Path(__file__).resolve().parent
OLD=JOB.parent/'20260909_v01'
shots={s['number']:s for s in json.loads((JOB/'shots.json').read_text(encoding='utf-8'))}
def index(path):
    return {n:r for r in json.loads(path.read_text(encoding='utf-8')) for n in r['shots']}
v1=index(OLD/'派生链.json');v2=index(JOB/'派生链.json')
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',21)
small=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',18)
image=Image.new('RGB',(1500,1060),'#15171b');draw=ImageDraw.Draw(image)
for column,label in enumerate(('原片','v01 · 轻校色','v02 · 电影感加强')):
    draw.text((column*500+12,10),label,font=font,fill=('#e7e7e7' if column<2 else '#95d3b9'))
for row,(n,title) in enumerate(((1,'办公日景：黑位与冷暖分离'),(9,'深夜：保留脸部与低调空间'),(12,'清晨：更浓郁的暖光与材料色'),(22,'街道：肤色与环境分离'))):
    y=50+row*250
    draw.text((12,y),title,font=small,fill='#c4c7ce')
    for column,path in enumerate((v2[n]['source'],v1[n]['output'],v2[n]['output'])):
        raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-ss',str(shots[n]['sample_source_seconds']),'-i',path,
            '-frames:v','1','-vf','setparams=range=limited:colorspace=bt709:color_trc=bt709:color_primaries=bt709,scale=490:210',
            '-f','image2pipe','-c:v','png','-'])
        decoded=Image.open(io.BytesIO(raw))
        image.paste(decoded,(column*500+5,y+30))
        if n==1 and column==2:
            decoded.save(JOB/'审看/调色/01.png')
image.save(JOB/'原片_v01_v02对照.jpg',quality=96)
