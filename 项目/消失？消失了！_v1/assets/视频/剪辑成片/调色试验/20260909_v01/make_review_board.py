"""A review board from the actual encoded derivatives, not simulated grading."""
import io
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

JOB=Path(__file__).resolve().parent
shots={s['number']:s for s in json.loads((JOB/'shots.json').read_text(encoding='utf-8'))}
records=json.loads((JOB/'派生链.json').read_text(encoding='utf-8'))
by_shot={n:r for r in records for n in r['shots']}
selected=[(1,'办公日景 · 中性色与高光'),(9,'深夜加班 · 保留低调与脸部'),
          (10,'入睡 · 轻扶已有暗部'),(12,'清晨卧室 · 暖光与自然肤色'),
          (24,'公司消失 · 保持现实环境'),(33,'理发异常 · 暖木色与黄色围布')]
canvas=Image.new('RGB',(1480,780),'#17191b');draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',19)
for index,(n,label) in enumerate(selected):
    x=index%2*740;y=index//2*260
    for side,path in enumerate((by_shot[n]['source'],by_shot[n]['output'])):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(shots[n]['sample_source_seconds']),
            '-i',path,'-frames:v','1','-vf','setparams=range=limited:colorspace=bt709:color_trc=bt709:color_primaries=bt709,scale=364:156',
            '-f','image2pipe','-c:v','png','-'])
        canvas.paste(Image.open(io.BytesIO(raw)),(x+side*370+3,y+30))
    draw.text((x+8,y+5),label,font=font,fill='white')
    draw.text((x+8,y+195),'原片',font=font,fill='#adb4bc')
    draw.text((x+378,y+195),'调色 v01',font=font,fill='#8cd5ba')
    draw.text((x+8,y+226),f"片段 {n:02d} · 实际输出同帧对照",font=font,fill='#adb4bc')
canvas.save(JOB/'调色对照预览.jpg',quality=96)
