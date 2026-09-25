"""Voice activity detection — stdlib energy-based VAD plus the interface."""

from __future__ import annotations

import math
import struct
from typing import Optional

from core.voice.base import AudioChunk, VoiceActivityDetector


def _rms_16bit(pcm: bytes) -> float:
    """Root-mean-square of 16-bit little-endian PCM (pure stdlib)."""
    if not pcm:
        return 0.0
    count = len(pcm) // 2
    if count == 0:
        return 0.0
    fmt = "<" + "h" * count
    total = 0
    for sample in struct.unpack(fmt, pcm[:count * 2]):
        total += sample * sample
    return math.sqrt(total / count)


class EnergyVAD(VoiceActivityDetector):
    """Simple energy-threshold VAD over 16-bit PCM. Stdlib only.

    ``threshold_db`` is the dB level above the measured noise floor that
    counts as speech. Call :meth:`calibrate` on a second of room tone first
    for best results.
    """

    def __init__(self, threshold_db: float = 12.0, noise_floor: Optional[float] = None):
        self.threshold_db = threshold_db
        self.noise_floor = noise_floor if noise_floor is not None else 200.0

    def calibrate(self, chunk: AudioChunk) -> float:
        """Measure the noise floor from a chunk of background audio."""
        self.noise_floor = max(_rms_16bit(chunk.pcm), 1.0)
        return self.noise_floor

    def level_db(self, chunk: AudioChunk) -> float:
        rms = _rms_16bit(chunk.pcm)
        if rms <= 0:
            return float("-inf")
        return 20.0 * math.log10(rms / self.noise_floor)

    def is_speech(self, chunk: AudioChunk) -> bool:
        if chunk.sample_width != 2:
            return False
        try:
            return self.level_db(chunk) >= self.threshold_db
        except ValueError:
            return False


def record_until_silence(capture, vad: VoiceActivityDetector,
                         stt=None, max_seconds: float = 30.0,
                         silence_seconds: float = 1.2,
                         device: Optional[int] = None) -> AudioChunk:
    """Record from ``capture`` until ``silence_seconds`` of non-speech.

    Returns the concatenated speech audio. Raises VoiceError from the
    capture backend when the microphone is unavailable.
    """
    import time
    from core.voice.base import AudioChunk as _Chunk

    speech_frames = []
    silent_for = 0.0
    heard_speech = False
    start = time.time()
    fmt = None
    for chunk in capture.stream(device=device):
        if fmt is None:
            fmt = (chunk.sample_rate, chunk.channels, chunk.sample_width)
        frame_len = len(chunk.pcm) / (chunk.sample_rate * chunk.channels * chunk.sample_width)
        if vad.is_speech(chunk):
            heard_speech = True
            silent_for = 0.0
            speech_frames.append(chunk.pcm)
        else:
            if heard_speech:
                silent_for += frame_len
                speech_frames.append(chunk.pcm)
                if silent_for >= silence_seconds:
                    break
        if time.time() - start >= max_seconds:
            break
    pcm = b"".join(speech_frames)
    sr, ch, sw = fmt or (16000, 1, 2)
    return _Chunk(pcm=pcm, sample_rate=sr, channels=ch, sample_width=sw)
