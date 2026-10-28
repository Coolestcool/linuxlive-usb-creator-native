# SPDX-License-Identifier: GPL-3.0-only
# Mac adaptation of LinuxLive USB Creator 2.9.4, Thibaut Lauziere.
# Original modules: Settings, Releases, Checking_And_Recognizing, Languages.
import configparser
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import zlib

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
RES = ROOT / "Resources" if (ROOT / "Resources").exists() else ROOT
TOOLS = Path(os.environ.get("LILI_NATIVE_TOOLS", ROOT / "NativeTools" / "bin"))
SUPPORT = Path(os.environ.get("LILI_SUPPORT", Path.home() / "Library/Application Support/LinuxLive USB Creator" if sys.platform == "darwin" else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "linuxlive-usb-creator"))


def text_file(path):
    data = Path(path).read_bytes()
    return data.decode("utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", errors="replace") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else data.decode("cp1252")


def ini(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",), comment_prefixes=(";", "#", ":"), allow_no_value=True)
    parser.read_string(text_file(path))
    return {section: dict(parser[section]) for section in parser.sections()}


def settings():
    values = ini(RES / "settings/settings.ini")
    # A local port does not report to the Windows author's analytics account.
    values.setdefault("Advanced", {})["skip_stats"] = "yes"
    values["Advanced"]["skip_autoreport"] = "yes"
    path = SUPPORT / "settings.json"
    if path.exists():
        for section, data in json.loads(path.read_text()).items():
            values.setdefault(section, {}).update(data)
    return values


def save_settings(values):
    SUPPORT.mkdir(parents=True, exist_ok=True)
    path = SUPPORT / "settings.json"
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as out:
        os.chmod(temporary, 0o600)
        json.dump(values, out, ensure_ascii=False, indent=2)
    temporary.replace(path)


def tool(name):
    p = TOOLS / name
    if not p.is_file():
        raise ValueError("Required native tool is missing: " + name)
    return str(p)


def run(args, **kwargs):
    env = dict(os.environ, PATH=str(TOOLS) + ":/usr/bin:/bin:/usr/sbin:/sbin", MTOOLS_SKIP_CHECK="1")
    result = subprocess.run([str(a) for a in args], capture_output=True, env=env, **kwargs)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace")[-1800:] or "Command failed: " + str(args[0]))
    return result.stdout


def catalog():
    path = SUPPORT / "compatibility_list.ini"
    data = ini(path if path.exists() else RES / "settings/compatibility_list.ini")
    rows = []
    mirrors = ini(RES / "settings/common_mirrors.ini")
    for key, row in data.items():
        if key == "Compatibility_List" or not row.get("filename"):
            continue
        item = dict(row, id=key)
        item["mirrors"] = []
        for field, value in row.items():
            if not field.startswith("mirror") or not value: continue
            if "::" in value:
                common, suffix = value.split("::", 1)
                item["mirrors"].extend(base + suffix for base in mirrors.get(common, {}).values() if base)
            else: item["mirrors"].append(value)
        item["mirrors"] = [v for v in item["mirrors"] if v.startswith(("http://", "https://"))]
        rows.append(item)
    return rows


def translations(language):
    path = RES / "languages" / (language + ".ini")
    if language == "English" or not path.exists():
        return {}
    return {k: v for group in ini(path).values() for k, v in group.items() if v is not None}


def hashes(path, progress=None):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or str(path).startswith("/dev/"):
        raise ValueError("Choose a regular image file.")
    md5, sha1, sha256, crc = hashlib.md5(), hashlib.sha1(), hashlib.sha256(), 0
    total, done = path.stat().st_size, 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            md5.update(block); sha1.update(block); sha256.update(block); crc = zlib.crc32(block, crc); done += len(block)
            if progress:
                progress(done / max(1, total), "Checking source integrity")
    return {"md5": md5.hexdigest(), "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest(), "crc32": "%08x" % (crc & 0xffffffff)}


def recognize(path, digest=None, config=None):
    from releases import current_catalog
    rows = current_catalog()["rows"] + catalog()
    name = Path(path).name.lower()
    options = (config or settings()).get("Install_Parameters", {})
    forced = options.get("use_same_parameter_as", "")
    if options.get("automatic_recognition") == "no":
        preset=next((r for r in rows if r["id"] == forced), {"id": "default", "name": "Default mode", "supported_features": ""})
        return dict(preset,recognition="Manual preset",sha256="")
    for r in rows:
        if digest and r.get("file_md5", "").lower() == digest.lower():
            return dict(r, recognition="MD5 verified")
    for r in rows:
        if r.get("filename", "").lower() == name:
            expected = r.get("file_md5", "").lower()
            return dict(r, recognition="Filename match", hash_mismatch=bool(digest and expected not in ("", "any", digest.lower())))
    for token, distribution in [("ubuntu", "ubuntu"), ("mint", "ubuntu"), ("debian", "debian"), ("kali", "debian"), ("fedora", "fedora"), ("centos", "fedora"), ("mandriva", "mandriva")]:
        if token in name:
            features = {"ubuntu": "ubuntu-persistence", "debian": "debian-persistence", "fedora": "fedora-persistence", "mandriva": "mandriva-persistence"}[distribution]
            return {"id": "detected-" + token, "name": token.title(), "distribution": distribution, "variant": token, "supported_features": features, "recognition": "Filename inference"}
    return {"id": "default", "name": "Default mode", "supported_features": "", "recognition": "Unlisted image"}


def disk_info(identifier):
    if sys.platform.startswith("linux"):
        from linux_disks import disk_info as linux_info
        return linux_info(identifier)
    if not re.fullmatch(r"disk\d+(?:s\d+)?", identifier):
        raise ValueError("Invalid device identifier")
    return plistlib.loads(run(["/usr/sbin/diskutil", "info", "-plist", identifier]))


def validate_disk(info, expected=None):
    identifier = info.get("DeviceIdentifier", "")
    pattern = r"disk\d+" if sys.platform == "darwin" else r"(?:sd[a-z]+|nvme\d+n\d+|mmcblk\d+)"
    if not re.fullmatch(pattern, identifier) or info.get("Whole") is not True:
        raise ValueError("Select an entire external physical USB disk.")
    if info.get("Internal") is not False or info.get("VirtualOrPhysical") != "Physical":
        raise ValueError("Internal disks and disk images are excluded.")
    if info.get("Writable") is not True or int(info.get("TotalSize", 0)) < 16 * 1024 * 1024:
        raise ValueError("The selected disk is not writable.")
    if info.get("DeviceNode") != "/dev/" + identifier:
        raise ValueError("Device path does not match its identity.")
    identity = {k: info.get(k) for k in ("DeviceIdentifier", "TotalSize", "MediaName", "DeviceTreePath", "BusProtocol")}
    if expected and identity != expected:
        raise ValueError("The selected device changed. Refresh and select it again.")
    return identity


def disks():
    if sys.platform.startswith("linux"):
        from linux_disks import disks as linux_disks
        return linux_disks()
    data = plistlib.loads(run(["/usr/sbin/diskutil", "list", "-plist", "external", "physical"]))
    result = []
    for disk in data.get("AllDisksAndPartitions", []):
        try:
            info = disk_info(disk["DeviceIdentifier"]); identity = validate_disk(info)
            volumes = []
            for part in disk.get("Partitions", []):
                detail = disk_info(part["DeviceIdentifier"])
                if detail.get("FilesystemType") == "msdos":
                    volumes.append({"identifier": part["DeviceIdentifier"], "mount": detail.get("MountPoint", ""), "size": detail.get("TotalSize", 0)})
            result.append({"id": info["DeviceIdentifier"], "name": info.get("MediaName", info["DeviceIdentifier"]), "size": info["TotalSize"], "identity": identity, "volumes": volumes})
        except ValueError:
            continue
    return result


def url_opener(config=None):
    p = (config or settings()).get("Proxy", {})
    mode = str(p.get("proxy_mode", "0"))
    if mode == "1":
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    if mode == "2":
        host, port = p.get("proxy_url", ""), p.get("proxy_port", "")
        if not host or not port.isdigit():
            raise ValueError("Enter a proxy host and port.")
        server = host if "://" in host else "http://" + host
        parsed = urllib.parse.urlsplit(server)
        netloc = parsed.hostname + ":" + port
        if p.get("proxy_username"):
            netloc = urllib.parse.quote(p["proxy_username"], safe="") + ":" + urllib.parse.quote(p.get("proxy_password", ""), safe="") + "@" + netloc
        proxy = urllib.parse.urlunsplit((parsed.scheme, netloc, "", "", ""))
        return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener()


def download(url, destination, progress=None, config=None, max_bytes=32 * 1024 ** 3, expected_sha256=None):
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("Only HTTP(S) download URLs are accepted.")
    if expected_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):raise ValueError("Invalid SHA256 checksum")
    digest = hashlib.sha256()
    destination = Path(destination)
    partial = destination.with_name(destination.name + ".part")
    if destination.is_symlink() or partial.is_symlink():raise ValueError("Download paths cannot be symbolic links.")
    try:
        with url_opener(config).open(urllib.request.Request(url, headers={"User-Agent": "LiLi-Mac/1.0"}), timeout=30) as source, partial.open("wb") as out:
            total, received = int(source.headers.get("Content-Length", "0")), 0
            if total > max_bytes:
                raise ValueError("Download exceeds the selected size limit.")
            while True:
                block = source.read(1024 * 1024)
                if not block: break
                received += len(block)
                if received > max_bytes: raise ValueError("Download exceeds the selected size limit.")
                out.write(block);digest.update(block)
                if progress: progress(received / max(1, total), "Downloading " + destination.name)
            if total and received != total: raise ValueError("Incomplete download")
        if expected_sha256 and digest.hexdigest().lower()!=expected_sha256.lower():raise ValueError("The downloaded image does not match the official SHA256 checksum.")
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return str(destination)


def exclusive_device(action):
    """Serialize authorized operations on the same physical disk across instances."""
    from functools import wraps
    import fcntl
    @wraps(action)
    def execute(plan, *args, **kwargs):
        if os.geteuid() != 0:raise ValueError("Administrator authorization is required for this USB operation.")
        identifier=plan["disk"]["id"]
        validate_disk(disk_info(identifier),plan["disk"]["identity"])
        descriptor=os.open("/var/run/linuxlive-"+identifier+".lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,"w") as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ValueError("Another LinuxLive operation is already using this USB.")
            return action(plan,*args,**kwargs)
    return execute
