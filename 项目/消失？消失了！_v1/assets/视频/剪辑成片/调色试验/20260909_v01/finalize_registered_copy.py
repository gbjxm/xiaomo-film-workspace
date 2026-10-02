"""Reconcile only this new test copy with an editor-created registry entry."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

JOB=Path(__file__).resolve().parent
DEST=Path(r'D:\JianyingPro Drafts\消失？消失了！-副本-调色v01')
SOURCE=Path(r'D:\JianyingPro Drafts\消失？消失了！-副本')
ROOT=Path(os.environ['LOCALAPPDATA'])/'JianyingPro/User Data/Projects/com.lveditor.draft/root_meta_info.json'
sys.path.insert(0,r'D:\codex\tools\jianying-color-lab\helpers')
from aoguai_draft_crypto import encrypt_draft_file,decrypt_draft_file


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


root_before=ROOT.read_bytes();root=json.loads(root_before)
entries=[e for e in root['all_draft_store'] if e.get('draft_name')==DEST.name]
assert len(entries)==1
entry=entries[0]
assert Path(entry['draft_fold_path']).resolve()==DEST.resolve()
content=read(JOB/'草稿解读/actual_copy_content.json')
planned=read(JOB/'草稿解读/graded_content.json')
assert content==planned
oldmeta=read(JOB/'草稿解读/actual_copy_meta.json')
meta=deepcopy(oldmeta)
meta['draft_id']=entry['draft_id']
for key in ('draft_name','draft_fold_path','draft_root_path'):
    if key in entry:meta[key]=entry[key]
meta_file=JOB/'草稿解读/registered_copy_meta.json';write(meta_file,meta)
encoded=JOB/'草稿解读/registered_copy_meta.enc.json'
before_hash=sha(DEST/'draft_meta_info.json')
encrypt_draft_file(meta_file,encoded,jy_install_dir=r'D:\JianyingPro\11.3.0.14362',timeout=45)
assert ROOT.read_bytes()==root_before,'Registry changed again; preserve current files'
assert not (DEST/'.locked').exists(),'The new copy is open; do not write its metadata'
assert sha(DEST/'draft_meta_info.json')==before_hash,'Metadata changed'
shutil.copyfile(DEST/'draft_meta_info.json',JOB/'草稿解读/metadata-before-registry-alignment.enc.json')
temporary=DEST/('draft_meta_info.'+uuid.uuid4().hex+'.tmp')
shutil.copyfile(encoded,temporary)
os.replace(temporary,DEST/'draft_meta_info.json')
verified=JOB/'草稿解读/registered_copy_meta.verify.json'
decrypt_draft_file(DEST/'draft_meta_info.json',verified,jy_install_dir=r'D:\JianyingPro\11.3.0.14362',timeout=45)
assert read(verified)['draft_id']==entry['draft_id']
assert ROOT.read_bytes()==root_before,'Registry changed after alignment'
original=read(JOB/'草稿解读/draft_content.dec.json')
assert content['tracks']==original['tracks']
restored=deepcopy(content)
by_id={m['id']:m['path'] for m in original['materials']['videos']}
for material in restored['materials']['videos']:material['path']=by_id[material['id']]
assert restored==original
for name in ('draft_content.json','draft_meta_info.json'):
    assert sha(SOURCE/name)==sha(JOB/'原草稿快照'/name),'Original copy changed'
records=read(JOB/'派生链.json')
prior_root=read(JOB/'root_meta_info.before.json')
other_entries=[e for e in root['all_draft_store'] if e.get('draft_name')!=DEST.name]
receipt={'draft':str(DEST),'new_draft_id':entry['draft_id'],'timeline_id_preserved':content['id'],
    'duration_us':content['duration'],'track_count':len(content['tracks']),
    'segment_count':sum(len(t.get('segments',[])) for t in content['tracks']),
    'graded_segments':33,'derivative_files':len(records),'source_copy':'unchanged',
    'editorial_structure':'exact match','audio_tracks':'exact match','hidden_tracks':'exact match',
    'encryption_roundtrip':'passed','registry_id_alignment':'passed',
    'registry_other_entries_unchanged':other_entries==prior_root['all_draft_store'],
    'registry_current_sha256':sha(ROOT),'content_sha256':sha(DEST/'draft_content.json'),
    'metadata_sha256':sha(DEST/'draft_meta_info.json'),
    'pixel_method':'graded full-length source derivatives, original source files retained',
    'native_gui_playback':'not performed','status':'first grade candidate ready for user review'}
write(JOB/'调色交付回执.json',receipt)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
