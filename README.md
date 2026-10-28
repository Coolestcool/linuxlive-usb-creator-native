# LinuxLive USB Creator — native macOS / Linux port

Preview 1.0.0-preview4. Native edition maintained by Enrique ([Coolestcool](https://github.com/Coolestcool)). This is an independent GPL v3 adaptation; origin, copyright and dependency notices are retained in `NOTICE`, `LICENSE`, and `Licenses/`. Changes dated 2026-10-28. The original AutoIt sources, artwork, translations, release catalog and boot templates are under `Original/`. Changed implementation is under `Sources/` and `Backend/`; GPL-3.0-only. See `LICENSE` and `Licenses/` for dependency notices.

## Platforms and installation

- This build targets Intel macOS 26+ and Ubuntu 22.04+/Debian 12+ amd64. Apple Silicon, ARM Linux and older Linux versions are not certified by these builds.
- macOS: unpack the Mac archive and move `LinuxLive USB Creator.app` into Applications. The local build is ad-hoc signed, not Apple-notarized.
- Ubuntu/Debian: `sudo apt install ./linuxlive-usb-creator_1.0.0-preview4_amd64.deb`. Launch `linuxlive-usb-creator` or use the desktop entry.
- QEMU is optional for creating USB media and required for the “launch LinuxLive” feature: `brew install qemu` on Mac; `sudo apt install qemu-system-x86` on Ubuntu/Debian.
- Homebrew uses this repository as a custom tap. First run `brew tap Coolestcool/lili`, then `brew trust --formula Coolestcool/lili/linuxlive-usb-creator` and `brew install lili`. Later use `brew update` and `brew upgrade lili`. The package is not part of Homebrew’s central catalog. The prebuilt Mac package requires Intel macOS 26+; Linux builds target Ubuntu/Debian x86_64.
- Packages are published as GitHub Release assets under immutable version tags, with SHA256 checksums pinned in the formula. `lili` is a short alias for the package and launcher. For Ubuntu/Debian, the `.deb` installs the required desktop and disk-tool dependencies.

## Implemented workflow

Scalable SVG graphics with the original 450×750 five-step composition and palette; original 34 translation files plus English and automatic system-language selection; 519 original distribution presets; ISO/IMG/ZIP, directory and mounted CD sources; proxy-aware downloads; CRC32/MD5/SHA1/SHA256; native FAT32/MBR creation; native Syslinux 3.86/4.07/5.10/6.03; file verification; preservation of unrelated files through a per-installation manifest; ext2 persistence containers; a separate ext2 partition for modern Debian plus persistence.conf; native QEMU launcher; settings and logs. File → Create disk image creates a testable image without touching a physical USB. The installer preset selector shares the current release catalog, keeps historical profiles labeled, and enables the selector only in manual preset mode. Automatic interface scaling grows the whole app to 150% when the screen allows it; Options → General → Interface size selects 100–200% for the next launch. Scaling is capped to fit the available screen.

IMG mode writes an exact raw image; it does not retrofit persistence into arbitrary raw disk layouts. The current Ubuntu/Fedora catalog uses original hybrid images, preserving their own boot loaders and filesystem structure, with no added persistence. An extracted ISO with a file over FAT32’s limit also uses exact-copy mode when it has a valid hybrid MBR. This avoids trying to extract a 6 GiB modern ISO payload into a 4 GiB-limited file. FAT32 files must be smaller than 4 GiB. The current persistence selector allows up to 4095 MiB. Modern Debian excludes the boot volume from persistence probing, so its persistence uses a separate Linux partition and requires the explicit format option on physical USB media. Download opens a current stable x86_64 catalog for Ubuntu, Debian and Fedora, refreshed from official HTTPS metadata. Downloads are verified against official SHA256 before replacing the destination file. The original 2015 catalog is retained behind an explicit checkbox for compatibility; obsolete mirrors may fail. A current ISO can be supplied directly. Filename recognition is an inference; select the correct preset when required.

## Platform differences and preview limits

Windows drivers, Portable VirtualBox, Windows autorun and the Windows uninstaller are not executable on macOS/Linux. The port uses native tools, QEMU and native launchers instead. QEMU must be installed on the host; it is not a self-contained Windows-compatible virtualizer carried inside the USB. Launching a physical USB in QEMU needs administrator authorization and exclusive access to that selected device.

The advanced page retains the original debugging switches. Several switches refer to Windows-only legacy subsystems; they are identified as unavailable on native hosts. This preview does not certify all 519 presets, every BIOS/UEFI combination, Secure Boot, Fedora/Mandriva overlays or GRUB4DOS-only legacy images. Original EFI files are preserved, but preservation alone is not boot certification. The Update action refreshes distribution metadata; it is not a native app binary update feed. The port never installs a Windows executable as an update or reports to the original developer's statistics/crash endpoints.

No physical USB has been written during automated acceptance. Device enumeration and guards are tested, but physical formatting, hardware boot and the raw-device QEMU launcher still require a separately selected sacrificial USB. A successful file/VM test is not a claim of physical hardware certification.

## Build and verification

Use Python 3.9+ and PySide6-Essentials 6.8.3. macOS dependency versions are pinned in `requirements-macos-lock.txt`. Run `python build.py --output /absolute/build-directory` on the target platform. `build_native.py` rebuilds the four native Syslinux installers from `NativeSources/`; `Tests/build_linux_tools.sh` documents the Linux native-tool build. `Tests/Dockerfile` provides the Ubuntu build environment; `Tests/Dockerfile.debian` provides the separate Debian runtime check.

`Tests/test_backend.py`: source catalog/translations, hashes, disk guards, archive paths, four Syslinux versions, actual FAT images/ext2 files, manifest cleaning and loopback HTTP downloads. `Tests/ui_smoke.py`: own-widget renders and controls. `Tests/frozen_backend.py`: runs the packaged executable and its actual native tools against a temporary image. `--self-test <output-directory>` checks packaged frontend/backend communication and produces screenshots. `Tests/boot_guest.sh` + `Tests/boot_smoke.py` check a synthetic Alpine-kernel guest through two boots. `Tests/debian_live.py` checks an official Debian Live ISO, BIOS boot and persistence across guest shutdown/restart. These tests never need a physical USB.

All shipped Python/Qt libraries are dynamically loaded and can be replaced/rebuilt. Full port and original application source is bundled under `Source/` in each installed package. Native source archives and patches are included. See `Licenses/DEPENDENCIES.json` for upstream source locations, versions and notices. Runtime library licenses remain their respective licenses.

## Contact

Enrique · Coolestcool: [enrique330@gmail.com](mailto:enrique330@gmail.com).
