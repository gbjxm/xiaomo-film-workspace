"""Inspect only the saved copy's visible video segments; never edit sources."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

JOB = Path(__file__).resolve().parent
DATA = json.loads((JOB / '草稿解读/draft_content.dec.json').read_text(encoding='utf-8'))
MATERIALS = {m['id']: m for m in DATA['materials']['videos']}
FRAMES = JOB / '审看/原片'
FRAMES.mkdir(parents=True, exist_ok=True)
FONT = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 17)
shots = []
for ti, track in enumerate(DATA['tracks']):
    if track.get('type') not in ('video', 'mixed') or (track.get('attribute', 0) & 2):
        continue
    for segment in track.get('segments', []):
        material = MATERIALS.get(segment['material_id'])
        if material:
            shots.append({'number': len(shots) + 1, 'track_index': ti, 'segment': segment, 'material': material})


def inspect(shot):
    n, segment, material = shot['number'], shot['segment'], shot['material']
    time = (segment['source_timerange'].get('start', 0) + segment['source_timerange']['duration'] * .5) / 1e6
    data = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(time), '-i', material['path'],
                                   '-frames:v', '1', '-vf', 'scale=735:315', '-f', 'image2pipe', '-c:v', 'png', '-'])
    frame = Image.open(io.BytesIO(data)).convert('RGB')
    frame.save(FRAMES / f'{n:02d}.png')
    arr = np.asarray(frame, dtype=np.float32) / 255
    y = arr @ np.array([.2126, .7152, .0722])
    shot['sample_source_seconds'] = time
    shot['stats'] = {'rgb_mean': arr.mean(axis=(0,1)).round(5).tolist(),
                     'luma_percentiles': np.percentile(y, [1,10,50,90,99]).round(5).tolist(),
                     'near_white_fraction': float((y > .98).mean()), 'near_black_fraction': float((y < .01).mean())}
    return shot


with ThreadPoolExecutor(max_workers=4) as pool:
    shots = list(pool.map(inspect, shots))
for page_start in range(0, len(shots), 12):
    page = shots[page_start:page_start + 12]
    sheet = Image.new('RGB', (1600, 700), '#151515')
    draw = ImageDraw.Draw(sheet)
    for k, shot in enumerate(page):
        x, y = (k % 4) * 400, (k // 4) * 233
        frame = Image.open(FRAMES / f"{shot['number']:02d}.png").resize((392,168))
        sheet.paste(frame, (x + 4, y + 4))
        seg = shot['segment']
        label = f"{shot['number']:02d}  {seg['target_timerange'].get('start',0)/1e6:.2f}s  /  {seg['target_timerange']['duration']/1e6:.2f}s"
        draw.text((x+8,y+175), label, fill='white', font=FONT)
        draw.text((x+8,y+201), shot['material']['material_name'], fill='#bbbbbb', font=FONT)
    sheet.save(JOB / '审看' / f'原片联系表_{page_start//12+1}.jpg', quality=95)
(JOB / 'shots.json').write_text(json.dumps(shots, ensure_ascii=False, indent=2), encoding='utf-8')
for shot in shots:
    print(json.dumps({'n':shot['number'],'file':shot['material']['material_name'],'source_t':shot['sample_source_seconds'],
                      'timeline':shot['segment']['target_timerange'], 'stats':shot['stats']},ensure_ascii=False))
