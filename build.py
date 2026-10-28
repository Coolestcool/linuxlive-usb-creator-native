#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build the same Qt application on each target OS; never cross-freeze binaries."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import struct
import plistlib
import sys

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--native-tools',type=Path,default=ROOT/'NativeTools')
args=parser.parse_args()
out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
os.environ['PYINSTALLER_CONFIG_DIR']=str(out/'cache')
stage=out/'bundle-data';stage.mkdir(exist_ok=True)
source=stage/'Source'
if source.exists():shutil.rmtree(source)
source.mkdir()
for name in ['Backend','Sources','Tests','Original','NativeSources','Licenses','LICENSE','build.py','build_native.py','README.md','NOTICE','USER_GUIDE.md','requirements-macos-lock.txt','requirements-linux-lock.txt']:
    path=ROOT/name
    if path.is_dir():shutil.copytree(path,source/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    elif path.exists():shutil.copy2(path,source/name)
command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--name','LinuxLive USB Creator','--distpath',str(out/'dist'),'--workpath',str(out/'pyinstaller'),'--specpath',str(out),'--paths',str(ROOT/'Backend'),'--paths',str(ROOT/'Sources'),'--exclude-module','tkinter','--exclude-module','PySide6.QtNetwork','--exclude-module','PySide6.QtQml','--exclude-module','PySide6.QtQuick']
for src,dest in [(ROOT/'Resources','Resources'),(ROOT/'Original','Original'),(args.native_tools,'NativeTools'),(source,'Source'),(ROOT/'LICENSE','.')]:
    command+=['--add-data',str(src)+os.pathsep+dest]
if sys.platform=='darwin':
    # A single bundled executable also handles JSON backend IPC.
    iconset=out/'lili.iconset';iconset.mkdir(exist_ok=True)
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import Qt
    original=QSvgRenderer(str(ROOT/'Resources/img/lili.svg'))
    for size in [16,32,128,256,512]:
        for scale in [1,2]:
            pixels=QImage(size*scale,size*scale,QImage.Format_ARGB32_Premultiplied);pixels.fill(Qt.transparent)
            painter=QPainter(pixels);painter.setRenderHint(QPainter.Antialiasing);original.render(painter);painter.end()
            pixels.save(str(iconset/('icon_%sx%s%s.png'%(size,size,'@2x' if scale==2 else ''))))
    icon=out/'lili.icns'
    chunks=[]
    for kind,name in [(b'ic07','icon_128x128.png'),(b'ic08','icon_256x256.png'),(b'ic09','icon_512x512.png'),(b'ic10','icon_512x512@2x.png')]:
        data=(iconset/name).read_bytes();chunks.append(kind+struct.pack('>I',len(data)+8)+data)
    body=b''.join(chunks);icon.write_bytes(b'icns'+struct.pack('>I',len(body)+8)+body)
    command+=['--windowed','--osx-bundle-identifier','org.linuxliveusbcreator.port','--icon',str(icon)]
command.append(str(ROOT/'Sources/main.py'))
subprocess.run(command,check=True)

if sys.platform=='darwin':
    app=out/'dist/LinuxLive USB Creator.app'
    plist=app/'Contents/Info.plist'
    information=plistlib.loads(plist.read_bytes())
    information.update(CFBundleShortVersionString='1.0.0',CFBundleVersion='4',NSHighResolutionCapable=True,LSMinimumSystemVersion='26.0')
    plist.write_bytes(plistlib.dumps(information))
    subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(app)],check=True)
