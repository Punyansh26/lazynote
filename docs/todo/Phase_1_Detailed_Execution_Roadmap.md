# Lazy Note — Phase 1 Detailed Execution Roadmap

**Target:** Reliable Audio Lecture Capture $\rightarrow$ Classical DSP $\rightarrow$ Silero VAD $\rightarrow$ 10-Minute Slices $\rightarrow$ Hinglish STT $\rightarrow$ Structured Study Notes\
**Version:** 1.1 (Simplified: Strictly Lectures, No Speaker Identification)\
**Status:** Approved for Implementation\
**Target Repository Directory:** `backend/`

---

## 1. Executive Summary & Architectural Philosophy

Phase 1 establishes the core audio-to-notes processing engine of Lazy Note. It is focused **strictly on classroom lectures**. Because classroom lectures are single-lecturer events for note-taking purposes, **speaker identification and diarization are completely removed from Phase 1**.

### Why Dropping Speaker Diarization Simplifies the System:

- **Zero Cross-Chunk Fragmentation:** Slicing audio into 10-minute chunks no longer carries any risk of speaker ID mismatches.
- **Faster & Cheaper STT:** Passing `with_diarization=False` to Sarvam AI / Deepgram reduces API latency, eliminates diarization failure modes, and lowers processing overhead.
- **Simpler Data Models & Prompts:** Transcripts are clean chronological streams of `(start_ms, end_ms, text)`. Note-generation prompts don't have to parse conversational turn-taking—they focus purely on academic derivations, formulas, and concepts.

### The Core Invariants:

1. **Never Lose Audio (Crash-Resilient Transport):** Slicing audio at 30-second transport intervals on the client ensures device crashes or campus Wi-Fi drops only risk at most 30 seconds of audio.
2. **Offline Edge Persistence & Student Reuse:** The recorded audio is preserved locally in the student's browser storage (`IndexedDB` via `Dexie.js` or `OPFS`). After upload verification, the client retains the complete recording offline so students can replay, scrub, and review lectures without using mobile data.
3. **Lossless DSP Before Neural Models:** Clean fan rumble, electrical hum, and volume variance using deterministic FFmpeg filters before feeding audio to VAD or ASR.
4. **Pure Chronological Lecture Flow:** 10-minute silence-bounded audio slices are transcribed independently, their timestamps are projected back to the lecture timeline, and notes are generated from the unified stream.

---

## 2. Phase 1 Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER (Browser / Device)                    │
│  - MediaRecorder emits 30s WebM/Opus blobs (MediaRecorder.start(30000)) │
│  - Buffers immediately in local IndexedDB (Dexie.js) / OPFS             │
│  - Uploads sequentially with seq_no, start_ms, end_ms, and byte_length   │
│  - RETAINS audio locally for instant offline student playback & reuse   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP POST /chunks
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI INGESTION & STORAGE                        │
│  - StorageService: saves chunks to local disk (/uploads/) or R2          │
│  - Supabase PostgreSQL: records AudioChunk row (is_verified = true)     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ User taps Stop -> POST /finalize
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   STAGE 1: MASTER REMUXING & VERIFICATION               │
│  - FFmpeg concat demuxer stitches 30s blobs into master_raw.webm        │
│  - ffprobe checks duration, decodability, and integrity                 │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   STAGE 2: CLASSICAL CLASSROOM DSP (FFmpeg)             │
│  - 85Hz Highpass (AC/fan rumble) + 50/100Hz Notch (power grid hum)     │
│  - adeclick (pen taps) + speechnorm (volume leveling)                   │
│  - Outputs: 16kHz 16-bit mono PCM WAV                                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   STAGE 3: SILERO VAD v6 & SILENCE TRIMMING             │
│  - Silero VAD scans audio in <2s, identifies speech vs. silence         │
│  - Prunes pauses >2.5s (blackboard derivations) -> saves 20-35% cost    │
│  - Builds TimestampOffsetMap (maps compacted audio -> wall-clock ms)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   STAGE 4: SILENCE-BOUNDED 10-MIN SLICING               │
│  - Seeks natural breath pauses (>=400ms) near 10:00 mark (9:30 - 10:15) │
│  - Slices audio cleanly at silence (no mid-word cuts)                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   STAGE 5: PURE TIMESTAMPED STT (No Diarization)        │
│  - Sarvam AI Saaras v4 Batch API (mode="codemix", diarization=False)    │
│  - Remaps segment timestamps back to lecture timeline                   │
│  - Persists pure TranscriptSegment rows to PostgreSQL                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   STAGE 6: STRUCTURED STUDY NOTES GENERATION            │
│  - Gemini 2.5 Flash processes timestamped lecture transcript blocks     │
│  - Outputs Structured Markdown: Overview, Derivations, KaTeX Formulas,  │
│    Glossary, and Review Quiz                                            │
│  - Persists NoteArtifact row to PostgreSQL                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Milestone-by-Milestone Implementation Plan

