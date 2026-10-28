#!/usr/bin/env python3
"""Boot the generated FAT/Syslinux disk twice, checking persisted guest writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'Backend'))
from core import settings
from creation import inspect_source,prepare,make_image
root=Path(os.environ.get('LILI_BOOT_OUT','/out/boot-validation'));root.mkdir(parents=True,exist_ok=True)
config=settings();config['Install_Parameters']={'automatic_recognition':'no'}
source=inspect_source('/out/boot-fixture',config,lambda *_:None)
source['release']={'name':'Ubuntu persistence boot fixture','distribution':'ubuntu','supported_features':'ubuntu-persistence,syslinux6'}
job=root/'job';job.mkdir(exist_ok=True)
output=root/'persistence-boot.img'
if output.exists():output.unlink()
plan={'source':source,'job':str(job),'output':str(output),'persistence_mb':32,'image_size_mb':192,'settings':config,'hide_files':False,'virtualization':False}
plan=prepare(plan,lambda *_:None)
# Console routing belongs to this test guest, not the distributed boot menu.
menu=Path(plan['payload'])/'syslinux/syslinux.cfg'
menu.write_text(menu.read_text().replace(' quiet',' console=ttyS0 panic=1'))
result=make_image(plan,lambda *_:None)
for number,expected in [(1,'LILI_FIRST_BOOT_WRITE_PASS'),(2,'LILI_SECOND_BOOT_PERSISTENCE_PASS')]:
    command=['qemu-system-x86_64','-m','768','-display','none','-serial','stdio','-drive','file='+str(output)+',format=raw,if=virtio','-boot','c','-no-reboot']
    try: test=subprocess.run(command,capture_output=True,timeout=90)
    except subprocess.TimeoutExpired as error:
        (root/('boot-%s-timeout.log'%number)).write_bytes((error.stdout or b'')+(error.stderr or b''));raise
    log=test.stdout.decode(errors='replace')+test.stderr.decode(errors='replace')
    (root/('boot-%s.log'%number)).write_text(log)
    assert test.returncode==0 and expected in log,log[-4000:]
result['boot_twice']='PASS';result['scope']='Synthetic guest using official Alpine kernel/modules; does not certify every distribution ISO.'
(root/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
