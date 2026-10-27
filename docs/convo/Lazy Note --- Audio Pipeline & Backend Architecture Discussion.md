# Lazy Note — Audio Pipeline & Backend Architecture Discussion

**Date:** 27 October 2026\
**Status:** Architecture Agreed & Ready for Backend Implementation\
**Scope:** Phase 1 MVP — Robust Audio Capture $\rightarrow$ Classical DSP & VAD $\rightarrow$ Transcript $\rightarrow$ Structured Notes

---

## 1. Executive Summary & Scoping Decisions

During this discussion, we aligned on the initial development roadmap for Lazy Note, focusing strictly on building the **Python FastAPI backend** and the core **audio-to-notes pipeline** before integrating frontend recording views or multimodal context features.

### Key Scoping Decisions:

1. **Audio-Only Focus for Phase 1 MVP:**
   - Image uploads (whiteboard camera photos) and slide PDF context parsing (IBM Docling / vision alignment) are deferred to later phases.
   - The immediate focus is building a robust, fault-tolerant pipeline: **Audio Capture $\rightarrow$ Master Remuxing $\rightarrow$ Classical DSP $\rightarrow$ Silero VAD $\rightarrow$ STT Transcription $\rightarrow$ LLM Study Notes**.
1. **Storage Architecture (Local-First with Cloud-Ready Adapter):**
   - Direct integration with Cloudflare R2 requires an Account ID, Access Key ID, and Secret Access Key.
   - To enable instant local development without cloud storage friction, the backend implements a `StorageService` abstraction. Chunks are stored on the local disk (`backend/uploads/`) during development and can switch to Cloudflare R2 presigned URLs via configuration without changing endpoint interfaces.
3. **Strict Focus on Classroom Lectures (No Speaker Diarization):**
   - The user specified that Phase 1 is strictly for lectures, making speaker identification and diarization unnecessary.
   - Slicing audio into 10-minute chunks eliminates any cross-chunk speaker identity fragmentation.
   - STT runs with `with_diarization=False`, which lowers API latency, eliminates diarization failure modes, and keeps the transcript as a pure, chronological stream of `(start_ms, end_ms, text)`.
4. **Edge Persistence & Offline Audio Reuse:**
   - The recorded audio file remains stored on the user's edge device (in `IndexedDB` or `OPFS`) even after successful upload and cloud verification.
   - Students can replay, scrub, and export their recorded lecture offline without consuming internet bandwidth or redownloading audio from the cloud.


---

## 2. End-to-End Audio Pipeline Architecture

```
[ Browser / Device ]
       │
       │ (30s Transport Blobs: MediaRecorder.start(30000))
       ▼
[ FastAPI Ingestion ] ──► Stores in /uploads/ or R2 + Logs in PostgreSQL
       │
       │ (User taps 'Stop' -> Finalize Session)
       ▼
[ Master Audio Assembly ] ──► FFmpeg concatenates chunks into master WAV/WebM
       │
       ▼
[ Stage 1: Classical DSP ] ──► Highpass (85Hz) + Notch (50/100Hz) + adeclick + speechnorm
       │                       (Outputs clean 16kHz 16-bit mono PCM WAV)
       ▼
[ Stage 2: Silero VAD v6 ] ──► Identifies speech vs. silence (>2.5s pauses)
       │                       Generates TimestampOffsetMap
       ▼
[ Stage 3: Silence-Bounded 10-Min Slices ] ──► Split at >=400ms pauses near 10m
       │
       ▼
[ Stage 4: Parallel STT Calls ] ─────────────► Sarvam Saaras v4 (with_diarization=False)
       │                                       Remaps timestamps back to lecture timeline
       ▼
[ Transcript Segments in DB ] ───────────────► Pure timestamped (start_ms, end_ms, text)
                              │
                              ▼
             [ Note Generation Service (Gemini) ]
                              │
                              ▼
            [ Structured Study Notes Artifact ]
```

---

## 3. Pipeline Component Details

### 3.1 Transport Chunking vs. Semantic Slicing

- **Transport Slicing (Network Layer):** The device records 30-second audio blobs (`MediaRecorder.start(30000)`) and uploads them sequentially to prevent losing an entire 90-minute lecture if the tab crashes or Wi-Fi drops.
- **WebM EBML Header Invariant:** Only `chunk_0` contains the EBML container header; subsequent chunks are headerless raw clusters. Sending individual chunks to an STT API or audio processor fails with `Invalid Data`. Chunks must always be assembled into a master recording first.
- **Edge Persistence & Offline Reuse:** Chunks and the assembled audio recording are preserved locally on the client (in `IndexedDB` or OPFS). Uploading and verifying master audio in the cloud does not require deleting the local copy. The audio remains available on-device so students can replay and scrub their lectures anytime offline.


### 3.2 Pre-ASR Classical Classroom DSP (FFmpeg)

Raw lecture audio recorded on mobile phones or laptops suffers from fan rumble, electrical hum, and distance from the podium. Before running ASR, the assembled master audio is filtered:

