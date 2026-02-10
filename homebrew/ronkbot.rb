# Homebrew Formula for ronkbot
# Save this as ronkbot.rb in a Homebrew tap

class Ronkbot < Formula
  desc "Personal AI assistant with Telegram, n8n, and Gemini API"
  homepage "https://github.com/rohankag/ronkbot"
  url "https://github.com/rohankag/ronkbot/archive/v1.0.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "docker"
  depends_on "git"

  def install
    # Install all files to prefix
    prefix.install Dir["*"]
    
    # Create wrapper script
    (bin/"ronkbot").write <<~EOS
      #!/bin/bash
      export INSTALL_DIR="#{prefix}"
      exec "#{prefix}/bin/ronkbot" "$@"
    EOS
    
    chmod 0755, bin/"ronkbot"
  end

  def post_install
    ohai "ronkbot installed!"
    puts <<~EOS
      
      To set up ronkbot, run:
        ronkbot config
      
      Or use the web installer:
        curl -fsSL https://ronkbot.dev/install.sh | bash
      
    EOS
  end

  test do
    system "#{bin}/ronkbot", "help"
  end
end
