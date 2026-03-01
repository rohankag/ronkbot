# Homebrew Formula for ronkbot
# This file is auto-updated by the release workflow on each new version tag.
# Do not edit manually — changes will be overwritten on the next release.

class Ronkbot < Formula
  desc "Personal AI assistant — Telegram + n8n + Gemini, running on your Mac"
  homepage "https://github.com/rohankag/ronkbot"
  url "https://github.com/rohankag/ronkbot/archive/v1.0.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256_UPDATED_BY_RELEASE_WORKFLOW"
  license "MIT"
  version "1.0.0"

  depends_on :macos
  depends_on "docker" => :build

  def install
    prefix.install Dir["*"]

    # Install the ronkbot CLI wrapper
    (bin/"ronkbot").write <<~EOS
      #!/usr/bin/env bash
      export RONKBOT_INSTALL_DIR="#{prefix}"
      exec bash "#{prefix}/install.sh" "$@"
    EOS
    chmod 0755, bin/"ronkbot"
  end

  def post_install
    ohai "ronkbot #{version} installed!"
    puts <<~EOS

      To set up your personal AI bot, run:
        ronkbot config

      Documentation: https://github.com/rohankag/ronkbot

    EOS
  end

  test do
    assert_match "usage", shell_output("#{bin}/ronkbot help 2>&1", 0)
  end
end
