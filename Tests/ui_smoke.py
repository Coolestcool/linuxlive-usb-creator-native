#!/usr/bin/env python3
"""Render/test our own Qt widgets without driving the user's desktop."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
WORKSPACE=ROOT.parents[1] if len(ROOT.parents)>1 else ROOT.parent
OUT=Path(os.environ.get("LILI_TEST_OUT",WORKSPACE/"work/lili-mac/validation/ui"))
OUT.mkdir(parents=True,exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
os.environ["LILI_SUPPORT"]=str(OUT/"private-settings")
sys.path[:0]=[str(ROOT/"Sources"),str(ROOT/"Backend")]
from PySide6.QtWidgets import QApplication, QTabWidget, QPushButton
from PySide6.QtCore import Qt,QEvent
from PySide6.QtTest import QTest
from app import MainWindow
from options import OptionsDialog, DownloadDialog
from core import settings,translations
from lili import describe

application=QApplication([]);application.setStyle("Fusion")
window=MainWindow(bootstrap=False);window.info=describe();window.config=settings();window.catalog=window.info["catalog"];window.render();window.show();application.processEvents()
assert (window.width(),window.height())==(450,750)
assert len(window.catalog)==519
from scaling import choose_scale
assert choose_scale("auto",2880,1590)==1.5
assert choose_scale("2.0",1280,900)==1.0
assert choose_scale("1.25",1920,1080)==1.25
assert window.drive.geometry().getRect()==(117,187,200,22)
assert window.launch_button.geometry().getRect()==(62,642,22,43)
assert all(icon.width()==25 and icon.height()==40 for icon in window.step_icons)
errors=[];window.error=lambda message:errors.append(message)
QTest.mouseClick(window.launch_button,Qt.LeftButton)
assert errors and "ISO" in errors[-1]
# Refresh must never silently retarget a different physical device.
original_task=window.task
usb_a={"id":"fixture-a","name":"Fixture A","size":64*1024**3,"identity":{"key":"a"}}
usb_b={"id":"fixture-b","name":"Fixture B","size":512*1024**3,"identity":{"key":"b"}}
def inventory(rows):
    window.task=lambda args,done,*a,**kw:done(rows,None)
    window.refresh_disks()
inventory([usb_a,usb_b]);window.drive.setCurrentIndex(2)
inventory([usb_a]);assert window.selected_disk() is None
inventory([usb_a,usb_b]);window.drive.setCurrentIndex(1)
inventory([usb_b,usb_a]);assert window.selected_disk()["id"]=="fixture-a"
control=window.drive;inventory([usb_b,usb_a]);assert window.drive is control
window.task=original_task;window.devices=[];window.render();application.processEvents()
window.grab().save(str(OUT/"01-original-window.png"))
dialog=OptionsDialog(window);dialog.show();application.processEvents()
tabs=dialog.findChild(QTabWidget);assert tabs.count()==6
assert not any("donat" in w.text().lower() or "contact me" in w.text().lower() for w in dialog.findChildren(QPushButton))
assert dialog.preset.itemText(0).startswith("Ubuntu ")
dialog.recognition.setCurrentIndex(1);assert not dialog.preset.isEnabled()
dialog.recognition.setCurrentIndex(2);assert dialog.preset.isEnabled()
assert set(dialog.fields)=={"proxy_url","proxy_port","proxy_username","proxy_password"}
for n in range(6):
    tabs.setCurrentIndex(n);application.processEvents();dialog.grab().save(str(OUT/("02-options-"+str(n)+".png")))
assert len([key for key in dialog.flags if key[0]=="Advanced"])==len(window.config["Advanced"])
dialog.close()
download=DownloadDialog(window);download.show();application.processEvents();assert download.combo.count()==len(window.info["current_releases"]["rows"])
assert download.combo.count()>=3
assert any(download.combo.itemText(i).startswith("Ubuntu ") for i in range(download.combo.count()))
download.legacy.setChecked(True);assert download.combo.count()==519
download.legacy.setChecked(False)
download.grab().save(str(OUT/"03-download.png"));download.close()
window.translations=translations("Spanish");window.language="Spanish";window.render();application.processEvents()
assert any("PASO 1" in getattr(w,"text",lambda:"")() for w in window.widgets)
window.grab().save(str(OUT/"04-spanish.png"))
window.source={"name":"debian-live.iso","mode":"iso","bytes":1024,"release":{"name":"Debian Live","distribution":"debian","supported_features":"debian-persistence"}}
window.update_source();window.update_persistence();window.slider.setValue(512);application.processEvents()
assert window.amount.text()=="512" and window.slider.isVisible()
window.grab().save(str(OUT/"05-persistence.png"))
window.source={"name":"ubuntu-modern.iso","mode":"img","release":{}}
window.translations={};window.language="English"
window.update_source();window.update_persistence();application.processEvents()
assert not window.format.isEnabled() and window.format.isChecked()
assert "required for this image" in window.format.text()
assert "whole USB" in window.format.toolTip()
window.render();application.sendPostedEvents(None,QEvent.DeferredDelete);application.processEvents()
assert window.format.isChecked() and not window.format.isEnabled()
window.grab().save(str(OUT/"06-direct-image-options.png"))
window.clear_source();assert window.format.isEnabled() and not window.format.isChecked()
QTest.mouseClick(window.format,Qt.LeftButton);assert window.format.isChecked()
window.close();application.processEvents()
report={"status":"PASS","platform":sys.platform,"window":[450,750],"catalog":519,"tabs":6,"advanced_options":len(window.config["Advanced"]),"launch_without_source":"blocked via real button","spanish":"original translation loaded","persistence_slider":512,"source_image":"scalable SVG artwork, original logical layout"}
(OUT/"results.json").write_text(json.dumps(report,indent=2));print(json.dumps(report))
