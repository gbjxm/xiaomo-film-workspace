"""Publish a new 60-second excerpt, preserve original editing inside that range."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import uuid

JOB=Path(__file__).resolve().parent
SOURCE=Path(r'D:\JianyingPro Drafts\消失？消失了！-副本')
DEST=SOURCE.parent/'消失？消失了！-副本-电影加强v02-前60秒'
ROOT=Path(os.environ['LOCALAPPDATA'])/'JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json'
INSTALL=r'D:\JianyingPro\11.3.0.14362'
sys.path.insert(0,r'D:\codex\tools\jianying-color-lab\helpers')
from aoguai_draft_crypto import encrypt_draft_file,decrypt_draft_file


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8')


def first_minute(data):
    result=deepcopy(data);limit=60_000_000
    for track in result['tracks']:
        if 'segments' not in track:continue
        kept=[]
        for seg in track['segments']:
            tr=seg['target_timerange'];start=tr.get('start',0)
            if start>=limit:continue
            original_duration=tr['duration'];duration=min(original_duration,limit-start)
            if duration!=original_duration:
                tr['duration']=duration
                if seg.get('source_timerange'):
                    seg['source_timerange']['duration']=round(seg['source_timerange']['duration']*duration/original_duration)
                if seg.get('render_timerange',{}).get('duration',0)>duration:
                    seg['render_timerange']['duration']=duration
            kept.append(seg)
        track['segments']=kept
    result['duration']=limit
    return result


def main():
    if DEST.exists():raise FileExistsError(DEST)
    snapshot=JOB/'原草稿快照'
    for filename in ('draft_content.json','draft_meta_info.json'):
        assert sha(SOURCE/filename)==sha(snapshot/filename),'Original copy changed; inspect first'
    original=read(JOB/'草稿解读/draft_content.dec.json')
    expected=first_minute(original);content=deepcopy(expected)
    records=read(JOB/'派生链.json');shots=read(JOB/'shots.json')
    by_shot={n:r for r in records for n in r['shots']}
    mats={m['id']:m for m in content['materials']['videos']}
    for shot in shots:
        rec=by_shot[shot['number']]
        assert sha(Path(rec['output']))==rec['output_sha256']
        mats[shot['material']['id']]['path']=Path(rec['output']).as_posix()
    restored=deepcopy(content);original_paths={m['id']:m['path'] for m in expected['materials']['videos']}
    for m in restored['materials']['videos']:m['path']=original_paths[m['id']]
    assert restored==expected,'Non-color changes other than the requested 60s trim'
    assert content['tracks']==expected['tracks']

    stage=JOB/'一分钟草稿待发布';shutil.copytree(snapshot,stage)
    meta=read(JOB/'草稿解读/draft_meta_info.dec.json');old_id=meta['draft_id'];new_id=str(uuid.uuid4()).upper()
    meta.update(draft_name=DEST.name,draft_id=new_id,draft_fold_path=DEST.as_posix(),draft_root_path=DEST.parent.as_posix(),
                tm_duration=60_000_000,tm_draft_create=int(time.time()*1e6),tm_draft_modified=int(time.time()*1e6))
    video_group=next(g for g in meta['draft_materials'] if g.get('type')==0)
    for rec in records:
        template=next((m for m in video_group['value'] if m.get('file_Path')==rec['source']),None)
        assert template is not None,rec['source']
        new=deepcopy(template);new.update(id=str(uuid.uuid4()),file_Path=Path(rec['output']).as_posix(),
            extra_info=Path(rec['source']).stem+' · 电影加强v02 · '+rec['profile'],md5='')
        video_group['value'].append(new)
    content_json=JOB/'草稿解读/graded_60_content.json';meta_json=JOB/'草稿解读/graded_60_meta.json'
    write(content_json,content);write(meta_json,meta)
    encrypted=JOB/'草稿解读/graded_60_content.enc.json';encrypted_meta=JOB/'草稿解读/graded_60_meta.enc.json'
    encrypt_draft_file(content_json,encrypted,jy_install_dir=INSTALL,timeout=45)
    encrypt_draft_file(meta_json,encrypted_meta,jy_install_dir=INSTALL,timeout=45)
    tid=content['id']
    for target in (stage/'draft_content.json',stage/'draft_content.json.bak',stage/'Timelines'/tid/'draft_content.json',stage/'Timelines'/tid/'draft_content.json.bak'):
        shutil.copyfile(encrypted,target)
    for target in stage.rglob('template-2.tmp'):
        if sha(target)==sha(snapshot/'draft_content.json'):shutil.copyfile(encrypted,target)
    shutil.copyfile(encrypted_meta,stage/'draft_meta_info.json')
    project=read(stage/'Timelines/project.json');project['id']=str(uuid.uuid4()).upper();project['update_time']=int(time.time()*1e6)
    write(stage/'Timelines/project.json',project)
    if (stage/'Timelines/project.json.bak').exists():write(stage/'Timelines/project.json.bak',project)
    from PIL import Image
    image=Image.open(JOB/'审看/调色/01.png').convert('RGB')
    image.save(stage/'draft_cover.jpg',quality=95);image.save(stage/'Timelines'/tid/'draft_cover.jpg',quality=95)
    registry_before=ROOT.read_bytes();(JOB/'root_meta_info.before.json').write_bytes(registry_before)
    shutil.copytree(stage,DEST)
    # Let the editor's directory watcher register if present; never overwrite its other changes.
    for _ in range(5):
        raw=ROOT.read_bytes();root=json.loads(raw)
        matches=[e for e in root['all_draft_store'] if e.get('draft_name')==DEST.name]
        if matches:break
        time.sleep(.2)
    if not matches:
        source_entry=next(e for e in root['all_draft_store'] if e['draft_id']==old_id)
        entry=deepcopy(source_entry);entry.update(draft_name=DEST.name,draft_id=new_id,draft_fold_path=DEST.as_posix(),
            draft_json_file=(DEST/'draft_content.json').as_posix(),draft_cover=(DEST/'draft_cover.jpg').as_posix(),
            tm_duration=60_000_000,tm_draft_create=meta['tm_draft_create'],tm_draft_modified=meta['tm_draft_modified'])
        root['all_draft_store'].insert(0,entry)
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',delete=False,dir=ROOT.parent,prefix='codex-v02-',suffix='.tmp') as stream:
            json.dump(root,stream,ensure_ascii=False,separators=(',',':'));stream.flush();os.fsync(stream.fileno());temporary=Path(stream.name)
        assert ROOT.read_bytes()==raw,'Registry changed; preserve pending copy'
        os.replace(temporary,ROOT)
    else:
        assert len(matches)==1 and Path(matches[0]['draft_fold_path']).resolve()==DEST.resolve()
        entry=matches[0]
    # Align the new copy only if the editor assigned its own distinct registration ID.
    if entry['draft_id']!=meta['draft_id']:
        assert not (DEST/'.locked').exists(),'New copy was opened during publication'
        meta['draft_id']=entry['draft_id'];write(meta_json,meta)
        encrypt_draft_file(meta_json,encrypted_meta,jy_install_dir=INSTALL,timeout=45)
        pending=DEST/('meta-'+uuid.uuid4().hex+'.tmp');shutil.copyfile(encrypted_meta,pending);os.replace(pending,DEST/'draft_meta_info.json')
    verify_a=JOB/'草稿解读/actual_content.verify.json';verify_b=JOB/'草稿解读/actual_meta.verify.json'
    decrypt_draft_file(DEST/'draft_content.json',verify_a,jy_install_dir=INSTALL,timeout=45)
    decrypt_draft_file(DEST/'draft_meta_info.json',verify_b,jy_install_dir=INSTALL,timeout=45)
    assert read(verify_a)==content
    actual_meta=read(verify_b)
    current=read(ROOT);registered=[e for e in current['all_draft_store'] if e.get('draft_name')==DEST.name]
    assert len(registered)==1 and registered[0]['draft_id']==actual_meta['draft_id']
    assert actual_meta['tm_duration']==60_000_000
    for filename in ('draft_content.json','draft_meta_info.json'):
        assert sha(SOURCE/filename)==sha(snapshot/filename)
    receipt={'draft':str(DEST),'draft_id':actual_meta['draft_id'],'duration_seconds':60,
        'track_count':len(content['tracks']),'segment_count':sum(len(t.get('segments',[])) for t in content['tracks']),
        'graded_visible_segments':len(shots),'derived_files':len(records),
        'within_first_minute':'cuts, speeds, transforms and audio preserved; intersecting final segments trimmed at 60s',
        'source_copy_and_v01':'not overwritten','encrypted_roundtrip':'passed','registry_binding':'passed',
        'content_sha256':sha(DEST/'draft_content.json'),'meta_sha256':sha(DEST/'draft_meta_info.json'),
        'native_gui_playback':'not performed','scope':'Only the first minute; later grading waits for user feedback'}
    write(JOB/'调色交付回执.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
