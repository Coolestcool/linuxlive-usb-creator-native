# SPDX-License-Identifier: GPL-3.0-only
# Options_Menu.au3 and GUI_Actions.au3 cross-platform adapters.
from pathlib import Path
import json
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QTabWidget, QWidget, QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QScrollArea, QFileDialog, QMessageBox
from core import RES, SUPPORT
from graphics import VectorPicture


class OptionsDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main=main;self.tr=main.tr;self.setWindowTitle(self.tr("Options"));self.setFixedSize(401,436);self.setWindowModality(Qt.WindowModal)
        self.setStyleSheet("QDialog,QWidget{background:#f0f0f0;color:black;} QLineEdit,QComboBox{background:white;} QLabel{background:transparent;}")
        self.fields={};self.flags={}
        tabs=QTabWidget(self);tabs.setGeometry(8,8,385,393)
        def tab(name):
            view=QWidget();tabs.addTab(view,self.tr(name));return view
        general=tab("General")
        logo=VectorPicture(general,RES/"img/logo.svg",(12,12,344,107))
        self.label("Native edition · 1.0 preview 3",general,(40,135,300,26))
        self.label("Maintained by Enrique · Coolestcool",general,(35,165,310,24))
        self.button("Contact: enrique330@gmail.com",general,(35,194,310,24),lambda:QDesktopServices.openUrl(QUrl("mailto:enrique330@gmail.com")))
        self.label("Open-source software · GNU GPL v3",general,(25,222,325,20))
        self.label("Interface size (next launch)",general,(12,246,185,24))
        self.ui_scale=self.combo(["Automatic","100%","125%","150%","175%","200%"],general,(200,246,145,24))
        self.ui_scale.setCurrentIndex(["auto","1.0","1.25","1.5","1.75","2.0"].index(main.config.get("General",{}).get("ui_scale","auto")) if main.config.get("General",{}).get("ui_scale","auto") in ["auto","1.0","1.25","1.5","1.75","2.0"] else 0)
        self.button("Project on GitHub",general,(12,279,155,28),main.open_repository)
        self.button("Licenses and notices",general,(185,279,155,28),main.legal_notices)
        self.button("Source code and build instructions",general,(45,318,280,25),main.show_sources)
        install=tab("Options")
        self.label(self.tr("Install parameters"),install,(16,20,330,25))
        self.recognition=self.combo([self.tr("Use LiLi automatic recognition"),self.tr("Force using default mode (works with most Linuxes)"),self.tr("Force using same parameters as")],install,(16,62,330,26))
        options=main.config.get("Install_Parameters",{})
        self.recognition.setCurrentIndex(0 if options.get("automatic_recognition","yes")=="yes" else 2 if options.get("use_same_parameter_as") else 1)
        self.presets=main.info.get("current_releases",{}).get("rows",[])+main.catalog
        self.preset=self.combo([("[Historical] " if not r.get("sha256") else "")+r.get("description",r.get("name","Linux"))+" · "+r.get("filename","") for r in self.presets],install,(16,109,330,26))
        for i,row in enumerate(self.presets):
            if row["id"]==options.get("use_same_parameter_as"):self.preset.setCurrentIndex(i)
        self.preset.setEnabled(self.recognition.currentIndex()==2)
        self.recognition.currentIndexChanged.connect(lambda index:self.preset.setEnabled(index==2))
        self.label("Choose a matching distribution when automatic recognition cannot identify an image.",install,(20,164,325,60))
        languages=tab("Language")
        self.label(self.tr("Available languages"),languages,(30,45,310,26))
        self.language=self.combo(main.info.get("languages",["Automatic","English"]),languages,(65,105,240,26))
        self.language.setCurrentText(main.config.get("General",{}).get("force_lang") or "Automatic")
        self.label("Automatic follows your system language. The original translation files are retained.",languages,(35,160,300,60))
        proxy=tab("Proxy")
        self.label(self.tr("Proxy settings"),proxy,(20,17,320,25))
        self.proxy_mode=self.combo([self.tr("Use system settings"),self.tr("No proxy"),self.tr("Use custom settings")],proxy,(20,52,325,26))
        self.proxy_mode.setCurrentIndex(int(main.config.get("Proxy",{}).get("proxy_mode","0")))
        for n,(title,key) in enumerate([("Proxy URL","proxy_url"),("Port","proxy_port"),("Username","proxy_username"),("Password","proxy_password")]):
            self.label(self.tr(title),proxy,(20,100+n*37,110,24));field=QLineEdit(proxy);field.setGeometry(135,97+n*37,210,24);field.setText(main.config.get("Proxy",{}).get(key,"") or "")
            if key=="proxy_password":field.setEchoMode(QLineEdit.Password)
            self.fields[key]=field
        self.button(self.tr("Test settings"),proxy,(168,277,175,25),self.test_proxy)
        updates=tab("Update")
        self.check("Updates","check_for_updates",self.tr("Check for updates"),updates,35)
        beta=self.check("Updates","check_for_beta_versions","Include beta releases",updates,78)
        beta.setChecked(False);beta.setEnabled(False);beta.setToolTip("The current catalog lists stable releases only.")
        self.label("Refresh the current distribution catalog from the official Ubuntu, Debian and Fedora HTTPS sources.",updates,(25,130,310,70))
        self.button("Refresh distribution catalog",updates,(35,235,285,27),self.check_updates)
        advanced=tab("Advanced")
        self.label(self.tr("Do not modify these options unless you know what you are doing"),advanced,(8,8,350,36))
        scroll=QScrollArea(advanced);scroll.setGeometry(8,45,350,290);scroll.setWidgetResizable(False)
        keys=sorted(main.config.get("Advanced",{}));body=QWidget();body.resize(330,len(keys)*28)
        native_notes={
            "skip_autoreport":"The native port never sends crash reports to the Windows author.",
            "skip_stats":"The native port never sends statistics to the Windows author.",
            "skip_full_cleaning":"Native cleaning removes only files recorded by this port, preserving unrelated files.",
            "skip_uninstaller":"Windows USB uninstaller is unavailable on native hosts; remove the app with your package manager.",
            "skip_autorun":"Windows autorun is unavailable on macOS/Linux. Native launchers are used instead.",
            "skip_vbox_cleaning":"Windows Portable VirtualBox is not installed by the native port.",
            "skip_vboxwarning":"Windows Portable VirtualBox warnings do not apply to the QEMU adapter.",
            "skip_partitiontable_reporting":"The native port does not submit partition-table reports.",
            "skip_finalhelp":"Help is opened explicitly from the Help menu on native hosts.",
            "lili_portable_mode":"This preview uses native per-user settings. A self-contained portable package is not implemented."
        }
        for n,key in enumerate(keys):
            box=self.check("Advanced",key,key,body,n*28)
            if key in native_notes:
                box.setEnabled(False);box.setToolTip(native_notes[key])
                if key in ("skip_autoreport","skip_stats"):box.setChecked(True)
        scroll.setWidget(body)
        self.button(self.tr("OK"),self,(304,408,81,23),self.accept)
    def label(self,text,parent,rect):
        label=QLabel(text,parent);label.setGeometry(*rect);label.setWordWrap(True);return label
    def button(self,text,parent,rect,action):
        button=QPushButton(text,parent);button.setGeometry(*rect);button.clicked.connect(lambda checked=False:action());return button
    def combo(self,values,parent,rect):
        combo=QComboBox(parent);combo.setGeometry(*rect);combo.addItems(values);return combo
    def check(self,section,key,title,parent,y):
        box=QCheckBox(title,parent);box.setGeometry(16,y,320,27);box.setChecked(self.main.config.get(section,{}).get(key)=="yes");self.flags[(section,key)]=box;return box
    def capture(self):
        config=self.main.config
        config.setdefault("General",{})["ui_scale"]=["auto","1.0","1.25","1.5","1.75","2.0"][self.ui_scale.currentIndex()]
        language=self.language.currentText();config.setdefault("General",{})["force_lang"]="" if language=="Automatic" else language
        config.setdefault("Proxy",{})["proxy_mode"]=str(self.proxy_mode.currentIndex())
        for key,field in self.fields.items():config["Proxy"][key]=field.text()
        mode=self.recognition.currentIndex();config.setdefault("Install_Parameters",{})["automatic_recognition"]="yes" if mode==0 else "no"
        config["Install_Parameters"]["use_same_parameter_as"]=self.presets[self.preset.currentIndex()]["id"] if mode==2 and self.preset.currentIndex()>=0 else ""
        for (section,key),box in self.flags.items():config.setdefault(section,{})[key]="yes" if box.isChecked() else "no"
    def accept(self):self.capture();self.main.save_config(self.main.load_language);super().accept()
    def test_proxy(self):
        self.capture();path=self.main.write_json(SUPPORT/"proxy-test.json",self.main.config)
        self.main.task(["test-proxy",path],lambda data,error:QMessageBox.information(self,self.tr("Status"),error or "Proxy connection succeeded"))
    def check_updates(self):
        def done(data,error):
            if data:self.main.info["current_releases"]=data
            QMessageBox.information(self,self.tr("Update"),error or (str(len(data["rows"]))+" current stable releases available."))
        self.main.task(["updates"],done)