---

### Milestone 1: Environment, Database Models & Migrations

**Goal:** Establish the database schema, models, and async database engine.

#### 1.1 What to do:

1. Install core dependencies via `uv`:
   - `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
   - `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
   - `python-multipart` (for file uploads), `httpx`
1. Create Pydantic settings configuration in `backend/src/lazynote/config.py`.
2. Set up async database engine and session factory in `backend/src/lazynote/database/session.py`.
3. Define SQLAlchemy models in `backend/src/lazynote/database/models/`:
   - `RecordingSession`: session metadata and status.
   - `AudioChunk`: transport chunk logs.
   - `TranscriptSegment`: simplified timestamped text (no speaker columns).
   - `NoteArtifact`: generated study notes.
1. Configure Alembic for async migrations and generate the baseline migration.

#### 1.2 Database Models (`backend/src/lazynote/database/models/`):

```python
# session.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from lazynote.database.session import Base

class RecordingSession(Base):
    __tablename__ = "recording_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, default="Untitled Lecture")
    status = Column(String(50), nullable=False, default="recording")  # recording | uploading | processing | completed | failed
    expected_chunk_count = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    master_audio_path = Column(String(512), nullable=True)
    dsp_audio_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    chunks = relationship("AudioChunk", back_populates="session", cascade="all, delete-orphan")
    transcript_segments = relationship("TranscriptSegment", back_populates="session", cascade="all, delete-orphan")
    notes = relationship("NoteArtifact", back_populates="session", cascade="all, delete-orphan")
```

```python
# chunk.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from lazynote.database.session import Base

class AudioChunk(Base):
    __tablename__ = "audio_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("recording_sessions.id", ondelete="CASCADE"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    start_offset_ms = Column(Integer, nullable=False)
    end_offset_ms = Column(Integer, nullable=False)
    byte_length = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("RecordingSession", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_session_chunk_seq"),
    )
```

```python
# transcript.py (Pure timestamped lecture segments — no speaker fields!)
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from lazynote.database.session import Base

class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("recording_sessions.id", ondelete="CASCADE"), nullable=False)
    sequence_index = Column(Integer, nullable=False)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("RecordingSession", back_populates="transcript_segments")

class NoteArtifact(Base):
    __tablename__ = "note_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("recording_sessions.id", ondelete="CASCADE"), nullable=False)
    lens_type = Column(String(50), nullable=False, default="detailed_study_notes")
    markdown_content = Column(Text, nullable=False)
    structured_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("RecordingSession", back_populates="notes")
```

---

### Milestone 2: Storage Service & Chunk Ingestion API

**Goal:** Build the HTTP endpoints to create sessions, upload 30-second audio transport chunks, and finalize sessions.

#### 2.1 What to do:

