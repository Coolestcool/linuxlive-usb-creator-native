# SPDX-License-Identifier: GPL-3.0-only
"""Ubuntu/Debian USB identity adapter. Internal/root/swap disks are never targets."""
import json
import os
from pathlib import Path
import re
from core import run


def inventory():
    return json.loads(run(["/usr/bin/lsblk", "--json", "--bytes", "--output", "NAME,PATH,TYPE,SIZE,MODEL,TRAN,RM,RO,MOUNTPOINT,FSTYPE,PTTYPE,SERIAL,PKNAME"]))["blockdevices"]


def flattened(disks):
    for disk in disks:
        yield disk
        yield from flattened(disk.get("children", []))


def protected(disk):
    return any(row.get("mountpoint") in ("/", "/boot", "/boot/efi", "[SWAP]") for row in flattened([disk]))


def normalized(row, disk):
    name = row["name"]
    external = disk.get("tran") == "usb" and not protected(disk)
    return {"DeviceIdentifier": name, "DeviceNode": row.get("path", "/dev/" + name), "Whole": row.get("type") == "disk", "Internal": not external, "VirtualOrPhysical": "Physical" if disk.get("type") == "disk" and external else "Virtual", "Writable": not bool(row.get("ro")), "TotalSize": int(row.get("size", 0)), "MediaName": (disk.get("model") or name).strip(), "DeviceTreePath": str((Path("/sys/class/block") / disk["name"] / "device").resolve()) + ":" + (disk.get("serial") or ""), "BusProtocol": disk.get("tran") or "", "FilesystemType": "msdos" if row.get("fstype") in ("vfat", "fat", "fat32") else row.get("fstype", ""), "MountPoint": row.get("mountpoint") or "", "PartitionMap": disk.get("pttype") or ""}


def disk_info(identifier):
    if not re.fullmatch(r"(?:sd[a-z]+\d*|nvme\d+n\d+(?:p\d+)?|mmcblk\d+(?:p\d+)?)", identifier): raise ValueError("Invalid Linux USB device identifier")
    for disk in inventory():
        for row in flattened([disk]):
            if row["name"] == identifier: return normalized(row, disk)
    raise ValueError("The selected USB disk is no longer connected.")


def disks():
    from core import validate_disk
    result = []
    for disk in inventory():
        try:
            identity = validate_disk(normalized(disk, disk))
            volumes = [{"identifier": row["name"], "mount": row.get("mountpoint") or "", "size": int(row.get("size", 0))} for row in flattened(disk.get("children", [])) if row.get("fstype") in ("vfat", "fat", "fat32")]
            result.append({"id": disk["name"], "name": (disk.get("model") or disk["name"]).strip(), "size": int(disk["size"]), "identity": identity, "volumes": volumes})
        except ValueError: pass
    return result