- **`highpass=f=85:poles=2`:** Eliminates sub-85Hz HVAC rumble, wind, and desk thumps.
- **`equalizer=f=50:t=q:w=10:g=-25` & `equalizer=f=100:t=q:w=10:g=-15`:** Neutralizes 50Hz and 100Hz Indian power-grid hum.
- **`adeclick=w=55:o=75:t=2.5`:** Removes transient pen clicks, mic scratches, and desk taps.
- **`speechnorm=e=6.25:r=0.0001:l=1`:** Normalizes professor volume across far-field distances and dampens loud cough bursts.
- **Downsampling:** Downsampled to 16kHz 16-bit mono PCM (`pcm_s16le`), the native format for Silero VAD and ASR encoders.

### 3.3 Silero VAD & Silence Compaction

- **Model:** Silero VAD v6 runs locally on CPU in $<2\text{ seconds}$ for a 90-minute recording.
- **Silence Pruning:** Pauses $>2.5\text{ seconds}$ (such as blackboard derivations or silent reading) are detected. In a typical 90-minute lecture, 20–25 minutes are dead silence; pruning this saves 20–35% in cloud transcription costs.
- **`TimestampOffsetMap`:** A non-destructive mapping structure records the exact start and end offsets of all speech islands and removed silence gaps. When STT results return from compacted or segmented audio, their timestamps are projected back to exact wall-clock lecture milliseconds.

### 3.4 Slicing into 10-Minute Silence-Trimmed Macro-Chunks

To prevent large HTTP upload payloads, timeouts, and complete job failures:

- Instead of cutting blindly at rigid intervals (`10:00`, `20:00`), the segmenter looks within a boundary window (e.g. `9:30` to `10:15`) for a natural pause ($\ge 400\text{ ms}$) identified by Silero VAD.
- Audio is sliced cleanly at silence, ensuring zero mid-word or mid-sentence truncation.
- If one 10-minute segment fails due to a network glitch, only that 10-minute chunk is retried.

### 3.5 Eliminating Speaker Diarization Overhead for Classroom Lectures

Because Lazy Note Phase 1 focuses strictly on classroom lectures, **speaker diarization is completely removed**:
- In university lectures, students require clear transcriptions of the course content, derivations, and definitions rather than conversational turn-taking.
- Transcribing without diarization (`with_diarization=False`) makes each 10-minute API request faster, cuts cost, and avoids diarization errors entirely.
- Slicing audio into 10-minute chunks carries zero risk of speaker mismatches because there are no speaker IDs to reconcile.

### 3.6 Structured Note Generation

Once all 10-minute transcript segments are stored chronologically:

- The transcript stream is formatted with timestamp markers (`[mm:ss]`).
- Passed to **Google Gemini 2.5 Flash** with a structured engineering prompt requesting:
  - Lecture Title & Key Concepts
  - Detailed Step-by-Step Explanations (preserving Hinglish intuition and English technical terms)
  - Key Definitions & Formulas (LaTeX formatted with KaTeX)
  - Review Questions & Quick Summary

---

## 4. Backend Package Structure & Implementation Plan

Application code is organized in `backend/src/lazynote/`:

```
backend/src/lazynote/
├── __init__.py
├── main.py                  # FastAPI initialization, CORS, global error handling
├── config.py                # Environment configuration (Pydantic BaseSettings)
├── database/
│   ├── __init__.py
│   ├── session.py           # Async SQLAlchemy engine (asyncpg + Supabase)
│   └── models/
│       ├── __init__.py
│       ├── session.py       # RecordingSession model (use_case_type, status, duration)
│       ├── chunk.py         # AudioChunk model (seq_no, offsets, byte_length, status)
│       └── transcript.py    # TranscriptSegment and NoteArtifact models
├── schemas/
│   ├── __init__.py
│   ├── session.py           # SessionCreate, SessionResponse, FinalizeRequest
│   ├── chunk.py             # ChunkUploadResponse, ChunkAck
│   └── transcript.py        # TranscriptSegmentResponse, NoteResponse
├── router/
│   ├── __init__.py
│   ├── health.py            # GET /health
│   ├── sessions.py          # POST /sessions, POST /sessions/{id}/finalize, GET /sessions/{id}
│   ├── chunks.py            # POST /sessions/{id}/chunks
│   └── notes.py             # GET /sessions/{id}/notes, POST /sessions/{id}/notes/generate
└── services/
    ├── __init__.py
    ├── storage.py           # LocalDiskStorage and CloudflareR2Storage implementations
    ├── audio_dsp.py         # FFmpeg chunk concatenation & classical DSP filter chain
    ├── vad.py               # Silero VAD integration & TimestampOffsetMap calculation
    ├── stt.py               # Speech-to-text service adapter (Sarvam Saaras v4)
    └── notes.py             # Note generation service (Gemini 2.5 Flash)
```

---

## 5. Next Steps for Implementation

1. **Database Models & Alembic Migration:** Define `RecordingSession`, `AudioChunk`, `TranscriptSegment`, and `NoteArtifact` models and apply the migration to the Supabase database.
2. **Storage & Chunk Upload Endpoints:** Implement `StorageService` (local disk driver) and the chunk ingestion endpoints (`POST /api/v1/sessions` and `POST /api/v1/sessions/{id}/chunks`).
3. **Master Remuxing & Classical DSP Service:** Implement the FFmpeg assembly and filtering pipeline in `services/audio_dsp.py`.
4. **Silero VAD & 10-Minute Slicer:** Implement the pause detector, `TimestampOffsetMap`, and silence-bounded 10-minute segmenter in `services/vad.py`.
5. **STT & Notes Generation:** Wire the Sarvam Saaras v4 adapter and Gemini 2.5 Flash note generator.
