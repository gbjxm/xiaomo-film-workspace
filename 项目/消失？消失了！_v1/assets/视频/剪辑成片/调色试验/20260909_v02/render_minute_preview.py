"""Render a 60-second silent color preview using the saved cut and static transforms."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

JOB=Path(__file__).resolve().parent
shots=json.loads((JOB/'shots.json').read_text(encoding='utf-8'))
records=json.loads((JOB/'派生链.json').read_text(encoding='utf-8'))
by_shot={n:r for r in records for n in r['shots']}
parts=JOB/'预览片段_正式';parts.mkdir(exist_ok=True)
W,H,FPS=1470,630,30


def render(shot):
    s=shot['segment'];tr=s['target_timerange'];sr=s['source_timerange']
    frames=round(tr['duration']/1e6*FPS)
    speed=sr['duration']/tr['duration']
    clip=s.get('clip',{});scale=clip.get('scale',{});pos=clip.get('transform',{})
    sx=scale.get('x',1);sy=scale.get('y',1)
    sw=max(W,round(W*sx/2)*2);sh=max(H,round(H*sy/2)*2)
    cx=max(0,min(sw-W,round((sw-W)/2-pos.get('x',0)*W/2)))
    cy=max(0,min(sh-H,round((sh-H)/2+pos.get('y',0)*H/2)))
    assert not clip.get('rotation',0),'Rotation needs explicit preview support'
    graph=[f"trim=duration={sr['duration']/1e6:.9f}",f'setpts=(PTS-STARTPTS)/{speed:.12f}']
    if clip.get('flip',{}).get('horizontal'):graph.append('hflip')
    if clip.get('flip',{}).get('vertical'):graph.append('vflip')
    graph.extend([f'scale={sw}:{sh}',f'crop={W}:{H}:{cx}:{cy}',
                  'setsar=1','tpad=stop_mode=clone:stop_duration=0.1','fps=30'])
    out=parts/f"shot_{shot['number']:02d}.mp4"
    if out.exists():raise FileExistsError(out)
    cmd=['ffmpeg','-v','error','-nostdin','-n','-threads','1','-ss',str(sr.get('start',0)/1e6),
         '-i',by_shot[shot['number']]['output'],'-an','-vf',','.join(graph),'-frames:v',str(frames),
         '-c:v','libx264','-preset','fast','-crf','18','-threads','2','-profile:v','high','-level','4.1',
         '-pix_fmt','yuv420p','-video_track_timescale','30000','-movie_timescale','30000','-color_primaries','bt709',
         '-color_trc','bt709','-colorspace','bt709','-color_range','tv',str(out)]
    subprocess.run(cmd,check=True)
    return out,frames


with ThreadPoolExecutor(max_workers=3) as pool:
    rendered=list(pool.map(render,shots))
assert sum(frames for _,frames in rendered)==1800
playlist=JOB/'preview.ffconcat'
playlist.write_text('ffconcat version 1.0\n'+''.join(f"file '预览片段_正式/{path.name}'\nduration {frames/FPS:.12f}\n" for path,frames in rendered),encoding='utf-8')
output=JOB/'消失_电影感加强v02_前60秒_静音预览_正式.mp4'
subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-f','concat','-safe','0','-i',str(playlist),
                '-c','copy','-video_track_timescale','30000','-movie_timescale','30000','-movflags','+faststart',str(output)],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
    'format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,duration',
    '-of','json',str(output)],encoding='utf-8'))
assert abs(float(probe['format']['duration'])-60.0)<1/30000,probe
assert int(probe['streams'][0]['nb_frames'])==1800,probe
assert not any(s['codec_type']=='audio' for s in probe['streams'])
subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],check=True)
(JOB/'一分钟预览检查.json').write_text(json.dumps({'file':str(output),'probe':probe,'decode':'passed',
    'method':'Silent preview reconstructed from saved source ranges, speed, static crop/scale/flip. Not an export performed by Jianying.',
    'native_audio':'preserved in the corresponding editable draft'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'preview':str(output),'duration':60.0,'frames':1800,'audio':'silent','decode':'passed'},ensure_ascii=False))
