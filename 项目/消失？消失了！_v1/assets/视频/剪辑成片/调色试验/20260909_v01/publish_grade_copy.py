"""Publish a NEW color-test copy while preserving the saved editorial structure."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

from PIL import Image

JOB = Path(__file__).resolve().parent
SOURCE = Path(r'D:\JianyingPro Drafts\消失？消失了！-副本')
DEST = SOURCE.parent / '消失？消失了！-副本-调色v01'
INSTALL = r'D:\JianyingPro\11.3.0.14362'
ROOT_META = Path(os.environ['LOCALAPPDATA']) / 'JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json'
sys.path.insert(0, r'D:\codex\tools\jianying-color-lab\helpers')
from aoguai_draft_crypto import decrypt_draft_file, encrypt_draft_file


def hash_file(path):
    with open(path,'rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')


def rebase(value):
    if isinstance(value,str):
        return value.replace(SOURCE.as_posix(),DEST.as_posix()).replace(str(SOURCE),str(DEST))
    if isinstance(value,list):return [rebase(v) for v in value]
    if isinstance(value,dict):return {k:rebase(v) for k,v in value.items()}
    return value


def main():
    if DEST.exists():raise FileExistsError(DEST)
    snapshot=JOB/'原草稿快照'
    for filename in ('draft_content.json','draft_meta_info.json'):
        assert hash_file(SOURCE/filename)==hash_file(snapshot/filename),'Source was saved again; rebase before publishing.'
    original=json.loads((JOB/'草稿解读/draft_content.dec.json').read_text(encoding='utf-8'))
    meta=json.loads((JOB/'草稿解读/draft_meta_info.dec.json').read_text(encoding='utf-8'))
    shots=json.loads((JOB/'shots.json').read_text(encoding='utf-8'))
    records=json.loads((JOB/'派生链.json').read_text(encoding='utf-8'))
    by_shot={number:record for record in records for number in record['shots']}
    content=deepcopy(original)
    materials={m['id']:m for m in content['materials']['videos']}
    changed=[]
    for shot in shots:
        record=by_shot[shot['number']]
        assert Path(record['output']).is_file()
        assert hash_file(record['output'])==record['output_sha256']
        material=materials[shot['material']['id']]
        assert material['path']==record['source']
        material['path']=Path(record['output']).as_posix()
        changed.append({'shot':shot['number'],'material_id':material['id'],'source':record['source'],'graded':material['path']})
    # Exact editorial equality: only used video material paths may differ.
    restored=deepcopy(content)
    originals={m['id']:m for m in original['materials']['videos']}
    for material in restored['materials']['videos']:material['path']=originals[material['id']]['path']
    assert restored==original,'Unexpected non-color edit'
    assert content['tracks']==original['tracks'],'Cuts, audio, transforms or visibility changed'
    assert content['materials'].get('audios')==original['materials'].get('audios')

    stage=JOB/'调色草稿待发布'
    if stage.exists():raise FileExistsError(stage)
    shutil.copytree(snapshot,stage)
    new_id=str(uuid.uuid4()).upper()
    meta=rebase(meta)
    meta.update(draft_name=DEST.name,draft_id=new_id,draft_fold_path=DEST.as_posix(),
                draft_root_path=DEST.parent.as_posix(),tm_draft_create=int(time.time()*1e6),tm_draft_modified=int(time.time()*1e6))
    # Add derived sources to the media bin without removing original materials.
    video_group=next(group for group in meta['draft_materials'] if group.get('type')==0)
    for record in records:
        template=next((item for item in video_group['value'] if item.get('file_Path')==record['source']),None)
        if template is None:
            template={'metetype':'video','type':0,'width':1470,'height':630,'duration':30066666,'item_source':1}
        item=deepcopy(template)
        item.update(id=str(uuid.uuid4()),file_Path=Path(record['output']).as_posix(),
                    extra_info=Path(record['source']).stem+' · 调色v01 · '+record['profile'],md5='')
        video_group['value'].append(item)
    content_path=JOB/'草稿解读/graded_content.json'
    meta_path=JOB/'草稿解读/graded_meta_info.json'
    write_json(content_path,content);write_json(meta_path,meta)
    encrypted_content=JOB/'草稿解读/graded_content.enc.json'
    encrypted_meta=JOB/'草稿解读/graded_meta_info.enc.json'
    encrypt_draft_file(content_path,encrypted_content,jy_install_dir=INSTALL,timeout=45)
    encrypt_draft_file(meta_path,encrypted_meta,jy_install_dir=INSTALL,timeout=45)
    timeline_id=content['id']
    mirrors=[stage/'draft_content.json',stage/'draft_content.json.bak',
             stage/'Timelines'/timeline_id/'draft_content.json',stage/'Timelines'/timeline_id/'draft_content.json.bak']
    for path in mirrors:shutil.copyfile(encrypted_content,path)
    # Replace exact matching recovery mirrors of this timeline, retaining other histories.
    old_hash=hash_file(snapshot/'draft_content.json')
    for path in stage.rglob('template-2.tmp'):
        if hash_file(path)==old_hash:shutil.copyfile(encrypted_content,path)
    shutil.copyfile(encrypted_meta,stage/'draft_meta_info.json')
    project_path=stage/'Timelines/project.json'
    project=json.loads(project_path.read_text(encoding='utf-8'))
    project['id']=str(uuid.uuid4()).upper()
    project['update_time']=int(time.time()*1e6)
    write_json(project_path,project)
    if (stage/'Timelines/project.json.bak').exists():write_json(stage/'Timelines/project.json.bak',project)
    cover=Image.open(JOB/'审看/调色/01.png').convert('RGB')
    cover.save(stage/'draft_cover.jpg',quality=95)
    cover.save(stage/'Timelines'/timeline_id/'draft_cover.jpg',quality=95)
    verify_content=JOB/'草稿解读/published_content.verify.json'
    verify_meta=JOB/'草稿解读/published_meta.verify.json'
    decrypt_draft_file(stage/'draft_content.json',verify_content,jy_install_dir=INSTALL,timeout=45)
    decrypt_draft_file(stage/'draft_meta_info.json',verify_meta,jy_install_dir=INSTALL,timeout=45)
    assert json.loads(verify_content.read_text(encoding='utf-8'))==content
    assert json.loads(verify_meta.read_text(encoding='utf-8'))==meta
    assert not (stage/'.locked').exists()

    # Register a distinct new copy; existing registry entries are untouched.
    root_before=ROOT_META.read_bytes()
    root=json.loads(root_before)
    source_entry=next(entry for entry in root['all_draft_store'] if entry['draft_id']==json.loads((JOB/'草稿解读/draft_meta_info.dec.json').read_text(encoding='utf-8'))['draft_id'])
    entry=rebase(deepcopy(source_entry))
    entry.update(draft_id=new_id,draft_name=DEST.name,draft_fold_path=DEST.as_posix(),
                 draft_json_file=(DEST/'draft_content.json').as_posix(),draft_cover=(DEST/'draft_cover.jpg').as_posix(),
                 tm_draft_create=meta['tm_draft_create'],tm_draft_modified=meta['tm_draft_modified'])
    assert not any(e.get('draft_name')==DEST.name or e.get('draft_id')==new_id for e in root['all_draft_store'])
    root['all_draft_store'].insert(0,entry)
    (JOB/'root_meta_info.before.json').write_bytes(root_before)
    for filename in ('draft_content.json','draft_meta_info.json'):
        assert hash_file(SOURCE/filename)==hash_file(snapshot/filename),'Source changed during publication preparation'
    assert ROOT_META.read_bytes()==root_before,'Registry changed; do not overwrite it'
    shutil.copytree(stage,DEST)
    assert ROOT_META.read_bytes()==root_before,'Registry changed; new copy is staged but not registered'
    temp=ROOT_META.with_name('root_meta_info.codex-color-v01.tmp')
    with temp.open('x',encoding='utf-8') as stream:
        json.dump(root,stream,ensure_ascii=False,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
    assert ROOT_META.read_bytes()==root_before,'Registry changed before atomic replacement'
    os.replace(temp,ROOT_META)
    saved_root=json.loads(ROOT_META.read_text(encoding='utf-8'))
    assert saved_root['all_draft_store'][1:]==json.loads(root_before)['all_draft_store']
    receipt={'draft':str(DEST),'new_draft_id':new_id,'timeline_id_preserved':timeline_id,
             'duration_us':content['duration'],'track_count':len(content['tracks']),
             'graded_segments':len(changed),'derivative_files':len(records),
             'editorial_structure':'exactly preserved','audio_tracks':'exactly preserved',
             'hidden_tracks':'exactly preserved','source_draft':'unchanged',
             'encryption_roundtrip':'passed','registry_old_entries':'unchanged; one new entry added',
             'root_meta_before_sha256':hashlib.sha256(root_before).hexdigest(),
             'root_meta_after_sha256':hash_file(ROOT_META),
             'draft_content_sha256':hash_file(DEST/'draft_content.json'),
             'draft_meta_sha256':hash_file(DEST/'draft_meta_info.json'),
             'pixel_method':'scene-specific grading baked into separate full-length source derivatives; original sources retained',
             'native_gui_playback':'not performed','changes':changed}
    write_json(JOB/'调色交付回执.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='changes'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
