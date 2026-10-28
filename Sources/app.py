# SPDX-License-Identifier: GPL-3.0-only
# LinuxLive USB Creator 2.9.4 visual/workflow adaptation.
# Original: Thibaut Lauziere (Slym), AutoIt; original images and coordinates retained.
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid
from PySide6.QtCore import Qt, QProcess, QTimer, QUrl, QSize
from PySide6.QtGui import QPainter, QFont, QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QComboBox, QSlider, QLineEdit, QCheckBox, QProgressBar, QFileDialog, QMessageBox, QInputDialog, QMenu, QMenuBar
from core import ROOT, RES, SUPPORT, settings
from graphics import VectorPicture, render_vector
from PySide6.QtSvg import QSvgRenderer


def launch_command():
    return [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(ROOT / "Sources/main.py")]


class Task(QProcess):
    def __init__(self, owner, args, done, progress=None, administrator=False):
        super().__init__(owner)
        self.buffer = b"";self.value = None;self.failure = None;self.done = done;self.progress = progress
        self.setProcessChannelMode(QProcess.MergedChannels)
        self.readyReadStandardOutput.connect(self.consume)
        self.finished.connect(self.complete)
        self.errorOccurred.connect(self.process_error)
        command = launch_command() + ["--backend"] + [str(a) for a in args]
        if administrator:
            if sys.platform == "darwin":
                shell = shlex.join(command).replace("\\", "\\\\").replace('"', '\\"')
                command = ["/usr/bin/osascript", "-e", 'do shell script "' + shell + '" with administrator privileges']
            else:
                command = ["/usr/bin/pkexec"] + command
        self.setProgram(command[0]);self.setArguments(command[1:]);self.start()

    def consume(self):
        self.buffer += bytes(self.readAllStandardOutput()).replace(b"\r", b"\n")
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if not line: continue
            try: event = json.loads(line)
            except (ValueError, UnicodeError):
                self.failure = line.decode("utf-8", "replace")[-1500:];continue
            if event.get("event") == "result": self.value = event.get("value")
            elif event.get("event") == "error": self.failure = event.get("message")
            elif event.get("event") == "progress" and self.progress: self.progress(event.get("fraction", 0), event.get("message", ""))

    def process_error(self, error):
        if error == QProcess.FailedToStart:
            callback, self.done = self.done, None
            if callback: callback(None, self.errorString())
            self.deleteLater()

    def complete(self, code, status):
        self.consume()
        callback, self.done = self.done, None
        if self.value is None and not self.failure:self.failure="The worker stopped before completing this operation (exit %s)." % code
        if callback: callback(self.value, self.failure if code != 0 or self.value is None else None)
        self.deleteLater()


class IconButton(QPushButton):
    def __init__(self, parent, name, rect, action, accessible):
        super().__init__(parent)
        self.normal = QIcon(str(RES / "img" / (name + ".svg")))
        self.hover = QIcon(str(RES / "img" / (name + "_hover.svg")))
        if self.hover.isNull(): self.hover = self.normal
        self.setGeometry(*rect);self.setIcon(self.normal);self.setIconSize(QSize(rect[2], rect[3]))
        self.setStyleSheet("QPushButton {background:transparent;border:0;padding:0;} QPushButton:focus {border:1px dotted #aaa;}")
        self.setCursor(Qt.PointingHandCursor);self.setAccessibleName(accessible);self.setToolTip(accessible);self.clicked.connect(lambda checked=False: action())
    def enterEvent(self, event): self.setIcon(self.hover);super().enterEvent(event)
    def leaveEvent(self, event): self.setIcon(self.normal);super().leaveEvent(event)


