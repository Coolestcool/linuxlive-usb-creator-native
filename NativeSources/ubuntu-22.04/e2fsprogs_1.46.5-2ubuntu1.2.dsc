-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA512

Format: 3.0 (quilt)
Source: e2fsprogs
Binary: fuse2fs, logsave, e2fsck-static, e2fsprogs-l10n, libcom-err2, comerr-dev, libss2, ss-dev, e2fsprogs-udeb, libext2fs2, libext2fs-dev, e2fsprogs
Architecture: any all
Version: 1.46.5-2ubuntu1.2
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Homepage: http://e2fsprogs.sourceforge.net
Standards-Version: 4.6.0
Vcs-Browser: https://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git
Vcs-Git: https://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git -b debian/master
Testsuite: autopkgtest
Testsuite-Triggers: fuse3
Build-Depends: gettext, texinfo, pkg-config, libfuse-dev [linux-any kfreebsd-any] <!pkg.e2fsprogs.no-fuse2fs>, debhelper-compat (= 12), dh-exec, libblkid-dev, uuid-dev, m4, udev [linux-any], systemd [linux-any], cron [linux-any]
Package-List:
 comerr-dev deb libdevel optional arch=any
 e2fsck-static deb admin optional arch=any profile=!pkg.e2fsprogs.no-static
 e2fsprogs deb admin required arch=any
 e2fsprogs-l10n deb localization optional arch=all
 e2fsprogs-udeb udeb debian-installer optional arch=any profile=!noudeb
 fuse2fs deb admin optional arch=linux-any,kfreebsd-any profile=!pkg.e2fsprogs.no-fuse2fs
 libcom-err2 deb libs optional arch=any
 libext2fs-dev deb libdevel optional arch=any
 libext2fs2 deb libs optional arch=any
 libss2 deb libs optional arch=any
 logsave deb admin optional arch=any
 ss-dev deb libdevel optional arch=any
Checksums-Sha1:
 5eb29684be3d0b1b4379afb1e0631fd4cca7ae0e 9530158 e2fsprogs_1.46.5.orig.tar.gz
 fe5bb09669451d775a4e1c09408e669d468e090b 488 e2fsprogs_1.46.5.orig.tar.gz.asc
 81277ae6c881e2b78aed698711e4160f4e6d9e94 86604 e2fsprogs_1.46.5-2ubuntu1.2.debian.tar.xz
Checksums-Sha256:
 b7430d1e6b7b5817ce8e36d7c8c7c3249b3051d0808a96ffd6e5c398e4e2fbb9 9530158 e2fsprogs_1.46.5.orig.tar.gz
 b1e248ed73d4d67ac0cf7760e780e0a5cd2db85bbb9a5dcc235538b596128916 488 e2fsprogs_1.46.5.orig.tar.gz.asc
 b04fad2b12787628497127e6fab76de11c54229e08a406eba126df13f5224fdf 86604 e2fsprogs_1.46.5-2ubuntu1.2.debian.tar.xz
Files:
 3da91854c960ad8a819b48b2a404eb43 9530158 e2fsprogs_1.46.5.orig.tar.gz
 56db20f3239234854c3dcbc864dcfeaf 488 e2fsprogs_1.46.5.orig.tar.gz.asc
 8f2482f024b6deda6c6a2eb7c4458ce6 86604 e2fsprogs_1.46.5-2ubuntu1.2.debian.tar.xz
Original-Maintainer: Theodore Y. Ts'o <tytso@mit.edu>

-----BEGIN PGP SIGNATURE-----

iQIzBAEBCgAdFiEE4qlMxBx1Pex4dJYuxTfgBIBe5lcFAmaZVOkACgkQxTfgBIBe
5lc11xAAiJEUzVxKWQrBbntuNHOmikmAOwPmreEFOktaCJDTNruQyhDTSJpAo4+y
p60rnYuG1MDH889zttf5J32EFohQfm+IQTXB4CidRmb36//2LWaFqqyJ7QrD+PmV
oNTy89GyfxKRGnmJNaGuj5wUi2ZtDn+vEJ45m9iZE9t0GFuGXZ/MvjoM/zMZFu87
o9ZP//1FAHTf/UVqoU4U0pWzcjlfPiyK0G+WLw23ICr6Yipe1/o5R9xhDzs68gv3
MwQ/UpC5xFo6f5DcMvTdEsxfH6lfwo4NyiYxhlGr7ULIVTCCLWZJAfsHtfk9AfeD
2Et8+5sAOkNNEXV4gISdn8s89swL3hNOUqTdTfVtcsfejdq1XtNl2cbbscm9Edwy
bAX4YUVt75ke9crIY1lPogbCSuTNx5dtGrplIGUcWq5tlRwNxQYLEh/0YkxKizTT
17S/C+K9cE2kCjqxbB6a4Zn5D9I+c7NLgW3YRFQKA3kx2lfhmZB8Jf6SwY0DB195
QTHYCIe8PNbtcyaFlKTuFFiGg0yL8UvrdMfvsCtn5nB7eLDIYf7du5epOQfzsdRz
ZcC+COPReCQrnvXYRyT7BiRQCisZcQC7DmHmPHF6cyy3zf9QUKDZ1EtzN+GA20F6
PFIkrxtN0gpDv0I8SjYSZ2J7J9wqrCbU2x9p4azjw/6b1iMUtFY=
=BwiG
-----END PGP SIGNATURE-----
