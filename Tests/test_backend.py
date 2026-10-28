#!/usr/bin/env python3
"""File-only acceptance tests. No physical device is opened or written."""
import copy
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

CONFIG=tempfile.TemporaryDirectory(prefix="lili-test-settings-")
os.environ["LILI_SUPPORT"]=CONFIG.name
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"Backend"))
from core import catalog,translations,settings,hashes,recognize,validate_disk,run,tool,download,normalized_mac_info
from boot import persistence_spec,prepare_boot
from creation import archive_entries,inspect_source,prepare,make_image,clean_fat,verify_fat


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="lili-test-");self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def fixture(self,version=6):
        source=self.root/"ubuntu-test";source.mkdir(exist_ok=True);(source/"casper").mkdir(exist_ok=True)
        (source/"casper/vmlinuz").write_bytes(b"kernel-fixture"*500);(source/"casper/initrd").write_bytes(b"initrd-fixture"*500)
        (source/"document.txt").write_text("source data\n")
        config=settings();config["Install_Parameters"]={"automatic_recognition":"no","use_same_parameter_as":""}
        observed=inspect_source(source,config,lambda *_:None)
        observed["release"]={"name":"Ubuntu fixture","distribution":"ubuntu","supported_features":"ubuntu-persistence,syslinux"+str(version)}
        job=self.root/("job"+str(version));job.mkdir(exist_ok=True)
        return {"source":observed,"job":str(job),"output":str(self.root/("USB test "+str(version)+".img")),"persistence_mb":16,"image_size_mb":128,"settings":config,"hide_files":True,"virtualization":False}
    def test_catalog_languages_and_presets(self):
        self.assertEqual(len(catalog()),519)
        self.assertEqual(translations("Spanish")["step 1 : choose your key"],"PASO 1 : ELIJA SU UNIDAD")
        row=catalog()[0];self.assertEqual(recognize(row["filename"],row.get("file_md5"),settings())["id"],row["id"])
        self.assertEqual(persistence_spec({"supported_features":"ubuntu-persistence"})["file"],"casper-rw")
        self.assertTrue(persistence_spec({"supported_features":"debian-persistence","distribution_version":"12"})["config"])
        self.assertEqual(persistence_spec({"supported_features":"debian-persistence","distribution_version":"6"})["file"],"live-rw")
    def test_hashers(self):
        p=self.root/"hash.txt";p.write_bytes(b"123456789")
        data=hashes(p);self.assertEqual(data["crc32"],"cbf43926");self.assertEqual(data["md5"],hashlib.md5(p.read_bytes()).hexdigest());self.assertEqual(data["sha1"],hashlib.sha1(p.read_bytes()).hexdigest())
    def test_device_guards(self):
        name="disk9" if sys.platform=="darwin" else "sdb"
        good={"DeviceIdentifier":name,"DeviceNode":"/dev/"+name,"Whole":True,"Internal":False,"VirtualOrPhysical":"Physical","Writable":True,"TotalSize":8*1024**3,"MediaName":"Fixture USB","DeviceTreePath":"fixture","BusProtocol":"USB"}
        identity=validate_disk(good)
        for key,value in [("Internal",True),("Internal",None),("Whole",False),("VirtualOrPhysical","Virtual"),("Writable",False),("DeviceNode","/dev/disk0" if name!="disk0" else "/dev/sda")]:
            bad=dict(good);bad[key]=value
            with self.assertRaises(ValueError):validate_disk(bad)
        changed=dict(good);changed["TotalSize"]+=512
        with self.assertRaises(ValueError):validate_disk(changed,identity)
    def test_macos_diskutil_whole_disk_field(self):
        raw={"WholeDisk":True,"Internal":False,"VirtualOrPhysical":"Physical","Writable":True}
        self.assertIs(normalized_mac_info(raw)["Whole"],True)
        self.assertIs(normalized_mac_info(dict(raw,WholeDisk=False))["Whole"],False)
        self.assertIs(normalized_mac_info(dict(raw,Whole=False))["Whole"],False)
        self.assertIsNone(normalized_mac_info({})["Whole"])
    def test_linux_root_and_swap_protection(self):
        from linux_disks import normalized
        usb={"name":"sdb","path":"/dev/sdb","type":"disk","tran":"usb","size":100000000,"ro":False,"model":"Test","children":[{"name":"sdb1","mountpoint":"/","type":"part","size":99999999}]}
        self.assertTrue(normalized(usb,usb)["Internal"])
        usb["children"][0]["mountpoint"]="[SWAP]";self.assertTrue(normalized(usb,usb)["Internal"])
        usb["children"][0]["mountpoint"]="/media/test";self.assertFalse(normalized(usb,usb)["Internal"])
    def test_archive_traversal_rejected(self):
        path=self.root/"bad.zip"
        with zipfile.ZipFile(path,"w") as z:z.writestr("../outside.txt","forbidden")
        with self.assertRaises(ValueError):archive_entries(path)
        self.assertFalse((self.root.parent/"outside.txt").exists())
    def test_four_syslinux_versions_and_persistence(self):
        for version in [3,4,5,6]:
            with self.subTest(version=version):
                plan=self.fixture(version);ready=prepare(plan,lambda *_:None);result=make_image(ready,lambda *_:None)
                image=Path(result["path"]);volume=str(image)+"@@1048576"
                with image.open("rb") as f:
                    mbr=f.read(512);f.seek(1048576);vbr=f.read(512)
                self.assertEqual(mbr[510:512],b"\x55\xaa");self.assertEqual(vbr[510:512],b"\x55\xaa")
                self.assertEqual(struct.unpack_from("<I",mbr,454)[0],2048)
                cfg=run([tool("mtype"),"-i",volume,"::/syslinux/syslinux.cfg"]).decode()
                self.assertIn("persistent",cfg);self.assertIn("/casper/vmlinuz",cfg)
                persisted=self.root/("persistence-"+str(version)+".ext2")
                run([tool("mcopy"),"-i",volume,"::/casper-rw",persisted])
                with persisted.open("rb") as f:f.seek(1024);superblock=f.read(1024)
                self.assertEqual(superblock[56:58],b"\x53\xef");self.assertEqual(superblock[120:129],b"casper-rw")
                verify_fat(Path(plan["job"])/"payload/document.txt",volume,"document.txt")
                unrelated=self.root/"unrelated.txt";unrelated.write_text("Keep my own file")
                run([tool("mcopy"),"-i",volume,unrelated,"::/unrelated.txt"])
                clean_fat(volume)
                self.assertEqual(run([tool("mtype"),"-i",volume,"::/unrelated.txt"]),b"Keep my own file")
    def test_modern_debian_uses_separate_partition(self):
        plan=self.fixture()
        plan["source"]["release"]={"name":"Debian fixture","distribution":"debian","supported_features":"debian-persistence,syslinux6"}
        ready=prepare(plan,lambda *_:None)
        self.assertTrue(Path(ready["persistence_partition"]).is_file())
        self.assertFalse((Path(ready["payload"])/"persistence").exists())
        result=make_image(ready,lambda *_:None)
        with Path(result["path"]).open("rb") as disk:
            mbr=disk.read(512)
            self.assertEqual(mbr[466],0x83)
            start=struct.unpack_from("<I",mbr,470)[0]
            length=struct.unpack_from("<I",mbr,474)[0]
            self.assertEqual(length,16*2048)
            disk.seek(start*512+1024);superblock=disk.read(1024)
            self.assertEqual(superblock[56:58],b"\x53\xef")
            self.assertEqual(superblock[120:131],b"persistence")
        self.assertIn(b"/ union\n",Path(ready["persistence_partition"]).read_bytes())
    def test_current_catalog_stable_releases_and_point_versions(self):
        from releases import current_catalog,ubuntu,fedora
        current=current_catalog();self.assertGreaterEqual(len(current["rows"]),3)
        self.assertTrue(all(len(r["sha256"])==64 for r in current["rows"]))
        first=current["rows"][0]
        manual=recognize("custom.iso",config={"Install_Parameters":{"automatic_recognition":"no","use_same_parameter_as":first["id"]}})
        self.assertEqual(manual["id"],first["id"]);self.assertEqual(manual["sha256"],"")
        pages={"https://releases.ubuntu.com/":'<a href="26.04/">old</a><a href="26.04.1/">new</a><a href="26.10/">latest</a>',
               "https://releases.ubuntu.com/26.04.1/SHA256SUMS":"c"*64+" *ubuntu-26.04-desktop-amd64.iso\n"+"a"*64+" *ubuntu-26.04.1-desktop-amd64.iso\n",
               "https://releases.ubuntu.com/26.10/SHA256SUMS":"b"*64+" *ubuntu-26.10-desktop-amd64.iso\n"}
        with patch("releases.fetch",side_effect=lambda url:pages[url]):
            names=[r["name"] for r in ubuntu()]
            self.assertIn("Ubuntu 26.04.1 LTS Desktop",names)
            self.assertIn("Ubuntu 26.10 Desktop",names)
        rows=[{"version":"45 Beta","arch":"x86_64","subvariant":"Workstation","link":"https://fedoraproject.org/beta.iso","sha256":"a"*64},{"version":"44","arch":"x86_64","subvariant":"Workstation","link":"https://fedoraproject.org/stable.iso","sha256":"b"*64}]
        with patch("releases.fetch",return_value=json.dumps(rows)):
            self.assertEqual(fedora()[0]["name"],"Fedora 44 Workstation")
    def test_modern_hybrid_images_keep_their_original_layout(self):
        path=self.root/"modern.iso";data=bytearray(4096);data[510:512]=b"\x55\xaa";data[450]=0x17;struct.pack_into("<I",data,458,8);path.write_bytes(data)
        release={"name":"Modern fixture","install_method":"raw","sha256":hashlib.sha256(data).hexdigest()}
        with patch("creation.recognize",return_value=release):
            source=inspect_source(path,settings(),lambda *_:None)
        self.assertEqual(source["mode"],"img");self.assertIn("no added persistence",source["raw_reason"])
        job=self.root/"raw-job";job.mkdir()
        plan={"source":source,"job":str(job),"output":str(self.root/"raw-copy.img")}
        created=make_image(prepare(plan,lambda *_:None),lambda *_:None)
        self.assertEqual(Path(created["path"]).read_bytes(),data)
    def test_existing_output_is_not_overwritten(self):
        plan=self.fixture();Path(plan["output"]).write_bytes(b"important")
        plan=prepare(plan,lambda *_:None)
        with self.assertRaises(ValueError):make_image(plan,lambda *_:None)
        self.assertEqual(Path(plan["output"]).read_bytes(),b"important")
    def test_local_download_and_size_limit(self):
        source=self.root/"served";source.mkdir();(source/"test.iso").write_bytes(b"test ISO contents"*4000)
        handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(source))
        server=http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url="http://127.0.0.1:%s/test.iso" % server.server_address[1]
            target=self.root/"download.iso";download(url,target,config={"Proxy":{"proxy_mode":"1"}})
            self.assertEqual(target.read_bytes(),(source/"test.iso").read_bytes())
            protected=self.root/"protected.iso";protected.write_bytes(b"keep existing")
            with self.assertRaises(ValueError):download(url,protected,config={"Proxy":{"proxy_mode":"1"}},expected_sha256="0"*64)
            self.assertEqual(protected.read_bytes(),b"keep existing")
            self.assertFalse((self.root/"protected.iso.part").exists())
            with self.assertRaises(ValueError):download(url,self.root/"too-large.iso",config={"Proxy":{"proxy_mode":"1"}},max_bytes=100)
            self.assertFalse((self.root/"too-large.iso.part").exists())
        finally:server.shutdown();server.server_close()


if __name__=="__main__":unittest.main(verbosity=2)