1. Implement `backend/src/lazynote/services/storage.py` with `LocalDiskStorage` storing chunks in `backend/uploads/sessions/{session_id}/chunks/`.
2. Build FastAPI endpoints in `backend/src/lazynote/router/`:
   - `POST /api/v1/sessions`: Starts a lecture session.
   - `POST /api/v1/sessions/{id}/chunks`: Receives a 30s WebM chunk via `UploadFile`, writes to disk, logs in DB.
   - `POST /api/v1/sessions/{id}/finalize`: Validates expected chunk count, locks session, and queues assembly.
   - `GET /api/v1/sessions/{id}`: Returns session progress and verification state.

---

### Milestone 3: Master Remuxing & Classical Classroom DSP Pipeline

**Goal:** Assemble raw 30s WebM chunks into a single decodable master file and clean acoustic noise using FFmpeg.

#### 3.1 What to do:

1. Implement `backend/src/lazynote/services/audio_dsp.py`.
2. Generate an FFmpeg `filelist.txt` listing all verified chunks in sequential order.
3. Stitch chunks using FFmpeg concat demuxer into `master_raw.webm`:
   ```bash
   ffmpeg -y -f concat -safe 0 -i filelist.txt -c copy master_raw.webm
   ```
1. Run `ffprobe` to verify decodability and duration.
2. Apply the Classical Classroom DSP filter chain to generate `dsp_conditioned.wav`:
   ```bash
   ffmpeg -y -i master_raw.webm \
     -af "highpass=f=85:poles=2,equalizer=f=50:t=q:w=10:g=-25,equalizer=f=100:t=q:w=10:g=-15,adeclick=w=55:o=75:t=2.5,speechnorm=e=6.25:r=0.0001:l=1" \
     -ar 16000 -ac 1 -c:a pcm_s16le \
     dsp_conditioned.wav
   ```

---

### Milestone 4: Silero VAD Compaction & Silence-Bounded 10-Minute Slicing

**Goal:** Run Silero VAD to detect speech, prune $>2.5$s silence, build `TimestampOffsetMap`, and slice audio at natural breath pauses near 10 minutes.

#### 4.1 What to do:

1. Implement `backend/src/lazynote/services/vad.py`.
2. Run Silero VAD v6 across `dsp_conditioned.wav` to obtain speech intervals `[(start_ms, end_ms), ...]`.
3. Drop silence pauses $>2500$ms to eliminate Whisper silence hallucinations and save STT billing.
4. Build `TimestampOffsetMap` mapping compacted offsets back to wall-clock milliseconds.
5. Seek natural pauses ($\ge 400$ms) between 9:30 and 10:15 to slice the audio into ~10-minute macro-slices (`slice_00.wav`, `slice_01.wav`, ...).

---

### Milestone 5: Speech-to-Text Integration (Pure Timestamped ASR)

**Goal:** Transcribe the 10-minute macro-slices using Sarvam AI Saaras v4 with pure timestamped output (no speaker diarization).

#### 5.1 What to do:

1. Implement `backend/src/lazynote/services/stt.py` calling the Sarvam AI Batch API (`mode="codemix"`, without diarization).
2. For each 10-minute slice, transcribe audio to get word-level or sentence-level entries.
3. Remap returned slice offsets to absolute lecture timeline milliseconds: $\text{lecture\_ms} = \text{slice\_start\_ms} + \text{segment\_start\_ms}$
4. Persist segments directly to `transcript_segments`.

##### Implementation (`backend/src/lazynote/services/stt.py`):

```python
import os
import httpx
from typing import List, Dict

class SarvamSTTService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.sarvam.ai/speech-to-text"

    async def transcribe_slice(self, file_path: str, slice_start_ms: int) -> List[Dict]:
        headers = {"api-subscription-key": self.api_key}
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "audio/wav")}
                data = {
                    "model": "saaras:v2",
                    "mode": "codemix"
                    # with_diarization is omitted/false for pure lecture transcription
                }
                resp = await client.post(self.url, headers=headers, files=files, data=data)
                resp.raise_for_status()
                result = resp.json()

        # Parse transcript entries and project timestamps to full lecture timeline
        segments = []
        # Support both standard response format and timestamped sentence format
        for entry in result.get("transcript_entries", []):
            s_start = int(entry.get("start_time_seconds", 0) * 1000)
            s_end = int(entry.get("end_time_seconds", 0) * 1000)
            segments.append({
                "start_ms": slice_start_ms + s_start,
                "end_ms": slice_start_ms + s_end,
                "text": entry.get("text", entry.get("transcript", "")),
                "confidence": entry.get("confidence", 1.0)
            })

        if not segments and "transcript" in result:
            segments.append({
                "start_ms": slice_start_ms,
                "end_ms": slice_start_ms,
                "text": result["transcript"],
                "confidence": 1.0
            })

        return segments
```

