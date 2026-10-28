from typing import Any, Dict, List


class STTService:
    """Speech-to-text adapter for Sarvam AI Saaras v4 (with_diarization=False)."""

    async def transcribe_slice(
        self, audio_slice_path: str, language_code: str = "hi-IN"
    ) -> List[Dict[str, Any]]:
        """Transcribe a 10-minute audio slice with timestamped words/sentences."""
        # Implementation in Milestone 4
        return []


def get_stt_service() -> STTService:
    return STTService()
