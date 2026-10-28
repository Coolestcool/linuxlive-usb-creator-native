#!/usr/bin/env python3
"""Real Debian Live ISO boot/reboot acceptance, restricted to a new image file."""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'Backend'))
from core import settings
from creation import prepare,make_image
root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
observed=json.loads(Path(sys.argv[2]).read_text().splitlines()[-1])['value']
assert observed['hashes']['sha256']=='0e0a6ce1668475ca288061d73e5ce33e4483f562d9e49d9c092ec930a67c785d'
job=root/'job';job.mkdir(exist_ok=True)
output=root/'debian-persistent.img'
if not output.exists():
    plan={'source':observed,'job':str(job),'output':str(output),'persistence_mb':128,'image_size_mb':2200,'settings':settings(),'virtualization':False,'hide_files':False}
    plan=prepare(plan)
    menu=Path(plan['payload'])/plan['boot']['folder']/'syslinux.cfg'
    menu.write_text(menu.read_text().replace(' quiet',' console=ttyS0,115200n8 noeject'))
    make_image(plan)
qemu=shutil.which('qemu-system-x86_64') or '/usr/local/bin/qemu-system-x86_64'
for number in [1,2]:
    command=[qemu,'-m','1536','-smp','2','-display','none','-serial','stdio','-drive','file='+str(output)+',format=raw,if=virtio','-boot','c','-no-reboot','-nic','none']
    if sys.platform=='darwin':command+=['-accel','hvf','-cpu','host']
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    log=b'';recent=b'';state='login';deadline=time.monotonic()+180
    try:
        while time.monotonic()<deadline and process.poll() is None:
            for key,_ in selector.select(0.5):
                block=os.read(key.fileobj.fileno(),65536)
                if not block:break
                log+=block;recent=(recent+block)[-10000:]
                (root/('boot-%s.log'%number)).write_bytes(log)
                if state=='shutdown' and b'press ENTER' in recent:
                    process.stdin.write(b'\n');recent=b''
                elif state=='login' and b'login:' in recent:
                    process.stdin.write(b'user\n');state='password';recent=b''
                elif state=='password' and b'Password:' in recent:
                    process.stdin.write(b'live\n');state='shell';recent=b''
                elif state in ('password','shell') and (b'$ ' in recent or b'user@' in recent):
                    # Split the success literal so terminal input echo cannot satisfy the test.
                    if number==1:action="echo original-persistence-proof | sudo tee /var/lib/lili-proof >/dev/null; printf 'LILI_REAL_%s_PASS\\n' WRITE"
                    else:action="test \"$(cat /var/lib/lili-proof)\" = original-persistence-proof && printf 'LILI_REAL_%s_PASS\\n' REBOOT"
                    process.stdin.write((action+"; sudo sync; sudo poweroff\n").encode());state='shutdown';recent=b''
        code=process.wait(timeout=10)
        expected=b'LILI_REAL_WRITE_PASS' if number==1 else b'LILI_REAL_REBOOT_PASS'
        assert code==0 and expected in log,(number,code,log[-4000:].decode(errors='replace'))
    finally:
        if process.poll() is None:process.kill();process.wait()
        selector.close();process.stdout.close();process.stdin.close()
(root/'results.json').write_text(json.dumps({'status':'PASS','distribution':'Debian Live 12.15 standard amd64','sha256':observed['hashes']['sha256'],'boot':'BIOS/Syslinux','persistence':'128 MiB separate ext2 partition, / union; guest write survived reboot','physical_devices':0},indent=2))
print('REAL_DEBIAN_PERSISTENCE_PASS')
