"""Microphone audio capture backends (stdlib-first, optional deps)."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from core.voice.base import AudioChunk, AudioCapture, VoiceError


class UnavailableCapture(AudioCapture):
    """Honest stand-in used when no capture backend is installed."""

    def __init__(self, reason: str):
        self.reason = reason

    def list_devices(self) -> List[Dict[str, str]]:
        raise VoiceError(f"audio capture unavailable: {self.reason}")

    def record(self, seconds: float, device: Optional[int] = None) -> AudioChunk:
        raise VoiceError(f"audio capture unavailable: {self.reason}")

    def stream(self, device: Optional[int] = None):
        raise VoiceError(f"audio capture unavailable: {self.reason}")
        yield  # make this a generator


class SoundDeviceCapture(AudioCapture):
    """Capture via the optional ``sounddevice`` package."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1,
                 frame_seconds: float = 0.5):
        try:
            import sounddevice as sd  # noqa: F401
            # Touch the library: a missing PortAudio raises OSError here,
            # not ImportError.
            sd.query_devices()
        except ImportError as e:
            raise VoiceError(
                "sounddevice is not installed (pip install sounddevice)") from e
        except Exception as e:
            raise VoiceError(f"sounddevice unusable ({e})") from e
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_seconds = frame_seconds

    def list_devices(self) -> List[Dict[str, str]]:
        import sounddevice as sd
        out = []
        for i, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                out.append({"index": str(i), "name": dev.get("name", f"device {i}")})
        return out

    def record(self, seconds: float, device: Optional[int] = None) -> AudioChunk:
        import sounddevice as sd
        import numpy as np
        frames = int(seconds * self.sample_rate)
        try:
            audio = sd.rec(frames, samplerate=self.sample_rate,
                           channels=self.channels, device=device, dtype="int16")
            sd.wait()
        except Exception as e:
            raise VoiceError(f"no usable audio input device ({e})") from e
        return AudioChunk(pcm=audio.tobytes(), sample_rate=self.sample_rate,
                          channels=self.channels, sample_width=2)

    def stream(self, device: Optional[int] = None):
        import sounddevice as sd
        import numpy as np
        frames = int(self.frame_seconds * self.sample_rate)
        try:
            with sd.InputStream(samplerate=self.sample_rate,
                                channels=self.channels, device=device,
                                dtype="int16",
                                blocksize=frames) as stream:
                while True:
                    data, _ = stream.read(frames)
                    yield AudioChunk(pcm=bytes(data),
                                     sample_rate=self.sample_rate,
                                     channels=self.channels, sample_width=2)
        except Exception as e:
            raise VoiceError(f"audio stream failed ({e})") from e


def default_capture(sample_rate: int = 16000) -> AudioCapture:
    """Best available capture backend, or an honest unavailable stand-in."""
    try:
        return SoundDeviceCapture(sample_rate=sample_rate)
    except VoiceError as e:
        return UnavailableCapture(str(e))
