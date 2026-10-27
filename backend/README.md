# Lazy Note — Backend API & Processing Engine

The Python backend service for **Lazy Note**, built with FastAPI, SQLAlchemy 2.0 (async), and Alembic. It powers reliable classroom lecture recording, audio conditioning, speech transcription, and AI note generation.

---

## 1. Phase 1 Architecture: Audio-to-Notes Pipeline

Phase 1 focuses **strictly on classroom lecture processing**, with speaker diarization removed to keep transcription fast, cost-effective, and free of multi-chunk identity fragmentation.

```
30s Client Audio Blobs (Buffered & Retained in IndexedDB/OPFS for Offline Playback)
       │
       ▼
FastAPI Chunk Ingestion (/uploads/ or Cloudflare R2)
       │
       ▼ (Finalize Session)
FFmpeg Master Remuxing (Concatenates blobs into decodable master)
       │
       ▼
Classical Classroom DSP (85Hz highpass, 50/100Hz notch, declick, speechnorm -> 16kHz mono WAV)
       │
       ▼
Silero VAD v6 (Prunes >2.5s silence, generates TimestampOffsetMap)
       │
       ▼
Silence-Bounded Slicing (Slices audio at natural pauses near 10-minute marks)
       │
       ▼
Sarvam AI Saaras v4 STT (Hinglish/Indian English, with_diarization=False)
       │
       ▼
Chronological Timestamped Transcript Segments in PostgreSQL
       │
       ▼
Google Gemini 2.5 Flash (Generates structured study notes with KaTeX math)
```

---

## 2. Tech Stack

- **Framework:** FastAPI with Pydantic v2
- **Database:** Supabase PostgreSQL via SQLAlchemy 2.0 (`asyncio`) + `asyncpg`
- **Migrations:** Alembic
- **Package Manager:** `uv`
- **Audio DSP:** FFmpeg (classical filter chain) + Silero VAD v6 (ONNX/PyTorch)
- **Speech-to-Text:** Sarvam AI Saaras v4 API
- **AI Notes:** Google Gemini 2.5 Flash

---

## 3. Directory Layout

```
backend/
├── src/lazynote/
│   ├── main.py              # FastAPI application factory & lifespan
│   ├── config.py            # Pydantic Settings (.env configuration)
│   ├── database/
│   │   ├── session.py       # Async SQLAlchemy engine & get_db dependency
│   │   └── models/          # RecordingSession, AudioChunk, TranscriptSegment, NoteArtifact
│   ├── schemas/             # Request & response Pydantic schemas
│   ├── router/              # API route controllers (/sessions, /chunks, /notes)
│   └── services/            # Storage, AudioDSP, Silero VAD, STT, and Notes services
├── tests/
│   └── sample/              # Sample lecture audio for pipeline testing
├── scripts/                 # Utility and pipeline verification scripts
├── uploads/                 # Local chunk and master audio storage
├── pyproject.toml           # Project dependencies managed via uv
└── AGENTS.md                # Engineering invariants & architecture rules for agents
```

---

## 4. Development Commands

```bash
# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn lazynote.main:app --reload --port 8000
```