class MainWindow(QWidget):
    def __init__(self, bootstrap=True):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(450, 750);self.setWindowTitle("LinuxLive USB Creator")
        self.setWindowIcon(QIcon(str(RES / "img/lili.svg")))
        self.background = QSvgRenderer(str(RES / "img/GUI.svg"),self);self.background_cache=None
        self.config = {};self.catalog = [];self.devices = [];self.source = None;self.info = {};self.translations = {}
        self.language = "English";self.busy = False;self.tasks = [];self.widgets = [];self.drag_origin = None;self.logs = []
        self.current_job = None;self.dialogs = [];self.last_virtual_image = None;self.disks_loading=False
        self.device_timer=QTimer(self);self.device_timer.setInterval(5000);self.device_timer.timeout.connect(self.refresh_disks)
        self.pending_volume = sys.argv[sys.argv.index("--launch-volume")+1] if "--launch-volume" in sys.argv and len(sys.argv)>sys.argv.index("--launch-volume")+1 else None
        self.setAcceptDrops(True);self.render()
        self.setContextMenuPolicy(Qt.CustomContextMenu);self.customContextMenuRequested.connect(self.context_menu)
        if bootstrap:QTimer.singleShot(0,self.bootstrap);self.device_timer.start()

    def paintEvent(self, event):
        key=(self.width(),self.height(),self.devicePixelRatioF())
        if self.background_cache is None or self.background_cache[0]!=key:self.background_cache=(key,render_vector(self.background,*key))
        painter = QPainter(self);painter.drawPixmap(0,0,self.background_cache[1])
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_origin is not None: self.move(event.globalPosition().toPoint() - self.drag_origin)
    def mouseReleaseEvent(self, event): self.drag_origin = None
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        if event.mimeData().urls(): self.inspect(event.mimeData().urls()[0].toLocalFile())
    def closeEvent(self, event):
        if self.busy: self.error(self.tr("An operation is in progress. Wait for it to finish."));event.ignore()
        else: event.accept()
    def tr(self, text): return self.translations.get(text.lower(), text)
    def task(self, args, done, progress=None, administrator=False):
        task = Task(self, args, done, progress, administrator);self.tasks.append(task)
        task.destroyed.connect(lambda: self.tasks.remove(task) if task in self.tasks else None)
        return task
    def bootstrap(self):
        def loaded(data, error):
            if error: self.error(error);return
            self.info = data;self.config = data["settings"];self.catalog = data["catalog"]
            self.load_language();self.refresh_disks()
            if self.pending_volume:
                volume,self.pending_volume=self.pending_volume,None
                QTimer.singleShot(0,lambda:self.launch_volume(volume))
        self.task(["describe"], loaded)
    def load_language(self):
        language = self.config.get("General", {}).get("force_lang", "")
        if not language or language == "Automatic":
            from PySide6.QtCore import QLocale
            language = {"es":"Spanish","fr":"French","de":"German","it":"Italian","pt":"Portuguese (Brazilian)","ja":"Japanese","zh":"Chinese","ru":"Russian","ko":"Korean","nl":"Dutch","tr":"Turkish","pl":"Polish","uk":"Ukrainian"}.get(QLocale.system().name()[:2], "English")
        self.language = language
        def loaded(data, error): self.translations = data or {};self.render()
        self.task(["translate", language], loaded)
    def label(self, text, rect, size=11, bold=False):
        widget = QLabel(text, self);widget.setGeometry(*rect);widget.setFont(QFont("Tahoma", size));widget.setWordWrap(True)
        widget.setStyleSheet("color:white;background:transparent;" + ("font-weight:bold;" if bold else ""));self.widgets.append(widget);return widget
    def icon(self, name, rect, action, title):
        widget = IconButton(self, name, rect, action, title);self.widgets.append(widget);return widget
    def picture(self, name, rect):
        widget = VectorPicture(self,(RES / "img" / name).with_suffix(".svg"),rect);self.widgets.append(widget);return widget
    def checkbox(self, text, y, checked, callback):
        box = QCheckBox(text,self);box.setGeometry(67,y,300,42 if y == 558 else 25);box.setChecked(checked);box.setFont(QFont("Tahoma",8))
        box.setStyleSheet('QCheckBox{color:white;background:transparent;} QCheckBox::indicator{width:13px;height:13px;} QCheckBox::indicator:checked{image:url("'+str(RES/'img/checked.svg')+'");} QCheckBox::indicator:unchecked{image:url("'+str(RES/'img/unchecked.svg')+'");}')
        box.stateChanged.connect(callback);self.widgets.append(box);return box
    def render(self):
        selection = self.drive.currentIndex() if hasattr(self,"drive") else 0
        persistence = self.slider.value() if hasattr(self,"slider") else 0
        formatted = self.format.isChecked() if hasattr(self,"format") else False
        for widget in self.widgets: widget.deleteLater()
        self.widgets = [];self.step_icons = [];self.source_controls = []
        self.icon("close",(362,22,20,20),self.close,self.tr("Close"));self.icon("min",(332,22,20,20),self.showMinimized,self.tr("Minimize"))
        for step,title,y in [(1,"STEP 1 : CHOOSE YOUR KEY",150),(2,"STEP 2 : CHOOSE A SOURCE",246),(3,"STEP 3 : PERSISTENCE",386),(4,"STEP 4 : OPTIONS",496),(5,"STEP 5 : CREATE",608)]:
            self.label(self.tr(title),(55,y,312,25),10)
            if step < 5: self.icon("help",(362,y-3,20,20),lambda checked=False,n=step:self.help(n),self.tr("Help"))
        self.drive = QComboBox(self);self.drive.setGeometry(117,187,200,22);self.drive.setFont(QFont("Tahoma",8));self.widgets.append(self.drive)
        self.drive.addItem("→ " + self.tr("Choose a USB Key"))
        for disk in self.devices: self.drive.addItem("%s · %.1f GB (%s)" % (disk["name"],disk["size"]/1073741824,disk["id"]))
        self.drive.setCurrentIndex(min(selection,len(self.devices)));self.drive.currentIndexChanged.connect(self.disk_changed)
        self.icon("refresh",(327,187,20,20),self.refresh_disks,self.tr("Refresh"))
        self.step_icons.append(self.picture("bad.png",(365,192,25,40)))
        self.source_controls += [self.icon("iso",(65,273,75,75),lambda:self.choose_source(False),"ISO / IMG / ZIP"),self.icon("cd",(173,273,75,75),lambda:self.choose_source(True),"CD"),self.icon("download",(287,272,75,75),self.download_menu,self.tr("Download"))]
        self.source_controls += [self.label("ISO / IMG / ZIP",(67,344,110,20),8),self.label("CD",(202,344,40,20),8),self.label(self.tr("Download"),(289,344,75,20),8)]
        self.source_title = self.label("",(95,280,248,40),9);self.source_detail = self.label("",(95,322,248,46),8)
        self.back = self.icon("back",(62,278,20,20),self.clear_source,self.tr("Back"))
        self.step_icons.append(self.picture("bad.png",(365,329,25,40)))
        self.live = self.label(self.tr("Live Mode"),(82,424,280,38),16);self.live.setAlignment(Qt.AlignCenter)
        minimum = self.label("0 MB",(117,420,40,20),8);self.maximum = self.label("4095 MB",(337,420,60,20),8)
        self.slider = QSlider(Qt.Horizontal,self);self.slider.setGeometry(147,417,180,20);self.slider.setRange(0,4095);self.slider.setValue(persistence);self.slider.valueChanged.connect(self.slider_changed);self.widgets.append(self.slider)
        self.amount = QLineEdit(str(persistence),self);self.amount.setGeometry(177,447,48,21);self.amount.editingFinished.connect(self.amount_changed);self.widgets.append(self.amount)
        self.persistence_controls = [minimum,self.maximum,self.slider,self.amount,self.label("MB",(231,450,25,20),8),self.label(self.tr("(Live mode only)"),(247,450,110,20),8)]
        self.step_icons.append(self.picture("bad.png",(365,440,25,40)))
        self.hide = self.checkbox(self.tr("Hide created files on key"),520,self.config.get("Last_State",{}).get("hide_files","yes") == "yes",self.save_last_state)
        self.format = self.checkbox(self.tr("Format the key in FAT32 (this will erase your data !!)"),540,formatted,lambda:None)
        virtual_text = self.tr("Enable launching LinuxLive") + (" in macOS" if sys.platform == "darwin" else " in Linux")
        self.virtual = self.checkbox(virtual_text,558,self.config.get("Last_State",{}).get("virtualization","yes") == "yes",self.save_last_state)
        self.options_button = QPushButton(self.tr("Options").upper(),self);self.options_button.setGeometry(275,606,100,22);self.options_button.clicked.connect(self.open_options);self.widgets.append(self.options_button)
        self.launch_button = self.icon("launch",(62,642,22,43),self.launch,self.tr("Create"))
        self.status = self.label("← " + self.tr("Click the lightning icon to start the installation"),(87,647,295,54),9,True)
        self.progress = QProgressBar(self);self.progress.setGeometry(87,704,290,10);self.progress.setRange(0,1000);self.progress.setTextVisible(False);self.widgets.append(self.progress)
        for widget in self.widgets: widget.show()
        self.update_source();self.update_persistence();self.disk_changed();self.progress.setVisible(self.busy)
        self.make_menu()
    def selected_disk(self):
        n = self.drive.currentIndex()-1
        return self.devices[n] if n in range(len(self.devices)) else None
    def step(self, number, state): self.step_icons[number-1].set_asset(RES / "img" / (state+".svg"))
    def disk_changed(self,*args): self.step(1,"good" if self.selected_disk() else "bad");self.update_persistence()
    def refresh_disks(self):
        if self.busy or self.disks_loading:return
        self.disks_loading=True
        def loaded(data,error):
            self.disks_loading=False
            if self.busy:return
            rows=data or []
            selected=self.selected_disk()
            if rows!=self.devices:
                self.devices=rows;self.render()
                index=next((i+1 for i,disk in enumerate(rows) if selected and disk["id"]==selected["id"] and disk["identity"]==selected["identity"]),0)
                self.drive.setCurrentIndex(index)
            if error:self.status.setText(error)
        self.task(["disks"],loaded)
    def choose_source(self,folder=False):
        if self.busy:return
        if folder:path = QFileDialog.getExistingDirectory(self,self.tr("Please choose a CD"),"/Volumes" if sys.platform == "darwin" else "/media")
        else:path,_ = QFileDialog.getOpenFileName(self,self.tr("Please choose an ISO image of LinuxLive CD"),str(Path.home()),"ISO / IMG / ZIP (*.iso *.img *.zip *.raw *.bin)")
        if path:self.inspect(path)
    def inspect(self,path):
        if self.busy:return
        self.set_busy(True,"Checking source integrity")
        def loaded(data,error):
            self.set_busy(False)
            if error:self.error(error);return
            self.source = data;self.update_source();self.update_persistence()
            if data.get("release",{}).get("hash_mismatch"):self.error("The filename matches the catalog but its MD5 differs. Verify the source or select a different preset in Options.")
        self.task(["inspect",path],loaded,self.report_progress)
    def clear_source(self):self.source = None;self.update_source();self.update_persistence()
    def update_source(self):
        chosen = self.source is not None
        for widget in self.source_controls:widget.setVisible(not chosen)
        for widget in [self.source_title,self.source_detail,self.back]:widget.setVisible(chosen)
        if chosen:
            self.source_title.setText(self.source["name"]);r=self.source.get("release",{});self.source_detail.setText(r.get("name","LinuxLive")+"\n"+(self.source.get("raw_reason") or r.get("recognition","")))
        self.step(2,"warning" if chosen and self.source.get("release",{}).get("recognition") not in ("MD5 verified","SHA256 verified") else "good" if chosen else "bad")
    def update_persistence(self):
        raw=(self.source or {}).get("mode")=="img"
        self.format.setEnabled(not raw and not self.busy)
        if raw:self.format.setChecked(False)
        release=(self.source or {}).get("release",{});enabled="persistence" in release.get("supported_features","") and (self.source or {}).get("mode") != "img"
        limit=4095
        if self.selected_disk() and self.source:limit=max(0,min(limit,int((self.selected_disk()["size"]-self.source.get("install_bytes",self.source.get("bytes",0)))/1048576)-128))
        self.slider.setMaximum(limit);self.maximum.setText(str(limit)+" MB")
        for widget in self.persistence_controls:widget.setVisible(enabled)
        self.live.setVisible(not enabled)
        if not enabled:self.slider.setValue(0)
        self.amount.setText(str(self.slider.value()));self.step(3,"good" if self.source else "bad")
    def slider_changed(self,value):self.amount.setText(str(value))
    def amount_changed(self):
        try:self.slider.setValue(max(0,min(self.slider.maximum(),int(self.amount.text()))))
        except ValueError:self.amount.setText(str(self.slider.value()))
    def set_busy(self,busy,message=""):
        self.busy=busy;self.progress.setVisible(busy);self.launch_button.setEnabled(not busy);self.options_button.setEnabled(not busy)
        if message:self.status.setText(self.tr(message))
    def report_progress(self,fraction,message):self.progress.setValue(int(max(0,min(1,fraction))*1000));self.status.setText(self.tr(message))
    def error(self,message):self.logs.append(str(message));self.status.setText(str(message));QMessageBox.warning(self,self.tr("Please read"),str(message))
    def write_json(self,path,data):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2,ensure_ascii=False));path.chmod(0o600);return path
    def save_config(self,callback=None):
        path=self.write_json(SUPPORT/"settings-to-save.json",self.config)
        def done(data,error):
            if error:self.error(error)
            if callback:callback()
        self.task(["save-settings",path],done)
    def save_last_state(self,*args):
        self.config.setdefault("Last_State",{}).update(hide_files="yes" if self.hide.isChecked() else "no",virtualization="yes" if self.virtual.isChecked() else "no");self.save_config()
    def launch(self,output=None):
        if self.busy:return
        if not self.source:self.error(self.tr("Please choose an ISO image of LinuxLive CD"));return
        disk=self.selected_disk()
        if output is None and not disk:self.error(self.tr("Choose a USB Key"));return
        if output is None:
            destructive=self.format.isChecked() or self.source["mode"]=="img"
            message="%s · %s\n%s\nType %s to confirm." % (disk["name"],disk["id"],"All data on this device will be erased." if destructive else "Existing LinuxLive files will be replaced. Other files will be kept.",disk["id"])
            answer,ok=QInputDialog.getText(self,self.tr("Please read"),message)
            if not ok or answer != disk["id"]:return
        job=SUPPORT/"Jobs"/str(uuid.uuid4());job.mkdir(parents=True)
        plan=dict(job=str(job),source=self.source,persistence_mb=self.slider.value(),settings=self.config,format=self.format.isChecked(),hide_files=self.hide.isChecked(),virtualization=self.virtual.isChecked(),uid=os.getuid(),gid=os.getgid())
        if output is not None:plan["output"]=str(output)
        else:plan["disk"]=disk
        path=self.write_json(job/"plan.json",plan);self.current_job=path;self.set_busy(True,"Preparing source")
        def prepared(data,error):
            if error:self.set_busy(False);self.error(error);return
            command="make-image" if output is not None else "install"
            if output is None:self.status.setText("Administrator authorization is required to write the selected USB.")
            def completed(result,error):
                self.set_busy(False)
                if error:self.error(error);return
                self.status.setText(self.tr("Your LinuxLive key is now up and ready"))
                self.logs.append(json.dumps(result));self.last_virtual_image=str(output) if output else None
            self.task([command,path],completed,self.report_progress,administrator=output is None)
        self.task(["prepare",path],prepared,self.report_progress)
    def create_image(self):
        path,_=QFileDialog.getSaveFileName(self,"Create LinuxLive disk image",str(Path.home()/"LinuxLive.img"),"Disk image (*.img)")
        if path:self.launch(path)
    def help(self,step=0):QDesktopServices.openUrl(QUrl.fromLocalFile(str((ROOT/"Source" if (ROOT/"Source").exists() else ROOT)/"USER_GUIDE.md")))
    def open_options(self):
        from options import OptionsDialog
        dialog=OptionsDialog(self);self.dialogs.append(dialog);dialog.show()
    def download_menu(self):
        from options import DownloadDialog
        dialog=DownloadDialog(self);self.dialogs.append(dialog);dialog.show()
    def hasher(self,kind):
        path,_=QFileDialog.getOpenFileName(self,kind.upper()+" Easy Hasher")
        if not path:return
        self.set_busy(True,"Checking source integrity")
        def done(data,error):
            self.set_busy(False)
            if error:self.error(error);return
            value=data[kind];box=QMessageBox(self);box.setWindowTitle(kind.upper()+" Easy Hasher");box.setText(Path(path).name+"\n\n"+value);copy=box.addButton("Copy",QMessageBox.ActionRole);box.addButton("OK",QMessageBox.AcceptRole);box.exec()
            if box.clickedButton() is copy:QApplication.clipboard().setText(value)
        self.task(["hash",path],done,self.report_progress)
    def launch_vm(self):
        path,_=QFileDialog.getOpenFileName(self,"Launch LinuxLive",str(Path.home()),"LinuxLive images (*.img *.iso *.raw)")
        if not path:return
        self.set_busy(True,"Preparing virtual machine")
        def done(data,error):
            self.set_busy(False)
            if error:self.error(error)
            else:self.logs.append(json.dumps(data))
        self.task(["virtualize",path],done,self.report_progress)
    def launch_volume(self,volume):
        def found(disk,error):
            if error:self.error(error);return
            reply=QMessageBox.question(self,"LinuxLive", "%s (%s) will be unmounted while Linux runs. Close any files you have open on this USB. Continue?" % (disk["name"],disk["id"]))
            if reply!=QMessageBox.Yes:return
            job=SUPPORT/"Jobs"/str(uuid.uuid4());job.mkdir(parents=True)
            path=self.write_json(job/"plan.json",dict(job=str(job),disk=disk,uid=os.getuid(),gid=os.getgid(),home=str(Path.home()),memory_mb=1024,environment={key:os.environ[key] for key in ("DISPLAY","XAUTHORITY","XDG_RUNTIME_DIR","WAYLAND_DISPLAY","DBUS_SESSION_BUS_ADDRESS") if key in os.environ}))
            self.set_busy(True,"LinuxLive USB virtual machine")
            def done(data,error):
                self.set_busy(False)
                if error:self.error(error)
                else:self.status.setText("LinuxLive session finished.")
            self.task(["virtualize-usb",path],done,administrator=True)
        self.task(["volume",volume],found)
    def export_logs(self):
        path,_=QFileDialog.getSaveFileName(self,"Export logs","LinuxLive.log")
        if path:Path(path).write_text("\n".join(self.logs))
    def open_repository(self):QDesktopServices.openUrl(QUrl("https://github.com/Coolestcool/linuxlive-usb-creator-native"))
    def about(self):
        box=QMessageBox(self);box.setWindowTitle("About LinuxLive USB Creator")
        box.setText("LinuxLive USB Creator · Native edition\nVersion 1.0 preview 4\nMaintained by Enrique · Coolestcool\nContact: enrique330@gmail.com\nOpen-source software · GNU GPL v3")
        notices=box.addButton("Licenses and notices",QMessageBox.ActionRole);box.addButton("Close",QMessageBox.RejectRole);box.exec()
        if box.clickedButton() is notices:self.legal_notices()
    def legal_notices(self):
        box=QMessageBox(self);box.setWindowTitle("Licenses and notices")
        box.setText("Native adaptation © 2026 Enrique (Coolestcool).\nBased on LinuxLive USB Creator 2.9.4 by Thibaut Lauzière (Slÿm). Original copyright and license notices are retained.\n\nGNU GPL version 3: you may use, modify and redistribute this software under its terms. This program comes with no warranty.\nDependency licenses and full corresponding sources are included.")
        license_button=box.addButton("Open license",QMessageBox.ActionRole);source_button=box.addButton("Source code",QMessageBox.ActionRole);box.addButton("Close",QMessageBox.RejectRole);box.exec()
        if box.clickedButton() is license_button:QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT/"LICENSE")))
        elif box.clickedButton() is source_button:self.show_sources()
    def show_sources(self):QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT/"Source" if (ROOT/"Source").exists() else ROOT)))
    def make_menu(self):
        if hasattr(self,"menu"):self.menu.deleteLater()
        self.menu=QMenuBar(self);self.menu.setNativeMenuBar(sys.platform=="darwin")
        if sys.platform!="darwin" or QApplication.platformName()=="offscreen":self.menu.hide()
        def group(title,entries):
            menu=self.menu.addMenu(title)
            for text,callback in entries:menu.addAction(text,callback)
        group("LinuxLive USB Creator",[("About",self.about),(self.tr("Options")+"…",self.open_options),("Quit",self.close)])
        group("File",[("ISO / IMG / ZIP…",lambda:self.choose_source(False)),("CD / folder…",lambda:self.choose_source(True)),("Download…",self.download_menu),("Create disk image…",self.create_image),("Launch LinuxLive…",self.launch_vm),("Export logs…",self.export_logs)])
        group("Bonus",[("CRC32 Easy Hasher…",lambda:self.hasher("crc32")),("MD5 Easy Hasher…",lambda:self.hasher("md5")),("SHA1 Easy Hasher…",lambda:self.hasher("sha1"))])
        group("Help",[("User guide",self.help),("Licenses and notices",self.legal_notices),("Source code",self.show_sources)])
    def context_menu(self,position):
        menu=QMenu(self)
        for item in self.menu.actions():
            if item.menu():menu.addMenu(item.menu())
        menu.exec(self.mapToGlobal(position))


def main():
    if settings().get("Advanced",{}).get("graphical_safe_mode")=="yes":QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
    application=QApplication(sys.argv);application.setStyle("Fusion");application.setApplicationName("LinuxLive USB Creator");application.setOrganizationName("LiLi Mac Linux Port")
    from scaling import apply_scale
    apply_scale(application,settings(),launch_command()+sys.argv[1:])
    application.setFont(QFont("Tahoma",9))
    window=MainWindow();window.show()
    screen=window.screen().availableGeometry();window.move(screen.center()-window.rect().center())
    sys.exit(application.exec())