class DownloadDialog(QDialog):
    def __init__(self,main):
        super().__init__(main);self.main=main;self.setWindowTitle(main.tr("Download"));self.setFixedSize(540,290);self.setWindowModality(Qt.WindowModal)
        self.metadata=main.info.get("current_releases",{});self.rows=[]
        self.combo=QComboBox(self);self.combo.setGeometry(15,20,510,28)
        self.notice=QLabel(self);self.notice.setWordWrap(True);self.notice.setGeometry(15,58,510,50)
        self.legacy=QCheckBox("Show original catalog (2015)",self);self.legacy.setGeometry(15,112,320,28);self.legacy.toggled.connect(self.populate)
        self.refresh_button=QPushButton("Refresh",self);self.refresh_button.setGeometry(415,110,110,29);self.refresh_button.clicked.connect(self.refresh)
        self.direct=QLineEdit(self);self.direct.setPlaceholderText("Optional direct image URL (HTTP / HTTPS)");self.direct.setGeometry(15,159,510,28)
        self.automatic_button=QPushButton(main.tr("Download automatically"),self);self.automatic_button.setGeometry(15,229,165,32);self.automatic_button.clicked.connect(self.automatic)
        for title,x,action in [(main.tr("Download manually"),190,self.manual),(main.tr("Cancel"),365,self.reject)]:
            button=QPushButton(title,self);button.setGeometry(x,229,160,32);button.clicked.connect(action)
        self.populate()
        import datetime
        try:age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(self.metadata["updated"])).total_seconds()
        except (KeyError,ValueError):age=10**9
        if age>86400 and main.config.get("Updates",{}).get("check_for_updates","yes")=="yes":QTimer.singleShot(0,self.refresh)
    def populate(self,*args):
        self.rows=self.main.catalog if self.legacy.isChecked() else self.metadata.get("rows",[])
        self.combo.clear();self.combo.addItems([r.get("name","Linux")+" · x86_64" if not self.legacy.isChecked() else r.get("description",r.get("name","Linux"))+" · "+r.get("filename","") for r in self.rows])
        self.notice.setText("Original catalog from 2015. Many mirrors are obsolete." if self.legacy.isChecked() else "Current stable releases · Official HTTPS downloads + SHA256 verification\nUpdated: "+self.metadata.get("updated","")[:10]+(" · Some sources could not refresh" if self.metadata.get("errors") else ""))
    def refresh(self):
        self.refresh_button.setEnabled(False);self.automatic_button.setEnabled(False);self.notice.setText("Checking official distribution release metadata…")
        def done(data,error):
            self.refresh_button.setEnabled(True);self.automatic_button.setEnabled(True)
            if data:self.metadata=data;self.main.info["current_releases"]=data
            self.populate()
            if error:self.notice.setText("Could not refresh; showing the last saved catalog. "+error)
        self.main.task(["release-catalog-refresh"],done)
    def selected(self):
        n=self.combo.currentIndex();return self.rows[n] if n>=0 else {}
    def manual(self):
        url=QUrl(self.selected().get("download_page",""))
        if url.scheme() in ("http","https"):QDesktopServices.openUrl(url)
        self.accept()
    def automatic(self):
        row=self.selected();mirrors=row.get("mirrors",[]);url=self.direct.text() or (mirrors[0] if mirrors else "")
        if QUrl(url).scheme() not in ("http","https"):QMessageBox.warning(self,"Download","Enter a valid direct image URL or select an available mirror.");return
        path,_=QFileDialog.getSaveFileName(self,"Download",str(Path.home()/row.get("filename","LinuxLive.iso")))
        if not path:return
        self.main.set_busy(True,"Downloading");self.accept()
        def done(data,error):
            self.main.set_busy(False)
            if error:self.main.error(error)
            else:self.main.inspect(path)
        self.main.task(["download",url if self.direct.text() else json.dumps(mirrors),path,row.get("sha256","") if not self.direct.text() else ""],done,self.main.report_progress)
