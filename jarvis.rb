class Jarvis < Formula
  desc "Local AI coding assistant for macOS with voice commands and vector memory"
  homepage "https://github.com/nave433-blip/jarvis-dev"
  url "https://github.com/nave433-blip/jarvis-dev/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "c0345dfb6e182f09d9af645d7e49a2203796c066b31c4f9abe4024e567cf6e9b"
  license "MIT"

  depends_on "python@3.12"
  depends_on "ollama"
  depends_on "portaudio"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/jarvis", "--help"
  end
end
