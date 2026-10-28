from pathlib import Path
from typing import List


class AudioDSPService:
    """FFmpeg classical DSP and master remuxing service.

    Pipeline:
    1. Remux 30s WebM/Opus blobs into master_raw.webm.
    2. Apply classical classroom filter chain:
       - 85Hz Highpass (2 poles) - strips fan/HVAC rumble
       - 50Hz and 100Hz Notch (Q=10) - strips Indian electrical grid hum
       - adeclick - removes desk taps & pen clicks
       - speechnorm - volume leveling
    3. Output standard 16 kHz 16-bit mono PCM WAV.
    """

    async def remux_chunks(self, chunk_paths: List[str], output_path: str) -> str:
        """Stitch sequential WebM chunks into a single playable master file."""
        # Implementation in Milestone 2
        return output_path

    async def apply_dsp_filters(self, input_audio_path: str, output_wav_path: str) -> str:
        """Apply classical DSP filter chain to produce normalized 16kHz mono WAV."""
        # Implementation in Milestone 2
        return output_wav_path


def get_audio_dsp_service() -> AudioDSPService:
    return AudioDSPService()
