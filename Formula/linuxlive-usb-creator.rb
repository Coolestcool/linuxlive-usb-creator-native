class LinuxliveUsbCreator < Formula
  desc "Native macOS/Linux adaptation of LinuxLive USB Creator"
  homepage "https://github.com/Coolestcool/linuxlive-usb-creator-native"
  version "1.0.0-preview7"
  license "GPL-3.0-only"

  depends_on arch: :x86_64

  on_macos do
    depends_on macos: :tahoe
    url "https://github.com/Coolestcool/linuxlive-usb-creator-native/releases/download/v1.0.0-preview7/linuxlive-usb-creator-1.0.0-preview7-macos-x86_64.tar.gz"
    sha256 "d74b6daed72d39c60331dff21c1bbdf5bcd62a5cca2824dd96b68021f7c965a9"
  end
  on_linux do
    url "https://github.com/Coolestcool/linuxlive-usb-creator-native/releases/download/v1.0.0-preview7/linuxlive-usb-creator-1.0.0-preview7-linux-x86_64.tar.gz"
    sha256 "be50141d824d01f5c196389212961c5e687e43327fc532fde4e1f31ee74de17e"
  end

  def install
    bin.mkpath
    if OS.mac?
      target = prefix/"LinuxLive USB Creator.app"
      if Pathname("Contents").directory?
        target.mkpath
        target.install "Contents"
      else
        prefix.install "LinuxLive USB Creator.app"
      end
      executable = target/"Contents/MacOS/LinuxLive USB Creator"
    else
      if Pathname("LinuxLive USB Creator").directory?
        libexec.install Dir["LinuxLive USB Creator/*"]
      else
        libexec.install Dir["*"]
      end
      executable = libexec/"LinuxLive USB Creator"
    end
    (bin/"linuxlive-usb-creator").write <<~SH
      #!/bin/sh
      exec "#{executable}" "$@"
    SH
    (bin/"linuxlive-usb-creator").chmod 0755
    (bin/"lili").make_symlink "linuxlive-usb-creator"
  end

  def post_install
    if OS.mac?
      app = prefix/"LinuxLive USB Creator.app"
      system "/usr/bin/codesign", "--force", "--deep", "--sign", "-", app
      system "/usr/bin/codesign", "--verify", "--deep", "--strict", app
    end
  end

  def caveats
    <<~EOS
      Preview: Intel macOS 26+, or Ubuntu 22.04+/Debian 12+ amd64.
      QEMU is needed only for launching Linux in a virtual machine.
      macOS: direct USB access may require Full Disk Access for this installed app.
      Reopen it after granting permission; ad-hoc preview updates may need renewed permission.
      Physical USB booting has not been hardware-certified.
    EOS
  end

  test do
    result = JSON.parse(shell_output("#{bin}/linuxlive-usb-creator --backend describe").lines.last)
    assert_equal 519, result.fetch("value").fetch("catalog").length
    (testpath/"test.txt").write "123456789"
    checksum = JSON.parse(shell_output("#{bin}/linuxlive-usb-creator --backend hash #{testpath}/test.txt").lines.last)
    assert_equal "cbf43926", checksum.fetch("value").fetch("crc32")
  end
end
