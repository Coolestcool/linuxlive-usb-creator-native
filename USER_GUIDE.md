# LinuxLive USB Creator — native edition

Maintained by Enrique · Coolestcool. Open-source software under GNU GPL v3.

1. Select the external USB in Step 1. Check its name and capacity.
2. Choose an ISO/IMG/ZIP, a mounted CD/folder, or Download. Download shows current stable Ubuntu, Debian and Fedora images. Refresh updates the official list; SHA256 verification checks the downloaded image. The original catalog is an optional historical list.
3. Set persistence when the selected image supports it. Modern Debian uses a separate Linux partition and therefore requires formatting the USB. Images copied directly keep their original structure and do not receive additional persistence.
4. Choose file visibility, formatting and native launchers. Formatting and direct image copies replace the device's existing layout. QEMU is required only for running Linux inside the host OS.
5. Click the lightning button. Confirm the exact USB identifier and authorize the native disk operation. Wait until verification finishes.

For direct-copy images, Step 4 shows that erasing/replacing the USB layout is mandatory; a separate FAT32 format would be overwritten by the image. On macOS, a private SHA256-checked copy is prepared locally before administrator authorization, so the authorized worker does not need Downloads-folder access. Allow free local space equal to the ISO size plus 16 MiB; the temporary copy is removed after completion or cancellation.

To test without a USB, use File → Create disk image. On Linux, right-click the window to access the File, Bonus and Help menus.

Options → General → Interface size controls the whole window, fonts and dialogs on the next launch. Automatic uses up to 150% and fits the available screen; manual choices extend to 200% when space allows.

The Bonus menu offers CRC32, MD5 and SHA1 checks. Logs and full source are available from the menus. Licenses and notices explain the GPL terms, origin and dependency licenses. No donation prompts or advertising are included.