---

### Milestone 6: Structured Lecture Notes Generation (Gemini 2.5 Flash)

**Goal:** Pass the unified timestamped transcript to Google Gemini 2.5 Flash to generate comprehensive lecture study notes.

#### 6.1 What to do:

1. Implement `backend/src/lazynote/services/notes.py`.
2. Format the chronological transcript with timestamp markers: `[12:35] ...`.
3. Call Gemini 2.5 Flash with the engineering lecture prompt.
4. Save the generated Markdown to `note_artifacts`.

##### Prompt & Service (`backend/src/lazynote/services/notes.py`):

```python
from google import genai

class NotesGenerationService:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def generate_lecture_notes(self, session_title: str, formatted_transcript: str) -> str:
        prompt = f"""
You are an expert university teaching assistant. Convert the following transcript of a classroom lecture into comprehensive, high-quality study notes.

Lecture Title: {session_title}

Chronological Lecture Transcript:
{formatted_transcript}

Please structure the notes as follows:
# 📌 {session_title} — Executive Summary
A clear 3-paragraph summary of what was covered in this lecture.

# 🧠 Core Concepts & In-Depth Derivations
Break down each major topic discussed. For any mathematical derivation, explain the intuition, show step-by-step formulas in LaTeX (using $$ ... $$ for display math and $ ... $ for inline math), and cite the timestamp [mm:ss] where it was explained.

# 📐 Formulas & Key Rules Reference Sheet
A compact reference table or list of all formulas, theorems, and definitions introduced.

# 💡 Professor's Tips & Exam Alerts
Highlight specific warnings, exam tips, or rules emphasized during the lecture.

# ❓ Self-Assessment & Review Questions
Provide 5 concept-check questions with detailed answers based on the lecture material.
"""
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
```

---

### Milestone 7: Pipeline Orchestrator & End-to-End Testing

**Goal:** Connect all stages into an asynchronous workflow and validate against real classroom audio.

#### 7.1 What to do:

1. Implement `backend/src/lazynote/services/orchestrator.py` chaining: `Finalize -> Stitch (FFmpeg) -> DSP (FFmpeg) -> VAD (Silero) -> 10-Min Slices -> Sarvam STT -> Remap Timestamps -> Gemini Notes -> DB`.
2. Hook into `POST /api/v1/sessions/{id}/finalize` using FastAPI `BackgroundTasks`.
3. Execute `backend/scripts/test_pipeline.py` with `backend/tests/sample/ai for autonomous sample.m4a` to verify that complete notes and transcript segments are produced and saved in Supabase.

---

## 4. Definition of Phase 1 Done

Phase 1 is complete and ready for frontend UI pairing when:

1. A recording device can stream 30-second audio transport chunks to FastAPI without losing data.
2. The recorded audio remains cached and playable on the edge device offline for student review.
3. The finalize endpoint reliably remuxes chunks and validates decodability with FFmpeg.
4. Classical DSP filters classroom hum/noise to produce a clean 16kHz mono WAV.
5. Silero VAD prunes $>2.5$s dead silence and dynamically splits audio at natural pauses near 10 minutes.
6. Sarvam AI returns high-accuracy Hinglish text segments mapped to absolute lecture milliseconds.
7. Gemini 2.5 Flash generates comprehensive, KaTeX-formatted study notes.
8. The complete flow executes asynchronously without blocking HTTP requests.
