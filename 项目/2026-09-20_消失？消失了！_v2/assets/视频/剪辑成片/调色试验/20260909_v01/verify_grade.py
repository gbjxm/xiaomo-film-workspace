"""Verify rendered media timing, copied audio and temporal sample consistency."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import numpy as np

JOB=Path(__file__).resolve().parent
records=json.loads((JOB/'派生链.json').read_text(encoding='utf-8'))
shots=json.loads((JOB/'shots.json').read_text(encoding='utf-8'))
by_shot={n:r for r in records for n in r['shots']}


def frame(path,t):
    raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-ss',str(t),'-i',str(path),'-frames:v','1',
        '-vf','setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709,scale=490:210',
        '-pix_fmt','rgb24','-f','rawvideo','-'])
    return np.frombuffer(raw,np.uint8).reshape(210,490,3).astype(np.float32)/255


@lru_cache(maxsize=32)
def audio_hash(path):
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c:a','copy',
                                    '-f','hash','-hash','sha256','-'],text=True).strip()


def verify_audio(record):
    original=audio_hash(record['source']);graded=audio_hash(record['output'])
    assert original==graded,record['output']
    aa=[s for s in record['source_probe']['streams'] if s['codec_type']=='audio']
    bb=[s for s in record['output_probe']['streams'] if s['codec_type']=='audio']
    assert len(aa)==len(bb)
    for a,b in zip(aa,bb):
        for key in ('codec_name','sample_rate','channels','duration','start_time'):
            assert a.get(key)==b.get(key),(key,a,b)
    return {'profile':record['profile'],'output':record['output'],'audio_packet_hash':original,'audio_timing':'matched'}


def verify_shot(shot):
    record=by_shot[shot['number']];timerange=shot['segment']['source_timerange']
    points=[]
    for ratio in (.15,.5,.85):
        t=(timerange.get('start',0)+ratio*timerange['duration'])/1e6
        a=frame(record['source'],t);b=frame(record['output'],t)
        ya=a@np.array([.2126,.7152,.0722]);yb=b@np.array([.2126,.7152,.0722])
        points.append({'source_seconds':t,'mean_rgb_delta':float(np.abs(a-b).mean()),
            'black_before':float((ya<.01).mean()),'black_after':float((yb<.01).mean()),
            'white_before':float((ya>.98).mean()),'white_after':float((yb>.98).mean())})
    alerts=[p for p in points if p['black_after']>p['black_before']+.02 or p['white_after']>p['white_before']+.02]
    return {'shot':shot['number'],'samples':points,'clipping_alerts':alerts}


with ThreadPoolExecutor(max_workers=3) as pool:
    audio=list(pool.map(verify_audio,records))
with ThreadPoolExecutor(max_workers=3) as pool:
    visual=list(pool.map(verify_shot,shots))
report={'source_files':len(set(r['source'] for r in records)),'derived_files':len(records),
    'graded_segments':len(shots),'temporal_sample_count':sum(len(s['samples']) for s in visual),
    'audio_packets_and_timing':'matched','audio':audio,'visual':visual,
    'clipping_alerts':sum(len(s['clipping_alerts']) for s in visual),
    'native_application_full_playback':'not performed','display_calibration':'not verified'}
(JOB/'色彩专项检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('audio','visual')},ensure_ascii=False,indent=2))
