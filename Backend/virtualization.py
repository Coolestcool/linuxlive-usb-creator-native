# SPDX-License-Identifier: GPL-3.0-only
"""Native host virtualization adapter; no Windows drivers or executables."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
from core import run, disk_info, validate_disk, SUPPORT, exclusive_device


def qemu_path():
    candidates = (["/usr/local/bin/qemu-system-x86_64", "/opt/homebrew/bin/qemu-system-x86_64"] if sys.platform == "darwin" else ["/usr/bin/qemu-system-x86_64"])
    return next((p for p in candidates if Path(p).is_file()), None)


def virtualize_image(path):
    image = Path(path).resolve(strict=True)
    if not image.is_file() or str(image).startswith("/dev/"): raise ValueError("Choose a regular LinuxLive image.")
    qemu = qemu_path()
    if not qemu: raise ValueError("Install QEMU to use the native LinuxLive launcher (brew install qemu, or apt install qemu-system-x86).")
    arguments = [qemu, "-name", "LinuxLive", "-m", "4096", "-smp", "2", "-usb", "-device", "usb-tablet"]
    if sys.platform == "darwin": arguments += ["-accel", "hvf", "-cpu", "host", "-display", "cocoa"]
    else: arguments += ["-machine", "accel=kvm:tcg", "-display", "gtk"]
    if image.suffix.lower() == ".iso": arguments += ["-cdrom", str(image), "-boot", "d"]
    else: arguments += ["-drive", "file=" + str(image).replace(",", ",,") + ",format=raw,if=ide", "-boot", "c"]
    logs = SUPPORT / "VirtualMachines";logs.mkdir(parents=True, exist_ok=True)
    log = logs / "last-launch.log"
    with log.open("wb") as errors:
        process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return {"pid": process.pid, "virtualizer": "QEMU", "source": str(image), "log": str(log)}
    raise ValueError(log.read_text(errors="replace")[-1800:] or "The virtual machine stopped before opening.")


def volume_device(path):
    path = Path(path).resolve(strict=True)
    if not path.is_dir(): raise ValueError("Choose the mounted LinuxLive USB folder.")
    if sys.platform == "darwin":
        volume = plistlib.loads(run(["/usr/sbin/diskutil", "info", "-plist", path]))
        identifier = volume.get("ParentWholeDisk") or volume.get("PartOfWhole")
        if not identifier: raise ValueError("The volume has no physical USB parent.")
    else:
        from linux_disks import inventory, flattened
        data = json.loads(run(["/usr/bin/findmnt", "--json", "--target", path, "--output", "SOURCE"]))
        source = data["filesystems"][0]["source"]
        identifier = next((disk["name"] for disk in inventory() if any(row.get("path") == source for row in flattened([disk]))), None)
        if not identifier: raise ValueError("The selected folder is not on a USB disk.")
    info = disk_info(identifier);identity = validate_disk(info)
    return {"id": identifier, "identity": identity, "name": info.get("MediaName", identifier), "size": info["TotalSize"]}


def uefi_firmware(qemu):
    folder=Path(qemu).parent.parent/"share/qemu"
    pairs=[(folder/"edk2-x86_64-code.fd",folder/"edk2-i386-vars.fd"),
           (Path("/usr/share/OVMF/OVMF_CODE_4M.fd"),Path("/usr/share/OVMF/OVMF_VARS_4M.fd"))]
    return next(((code,variables) for code,variables in pairs if code.is_file() and variables.is_file()),None)


def usb_arguments(qemu,plan,runtime):
    protected=plan.get("read_only",True)
    drive="file=/dev/fdset/1,format=raw,if=none,id=lili-usb"+(",snapshot=on" if protected else "")
    args=[qemu,"-name","LinuxLive USB","-m",str(max(512,min(8192,int(plan.get("memory_mb",4096))))),"-smp","2",
          "-add-fd","fd=3,set=1,opaque=LinuxLiveUSB","-device","qemu-xhci,id=xhci","-drive",drive,
          "-device","usb-storage,drive=lili-usb,bus=xhci.0,bootindex=1","-device","usb-tablet,bus=xhci.0"]
    if plan.get("firmware","bios")=="uefi":
        firmware=uefi_firmware(qemu)
        if not firmware:raise ValueError("UEFI firmware is unavailable. Install QEMU/OVMF or use BIOS mode.")
        args += ["-drive","if=pflash,unit=0,format=raw,readonly=on,file="+str(firmware[0]).replace(",",",,"),
                 "-drive","if=pflash,unit=1,format=raw,file="+str(runtime/"uefi-vars.fd").replace(",",",,")]
    if plan.get("diagnostics"):
        if not protected:raise ValueError("Boot diagnostics require USB write protection.")
        args += ["-display","none","-nic","none","-qmp","unix:"+str(runtime/"qmp.sock")+",server=on,wait=off",
                 "-serial","file:"+str(runtime/"serial.log")]
    else:args += ["-display","cocoa" if sys.platform=="darwin" else "gtk"]
    args += ["-accel","hvf","-cpu","host"] if sys.platform=="darwin" else ["-machine","accel=kvm:tcg"]
    return args


@exclusive_device
def virtualize_usb(plan):
    if os.geteuid() != 0: raise ValueError("Administrator authorization is needed to start Linux from the USB.")
    from creation import unmount
    identifier = plan["disk"]["id"]
    info = disk_info(identifier);validate_disk(info, plan["disk"]["identity"])
    job = Path(plan["job"])
    import pwd
    uid = int(plan["uid"]);account = pwd.getpwuid(uid);gid = account.pw_gid
    if uid <= 0 or job.stat().st_uid != uid: raise ValueError("The virtual machine must run as the owner of this job, never root.")
    qemu = qemu_path()
    if not qemu: raise ValueError("QEMU is required for the USB launcher.")
    runtime=Path(tempfile.mkdtemp(prefix="lili-vm-",dir="/tmp"));os.chown(runtime,uid,gid)
    arguments=usb_arguments(qemu,plan,runtime)
    if plan.get("firmware")=="uefi":
        shutil.copyfile(uefi_firmware(qemu)[1],runtime/"uefi-vars.fd");os.chown(runtime/"uefi-vars.fd",uid,gid)
    (job/"vm.json").write_text(json.dumps({"runtime":str(runtime),"read_only":plan.get("read_only",True),"firmware":plan.get("firmware","bios"),"arguments":arguments},indent=2))
    unmount(identifier, info);validate_disk(disk_info(identifier), plan["disk"]["identity"])
    device = ("/dev/r" if sys.platform == "darwin" else "/dev/") + identifier
    fd = os.open(device, os.O_RDONLY if plan.get("read_only",True) else os.O_RDWR)
    pid = os.fork()
    if pid == 0:
        try:
            if fd != 3: os.dup2(fd,3);os.close(fd)
            os.set_inheritable(3,True);os.closerange(4,1024)
            os.setgroups([]);os.setgid(gid);os.setuid(uid)
            environment = dict(os.environ)
            for key in ("LD_LIBRARY_PATH","DYLD_LIBRARY_PATH","DYLD_FRAMEWORK_PATH"): environment.pop(key,None)
            environment["HOME"] = account.pw_dir
            # The unprivileged guest process cannot use root's private TMPDIR.
            environment["TMPDIR"] = str(runtime)
            for key in ("DISPLAY","XAUTHORITY","XDG_RUNTIME_DIR","WAYLAND_DISPLAY","DBUS_SESSION_BUS_ADDRESS"):
                if key in plan.get("environment",{}):environment[key]=str(plan["environment"][key])
            os.execve(qemu,arguments,environment)
        except Exception:
            os._exit(1)
    os.close(fd)
    _,status = os.waitpid(pid,0)
    if sys.platform == "darwin" and not plan.get("read_only",True):run(["/usr/sbin/diskutil","mountDisk",identifier])
    if status != 0: raise ValueError("The virtual machine could not finish normally. The USB is no longer held by the launcher.")
    return {"status":"finished","disk":identifier,"virtualizer":"QEMU; user privileges","read_only":plan.get("read_only",True)}
