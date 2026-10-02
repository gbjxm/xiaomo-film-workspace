"""Read back the existing published excerpt and align only its metadata ID."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

JOB=Path(__file__).resolve().parent
DEST=Path(r'D:\JianyingPro Drafts\消失？消失了！-副本-电影加强v02-前60秒')
SOURCE=Path(r'D:\JianyingPro Drafts\消失？消失了！-副本')
ROOT=Path(os.environ['LOCALAPPDATA'])/'JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json'
sys.path.insert(0,r'D:\codex\tools\jianying-color-lab\helpers')
from aoguai_draft_crypto import decrypt_draft_file,encrypt_draft_file
from publish_minute_copy import first_minute

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

root_before=ROOT.read_bytes();root=json.loads(root_before)
matches=[e for e in root['all_draft_store'] if e.get('draft_name')==DEST.name]
assert len(matches)==1 and Path(matches[0]['draft_fold_path']).resolve()==DEST.resolve()
entry=matches[0]
assert entry['tm_duration']==60_000_000
assert not (DEST/'.locked').exists(),'Do not modify the new copy while open'
actual=JOB/'草稿解读/actual_60_content.json';actual_meta=JOB/'草稿解读/actual_60_meta.json'
decrypt_draft_file(DEST/'draft_content.json',actual,jy_install_dir=r'D:\JianyingPro\11.3.0.14362',timeout=45)
decrypt_draft_file(DEST/'draft_meta_info.json',actual_meta,jy_install_dir=r'D:\JianyingPro\11.3.0.14362',timeout=45)
content=read(actual);meta=read(actual_meta)
assert content==read(JOB/'草稿解读/graded_60_content.json')
assert meta['tm_duration']==60_000_000
before_hash=sha(DEST/'draft_meta_info.json')
meta['draft_id']=entry['draft_id']
aligned=JOB/'草稿解读/aligned_60_meta.json';write(aligned,meta)
encoded=JOB/'草稿解读/aligned_60_meta.enc.json'
encrypt_draft_file(aligned,encoded,jy_install_dir=r'D:\JianyingPro\11.3.0.14362',timeout=45)
assert sha(DEST/'draft_meta_info.json')==before_hash and ROOT.read_bytes()==root_before
pending=DEST/'codex_v02_metadata_align.tmp'
assert not pending.exists()
shutil.copyfile(encoded,pending);os.replace(pending,DEST/'draft_meta_info.json')
decrypt_draft_file(DEST/'draft_meta_info.json',actual_meta,jy_install_dir=r'D:\JianyingPro\11.3.0.14362',timeout=45)
assert read(actual_meta)==meta
expected=first_minute(read(JOB/'草稿解读/draft_content.dec.json'))
restored=deepcopy(content);paths={m['id']:m['path'] for m in expected['materials']['videos']}
for m in restored['materials']['videos']:m['path']=paths[m['id']]
assert restored==expected and content['tracks']==expected['tracks']
assert sha(DEST/'draft_content.json')==sha(DEST/'Timelines'/content['id']/'draft_content.json')
for name in ('draft_content.json','draft_meta_info.json'):
    # The editor may re-encrypt identical JSON with different bytes during a save.
    source_now=JOB/'草稿解读'/('verify_source_'+name)
    decrypt_draft_file(SOURCE/name,source_now,jy_install_dir=r'D:\JianyingPro\11.3.0.14362',timeout=45)
    baseline=JOB/'草稿解读'/name.replace('.json','.dec.json')
    assert read(source_now)==read(baseline),'Original semantic content changed'
assert ROOT.read_bytes()==root_before
records=read(JOB/'派生链.json');qc=read(JOB/'色彩专项检查.json');preview=read(JOB/'一分钟预览检查.json')
receipt={'draft':str(DEST),'draft_id':meta['draft_id'],'duration_seconds':60,'track_count':len(content['tracks']),
    'segment_count':sum(len(t.get('segments',[])) for t in content['tracks']),
    'graded_visible_segments':23,'derived_files':len(records),'scope':'first minute only',
    'editorial_check':'matches original first minute; boundary-crossing final clips trimmed at 60s',
    'audio_tracks':'matches the first-minute excerpt','source_copy':'semantic content unchanged; no edits to original','v01':'not overwritten',
    'encryption_and_registry_id':'matched','content_sha256':sha(DEST/'draft_content.json'),
    'meta_sha256':sha(DEST/'draft_meta_info.json'),'preview':preview['file'],'preview_sha256':sha(Path(preview['file'])),
    'preview_duration':float(preview['probe']['format']['duration']),'preview_frames':int(preview['probe']['streams'][0]['nb_frames']),
    'preview_audio':'silent; native draft retains audio','decode':'passed',
    'temporal_samples':qc['temporal_sample_count'],'near_black_white_area_alerts':qc['near_black_white_area_alerts'],
    'hard_clip_area_alerts':qc['hard_clip_alerts'],
    'dark_review':'Shots 3 and 20 inspected side-by-side; stronger silhouette/clothing/door-frame blacks retained as candidate styling, not final QC approval.',
    'native_gui_full_playback':'not performed','status':'ready for user one-minute style review'}
write(JOB/'调色交付回执.json',receipt)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
