from typing import Dict, List, Tuple


class TimestampOffsetMap:
    """Non-destructive mapping from compacted audio timeline back to original wall-clock ms."""

    def __init__(self, intervals: List[Tuple[int, int]]):
        self.intervals = intervals  # [(start_ms, end_ms), ...] of speech segments

    def map_to_original_ms(self, compacted_ms: int) -> int:
        """Map millisecond timestamp on compacted audio back to real recording wall-clock ms."""
        # Baseline linear projection across active intervals
        accumulated = 0
        for start, end in self.intervals:
            duration = end - start
            if accumulated + duration >= compacted_ms:
                offset_in_segment = compacted_ms - accumulated
                return start + offset_in_segment
            accumulated += duration
        return self.intervals[-1][1] if self.intervals else compacted_ms


class VADService:
    """Silero VAD v6 silence pruning and silence-bounded 10-minute slicing service."""

    async def detect_speech_intervals(
        self, audio_path: str, min_silence_duration_ms: int = 2500
    ) -> List[Tuple[int, int]]:
        """Identify active speech intervals and prune non-speech pauses >2.5s."""
        # Implementation in Milestone 3
        return []

    async def create_timestamp_map(self, speech_intervals: List[Tuple[int, int]]) -> TimestampOffsetMap:
        """Generate lookup map for reprojecting timestamps."""
        return TimestampOffsetMap(speech_intervals)


def get_vad_service() -> VADService:
    return VADService()
