from typing import Any, Dict, List


class NotesGenerationService:
    """Structured study notes generator using Google Gemini 2.5 Flash."""

    async def generate_study_notes(
        self, session_title: str, transcript_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process chronological transcript blocks and produce structured KaTeX study notes."""
        # Implementation in Milestone 5
        return {
            "title": session_title,
            "markdown_content": "",
            "summary": "",
            "quiz_json": [],
        }


def get_notes_service() -> NotesGenerationService:
    return NotesGenerationService()
