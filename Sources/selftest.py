# SPDX-License-Identifier: GPL-3.0-only
"""Read-only package acceptance test; writes screenshots only to the given folder."""
import json
import os
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QTabWidget
from app import MainWindow, launch_command

def run(destination, scale=False):
    output=Path(destination);output.mkdir(parents=True,exist_ok=True)
    application=QApplication([]);application.setStyle('Fusion')
    if scale:
        from scaling import apply_scale
        from core import settings
        apply_scale(application,settings(),launch_command()+sys.argv[1:])
    window=MainWindow();window.show()
    attempts=0
    def check():
        nonlocal attempts
        attempts+=1
        if not window.info or window.tasks:
            if attempts<100:QTimer.singleShot(200,check);return
            (output/'result.json').write_text(json.dumps({'status':'FAIL','logs':window.logs}))
            application.exit(1);return
        try:
            assert len(window.catalog)==519
            assert all(window.info['tools'].values()),window.info['tools']
            window.grab().save(str(output/'main.png'))
            from options import OptionsDialog
            options=OptionsDialog(window)
            assert options.findChild(QTabWidget).count()==6
            options.show();options.grab().save(str(output/'options.png'));options.close()
            (output/'result.json').write_text(json.dumps({'status':'PASS','catalog':len(window.catalog),'tools':window.info['tools'],'option_tabs':6,'physical_writes':0,'ui_scale':float(os.environ.get('QT_SCALE_FACTOR','1')),'logical_window':[window.width(),window.height()],'screenshot_pixels':[window.grab().width(),window.grab().height()],'current_release_count':len(window.info.get('current_releases',{}).get('rows',[]))},indent=2))
            application.exit(0)
        except Exception as error:
            (output/'result.json').write_text(json.dumps({'status':'FAIL','error':str(error)}));application.exit(1)
    QTimer.singleShot(200,check)
    return application.exec()
