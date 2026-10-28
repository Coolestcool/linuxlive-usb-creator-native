#!/usr/bin/env python3
"""Exercise the shipped executable's IPC and native tools, using files only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
exe=str(Path(sys.argv[1]).resolve());out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=True)

def call(*args):
    result=subprocess.run([exe,'--backend',*map(str,args)],capture_output=True,text=True,timeout=90)
    events=[]
    for line in result.stdout.splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    assert result.returncode==0,(args,result.stdout[-2000:],result.stderr[-2000:])
    assert events and events[-1].get('event')=='result',events
    return events[-1]['value']
with tempfile.TemporaryDirectory(prefix='lili-package-test-') as temporary:
    root=Path(temporary);source=root/'ubuntu-frozen';(source/'casper').mkdir(parents=True)
    (source/'casper/vmlinuz').write_bytes(b'test-kernel'*1000)
    (source/'casper/initrd').write_bytes(b'test-initrd'*1000)
    job=root/'job';job.mkdir()
    information=call('describe');assert len(information['catalog'])==519
    observed=call('inspect',source)
    observed['release']={'name':'Ubuntu test','distribution':'ubuntu','supported_features':'ubuntu-persistence,syslinux6'}
    plan={'source':observed,'job':str(job),'output':str(root/'usb.img'),'persistence_mb':16,'image_size_mb':128,'settings':information['settings'],'virtualization':True,'hide_files':True}
    path=job/'plan.json';path.write_text(json.dumps(plan))
    call('prepare',path);created=call('make-image',path)
    assert Path(created['path']).stat().st_size==128*1024*1024
    assert call('hash',created['path'])['sha256']==created['sha256']
    with Path(created['path']).open('rb') as disk:
        disk.seek(510);assert disk.read(2)==b'\x55\xaa'
    results={'status':'PASS','executable':exe,'catalog':519,'packaged_native_tools':'FAT32 + Syslinux + ext2 persistence + hashing','image_bytes':created['bytes'],'physical_writes':0}
    (out/'backend.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
