# Lazy Note — Product Requirements Document (PRD), High-Level System Design (HLD) & Engineering Roadmap

**Role:** Technical Product Manager & Lead Systems Architect  
**Target Domain:** Multi-hour Hinglish/Hindi/English Classroom Lectures, Meetings, Presentations & Pitches  
**Document Purpose:** Production-Ready Blueprint & Step-by-Step First-Project Execution Guide  

## 1. Executive Vision & Product Strategy

### 1.1 The Core Problem & Why Existing Tools Fail in Indian Classrooms & Meetings
Most AI note-taking apps (such as Otter.ai, Fireflies, or standard Whisper wrappers) are built for short, clean, monolingual English Zoom calls. When taken into a real Indian college lecture hall, coaching class, or hybrid startup pitch, they fail across four critical dimensions:

1. **Intra-Sentence Code-Switching (Hinglish):** Indian professors and students naturally switch between Hindi and English mid-sentence (*"Agar hum is matrix ka eigenvalue calculate karein, toh diagonalization possible nahi hoga"*). Standard monolingual Automatic Speech Recognition (ASR) models experience a **30–50% relative increase in Word Error Rate (WER)** on code-switched speech, while standard embedding models drop by up to **27% in retrieval accuracy** across code-switched tasks ([arXiv:2610.27631v1](https://arxiv.org/html/2610.27631v1)).
2. **Multi-Hour Recording Reliability:** A typical university lecture block or marathon workshop runs 1 to 3 hours continuously. Browser recordings or naive mobile recorders crash when the phone screen locks, memory fills up, or campus Wi-Fi drops, losing the entire 2-hour file.
3. **Disconnected Visual Context:** When a teacher says *"Dekho is diagram mein..."* (Look at this diagram) and draws a circuit or derivation on the whiteboard, an audio-only transcript becomes useless. Research on university course materials confirms that **Multimodal Retrieval-Augmented Generation (RAG)**—passing slide/board images alongside aligned transcript segments directly to a Vision-Language Model—significantly outperforms text-only pipelines on complex, math-heavy, and diagrammatic lectures ([arXiv:2510.22272v2](https://arxiv.org/html/2510.22272v2), [arXiv:2512.02817v2](https://arxiv.org/html/2512.02817v2)).
4. **Single-Output Lock-In:** Most tools generate one generic summary and discard the workflow. Students and professionals need a **"Capture Once, Synthesize Infinitely"** workspace where a single immutable master transcript + multimodal asset bundle can generate quick 1-page revision cheat sheets, deep theoretical textbook notes, practice quizzes/flashcards, or action-item trackers on demand.

### 1.2 The "Lazy Note" Value Proposition
**Lazy Note** is a multi-modal, Hinglish-native knowledge engine that synchronizes continuous multi-hour audio recordings, live timestamped camera snapshots (whiteboards/slides), and uploaded PDFs/lecture handouts into a hierarchical workspace (`Workspace → Subject/Project → Folder → Subfolder → Session`).

## 2. Literature, Research & Community Intelligence Synthesis

Before selecting the architecture, we synthesized recent findings from speech processing literature (arXiv), open-source repositories (GitHub), and developer production reports (Reddit/engineering benchmarks).

### 2.1 Insights from Academic Literature (arXiv)
* **Code-Switching ASR & LLM Transfer ([arXiv:2610.27631v1](https://arxiv.org/html/2610.27631v1), [arXiv:2509.24310v2](https://arxiv.org/html/2509.24310v2)):**
  * *Finding:* Disentangling language confusion and accent bias shows that lexical/syntactic switching causes more errors than speaker accent alone. Furthermore, preserving **English technical terms in Latin script** while handling Hindi grammar (or normalizing Hinglish into clean Roman/Devanagari representations) dramatically improves downstream LLM reasoning. On knowledge queries, native Indian language prompts trail English by ~0.50 in accuracy, whereas **code-mixed representations come within ~0.05 of pure English performance** ([arXiv:2610.27631v1](https://arxiv.org/html/2610.27631v1)).
  * *Architectural Takeaway for Lazy Note:* Never force the STT engine to translate technical English terms (e.g., *backpropagation, thermodynamics, EBITDA*) into pure Hindi Devanagari. Preserve mixed-script or Romanized Hinglish in the raw transcript so the downstream LLM retains exact domain terminology.
* **Multimodal Lecture Companions & Visual Alignment ([arXiv:2510.22272v2](https://arxiv.org/html/2510.22272v2), [arXiv:2512.02817v2](https://arxiv.org/html/2512.02817v2), [arXiv:2505.02966v1](https://arxiv.org/html/2505.02966v1)):**
  * *Finding:* Systems like KIT's **BOOM** ([arXiv:2512.02817v2](https://arxiv.org/html/2512.02817v2)) and **AutoLectures** ([arXiv:2505.02966v1](https://arxiv.org/html/2505.02966v1)) prove that tracking which slide or whiteboard image corresponds to each audio timestamp—and feeding the actual image alongside the audio transcript into a Vision-Language Model—yields >92% alignment accuracy (F1) and prevents formula/diagram hallucination.
  * *Architectural Takeaway for Lazy Note:* Every photo snapped during recording must carry a `relative_timestamp_ms` (e.g., `00:42:15`). During note generation, the LLM receives both the transcript window (`00:40:00–00:45:00`) and the high-res whiteboard photo taken at `00:42:15`.

### 2.2 Insights from Open-Source & Developer Communities (GitHub & Reddit)
* **Open-Source Reference Architectures:**
  * **[WhisperX](https://github.com/m-bain/whisperx):** Combines `faster-whisper` batched inference (up to 70x real-time speed) with `wav2vec2` phoneme alignment and `pyannote.audio` speaker diarization for word-level speaker labels. However, GitHub issue reports ([WhisperX Issue #274](https://github.com/m-bain/whisperX/issues/274)) highlight that running `pyannote` diarization on raw 3–4 hour audio files in a single pass triggers GPU Out-Of-Memory (OOM) crashes unless audio is pre-segmented or VAD-chunked.
  * **[Docling (IBM Research)](https://github.com/docling-project/docling):** The leading open-source toolkit for parsing complex academic PDFs, PPTX slides, and DOCX files into structured Markdown and JSON while preserving layout, tables (`TableFormer`), and embedded figures ([IBM Research Blog](https://research.ibm.com/blog/docling-generative-AI)).
  * **[Meetily](https://github.com/Zackriya-Solutions/meetily) & [NoteForge](https://github.com/slnquangtran/NoteForge):** Demonstrate clean separation between local/chunked audio capture and modular LLM post-processing pipelines.
* **Practitioner Consensus on Reddit ([r/VoiceAutomationAI](https://www.reddit.com/r/VoiceAutomationAI/comments/1toeb8f/help_with_the_stt/), [r/vibecoding](https://www.reddit.com/r/vibecoding/comments/1rzfk3e/built_a_tool_that_lets_you_use_parakeet_v3_for/), [r/speechtech](https://www.reddit.com/r/speechtech/comments/1kd9abp/i_benchmarked_12_speechtotext_apis_under_various/)):**
  * Vanilla OpenAI Whisper frequently hallucinates repetitive loops during silent classroom intervals (when a professor is silently writing on the board) unless **Silero VAD (Voice Activity Detection)** strips silence beforehand.
  * For Indian languages and Hinglish code-switching, Indian developers strongly favor **[Sarvam AI (Saaras v3/v4)](https://www.sarvam.ai/apis/speech-to-text)** and **[Shunya Labs Zero STT Codeswitch](https://www.shunyalabs.ai/blog/best-hinglish-speech-to-text-models-0yw1)** over generic Western APIs, while **[Deepgram Nova-3](https://developers.deepgram.com/docs/models-languages-overview)** remains the top choice for low-latency English/global meetings.

## 3. Product Scope & Feature Prioritization (MoSCoW Matrix)

As a first-time builder aiming for a real, multi-user deployable product, **scope discipline is your biggest survival skill**. Below is your Product Manager MoSCoW prioritization:

| Priority Tier | Feature Category | Concrete Capabilities | Why This Tier? |
| :--- | :--- | :--- | :--- |
| **MUST HAVE (MVP — Months 1–3)** | **Resilient Capture & Multimodal Sync** | • **Chunked Audio Recorder** (saves 30s `.opus`/`.webm` chunks locally in `IndexedDB` + uploads in background so 2-hr sessions never die)<br>• **In-Session Camera Snap** (take whiteboard/slide photo while recording; auto-tags exact `timestamp_ms`)<br>• **PDF / Handout Attachment** (upload lecture slides/PDFs per session)<br>• **Hinglish + Diarized Transcript** (Speaker A, Speaker B with clickable timestamps)<br>• **Hierarchical Folders** (`Root → Folder → Subfolder → Session`)<br>• **Multi-Lens Artifact Generator** (generate *Quick Revision Cheat Sheet*, *Deep Theory Notes*, *Practice Quiz/Flashcards*, or *Meeting Action Items* from the same transcript) | Delivers the core "Lazy Note" magic reliably for 2-hour classes without overcomplicating infrastructure. |
| **SHOULD HAVE (v1.5 — Months 4–5)** | **Interactive Q&A & Speaker Naming** | • **Session & Folder RAG Chat** ("Ask my OS Folder: What did Prof. Sharma say about Deadlocks?") with inline timestamp citations<br>• **Speaker Enrollment / Voice Tagging** (Rename `Speaker A` → `Prof. Verma` once; match voice embedding across future classes)<br>• **Smart Reminders & Action Extractor** (Auto-detect *"Assignment due Friday"* or *"Send pitch deck by Tuesday"* from transcript)<br>• **Export Engine** (1-click export to PDF, Markdown, or Notion) | Turns Lazy Note from a passive note generator into an active study & productivity assistant. |
| **COULD HAVE (v2.0 — Month 6+)** | **Collaboration & Live Streaming** | • **Shared Class Folders** (1 student records, 50 classmates view notes & add photos collaboratively)<br>• **Live Real-Time Captions** (WebSocket streaming STT during the lecture)<br>• **Anki `.apkg` Export & Audio Overview** (NotebookLM-style 2-host Hinglish podcast summary) | High viral growth potential on college campuses, but requires higher server concurrency and billing controls. |
| **WON'T HAVE (For Now)** | **Anti-Scope Traps** | • **Custom ASR Model Training from Scratch** (use APIs first)<br>• **Full Video Recording of Lectures** (100x storage/bandwidth cost; audio + timestamped photos achieves 95% of value at 2% of cost)<br>• **Built-in Zoom/Meet Headless Bots** (high maintenance; use browser tab audio capture + mic capture first) | Prevents solo-developer burnout and keeps cloud bills near zero during early growth. |

## 4. Deep-Dive Technology Evaluation & Selection Matrix

### 4.1 Speech-to-Text (STT) & Hinglish Code-Switching Comparison

Choosing the right STT engine is the heart of Lazy Note. Below is the head-to-head comparison of the top production options in 2026 based on official documentation and independent benchmarks:

| Provider & Model | Hinglish / Code-Switching Support | Speaker Diarization & Timestamps | Pricing (2026 Rates) | Best Fit in Lazy Note |
| :--- | :--- | :--- | :--- | :--- |
| **[Sarvam AI — Saaras v4](https://www.sarvam.ai/apis/speech-to-text)** | **Purpose-built for India:** Supports 22 Indian languages + native Hindi-English code-mixing and domain-aware speech translation ([Sarvam Docs](https://docs.sarvam.ai/api/getting-started/models/saaras)). | Native speaker diarization & word/segment timestamps built in ([Sarvam STT Overview](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/overview)). | **₹30/hour** base (`~$0.35/hr`); **₹45/hour** (`~$0.53/hr`) with Speaker Diarization; billed per second with ₹100 free signup credits ([Smallest.ai Pricing Breakdown](https://smallest.ai/blog/sarvam-ai-speech-to-text-pricing), [Sarvam Pricing](https://www.sarvam.ai/api-pricing)). | **PRIMARY ENGINE for Indian Classrooms & Hinglish.** Unbeatable price-to-accuracy ratio (`₹45` for a full 1-hour diarized lecture) and native Indian accent resilience. |
| **[Deepgram — Nova-3](https://developers.deepgram.com/docs/models-languages-overview)** | Supports 45+ languages including Hindi and multilingual code-switching ([Deepgram Pricing](https://deepgram.com/pricing)); excels on clean/moderate English & global accents ([Hermify Benchmark](https://www.hermify.io/en/blog/deepgram-vs-whisper-ai-voice-agent)). | Fast out-of-the-box speaker diarization, smart formatting, and word-level timestamps ([Modal Comparison](https://modal.com/blog/whisper-vs-deepgram)). | **$0.0043/min** (`~$0.26/hr` or `~₹22/hr`) for batch; **$0.0077/min** for streaming ([ConvertAudioToText](https://convertaudiototext.com/blog/deepgram-nova-3-explained)). | **SECONDARY ENGINE for English-heavy Meetings, Pitches & Global Users.** Ultra-fast batch processing (transcribes a 1-hr file in <15 seconds). |
| **[Shunya Labs — Zero STT Codeswitch](https://www.shunyalabs.ai/blog/best-hinglish-speech-to-text-models-0yw1)** | Specifically trained for intra-sentence Hinglish code-switching, preserving English words in Latin script inside Indic transcripts (`11.9%` Hindi WER vs `13.8%` IndicWhisper) ([Shunya Labs](https://www.shunyalabs.ai/blog/best-hinglish-speech-to-text-models-0yw1)). | Supports ~200ms streaming partials and mixed-script output. | Custom / API credit tiers. | **GREAT ALTERNATIVE** if you want mixed Devanagari + Latin script output for specialized enterprise deployments. |
| **[Gladia — Solaria-3](https://www.google.com/search?q=https%3A%2F%2Fwww.gladia.io%2Fblog%2Fbest-speech-to-text-apis)** | Strong multilingual code-switching across 100+ languages ([Gladia Blog](https://www.google.com/search?q=https%3A%2F%2Fwww.gladia.io%2Fblog%2Fmastering-multilingual-speech-to-text-code-switching)). | High-accuracy speaker diarization and word timestamps. | Starts at **€0.16/hour** (`~₹15/hr`) for async batch ([Gladia](https://www.google.com/search?q=https%3A%2F%2Fwww.gladia.io%2Fblog%2Fbest-speech-to-text-apis)). | **COST-EFFECTIVE BATCH FALLBACK** for multilingual European/global expansion. |
| **Self-Hosted [WhisperX](https://github.com/m-bain/whisperx) (`faster-whisper` + `pyannote.audio`)** | Uses Whisper Large-v3-Turbo or AI4Bharat IndicWhisper. Requires VAD tuning to prevent silence hallucinations. | Uses `pyannote/speaker-diarization-community-1` on `pyannote.audio 4.x` ([Fora Soft Guide](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/pyannote-speaker-diarization-production)). | Free open-source weights (MIT / CC-BY-4.0), or €0.035–€0.112/hr on pyannoteAI; requires rented GPU (RunPod/Modal). | **USE LATER AT HIGH SCALE.** Avoid managing GPUs on Day 1; use Sarvam/Deepgram APIs first, then migrate to self-hosted WhisperX on Modal when monthly volume exceeds 5,000+ hours. |

> **PM Decision on STT:** Build an **STT Router Pattern** in your backend. Default to **Sarvam AI (Saaras v4 with Diarization)** when the user selects `Hinglish / Hindi / Indian Classroom` mode (`₹45/hr`), and route to **Deepgram Nova-3** when the user selects `English / Business Meeting` mode (`~₹22/hr`).

### 4.2 Speaker Diarization vs. Speaker Identification (Voice Recognition)
As highlighted in the [Fora Soft 2026 Pyannote Production Guide](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/pyannote-speaker-diarization-production), builders often confuse two distinct technologies:
1. **Speaker Diarization ("Who spoke when?"):** Splits audio into anonymous turns (`Speaker 0: 00:00–00:14`, `Speaker 1: 00:14–00:19`). Both **Sarvam AI Saaras v4** and **Deepgram Nova-3** include this natively via API. Note that far-field classroom audio (one phone mic on a student's desk) has a higher Diarization Error Rate (DER ~20% on far-field benchmarks like AliMeeting vs ~11% on close-mic VoxConverse) ([Fora Soft Guide](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/pyannote-speaker-diarization-production)).
2. **Speaker Identification / Voice Recognition ("Who is Speaker 0?"):** Matching `Speaker 0` to "Prof. Rajesh" or "Ananya (Co-founder)".
   * **How to build it simply in Lazy Note:**
     * **Phase 1 (Zero-ML UX trick — Build this first!):** In a classroom, the person who speaks for 80%+ of the duration is almost always the Professor. Automatically label the dominant speaker `Professor / Main Speaker` and others `Student / Participant 1, 2...`, and let the user click any speaker badge to rename `Speaker 0` → `Prof. Kulkarni` globally across the transcript in 1 click.
     * **Phase 2 (True Voiceprint Matching):** Extract a 256-dimensional speaker embedding vector (using `WeSpeaker` or `pyannote` embedding stage on a clean 10-second solo speech slice) and store it in your PostgreSQL `pgvector` table `speaker_profiles`. Next time the user records in the same folder, compare the new session's speaker embeddings via cosine similarity—if similarity > `0.82`, auto-label `Prof. Kulkarni`!

### 4.3 Full Production Tech Stack Recommendation

| Layer | Recommended Technology | Why This Choice for a Real Production App? |
| :--- | :--- | :--- |
| **Frontend (Web + Mobile)** | **[Next.js (App Router)](https://nextjs.org/) + TypeScript + Tailwind CSS + PWA (Progressive Web App)** *(Optional later: React Native / Expo)* | Starting with an installable Next.js PWA lets you ship to **Laptops, Android, and iOS from a single codebase** in Month 1. Using the browser's `MediaRecorder API` + `IndexedDB` (`Dexie.js`) + `Screen Wake Lock API`, students can record 2-hour classes and snap photos directly from their phone browser. |
| **Backend API** | **[FastAPI (Python)](https://fastapi.tiangolo.com/)** | Python is the native language of AI, audio manipulation (`ffmpeg`), PDF parsing ([Docling](https://github.com/docling-project/docling)), and vector pipelines. FastAPI gives you async performance, automatic OpenAPI docs, and clean Pydantic validation. |
| **Database, Auth & Vector Search** | **[Supabase (PostgreSQL + pgvector + Auth)](https://supabase.com/docs/guides/ai/hybrid-search)** | Instead ofstitching together MongoDB + Pinecone + Firebase Auth, Supabase gives you relational folders/sessions, Row-Level Security (RLS), user authentication, and **[Hybrid Search (`pgvector` semantic embeddings + Postgres `tsvector` keyword search)](https://supabase.com/docs/guides/ai/hybrid-search)** in one managed Postgres database. |
| **Object Storage (Audio, Photos, PDFs)** | **Cloudflare R2** or **AWS S3** (with Presigned URLs) | Multi-hour audio files and whiteboard photos should **never** pass through your FastAPI server memory. The client uploads 30-second audio chunks directly to Cloudflare R2 via presigned URLs (Cloudflare R2 has **zero egress fees**). |
| **Async Queue & Workflow Engine** | **[Inngest](https://www.inngest.com/docs/patterns/jobs/keeping-your-api-fast)** or **Celery / BullMQ + Upstash Redis** | Transcribing a 2-hour audio file, running OCR on 15 whiteboard photos, and generating notes takes 45–120 seconds. Synchronous HTTP requests will time out. [Inngest](https://starterpick.com/guides/background-jobs-inngest-vs-bullmq-vs-trigger-2026) gives you durable step functions (`step.run("transcribe")`, `step.run("parse-pdf")`, `step.run("synthesize-notes")`) with automatic retries and zero Redis boilerplate. |
| **Multimodal LLM & Note Synthesis** | **[Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models)** (Primary) & **[Gemini 2.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite)** (High-volume tasks) | **Why Gemini 2.5 Flash wins here:** A 2-hour lecture transcript (~20,000 words) + a 40-page PDF handout + 10 whiteboard photos easily totals 60,000–100,000 tokens. [Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/long-context) features a **1M token context window**, native vision (reads messy handwritten whiteboard equations in photos), strong Hinglish reasoning, and costs just **$0.30 / 1M input tokens** and **$2.50 / 1M output tokens** with up to 90% savings via context caching ([Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing), [Requesty](https://www.requesty.ai/models/google/gemini-2.5-flash)). |
| **PDF & Slide Parsing** | **[IBM Docling](https://github.com/docling-project/docling)** + **Native Multimodal Vision** | [Docling](https://docling-project.github.io/docling/) extracts structured Markdown, tables, and bounding boxes from uploaded PDFs/PPTX files for free, while critical diagram pages are passed as images to Gemini 2.5 Flash following the multimodal RAG architecture ([arXiv:2510.22272v2](https://arxiv.org/html/2510.22272v2)). |

## 5. High-Level System Design (HLD)

### 5.1 System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                        CLIENT LAYER (Next.js PWA / Mobile)                        |
|                                                                                   |
|  [Audio Capture Engine]           [In-Session Camera]       [Workspace UI]        |
|  • MediaRecorder (16kHz Opus)     • Snaps whiteboard/slide  • Folders/Subfolders  |
|  • Slices 30s chunks              • Tags relative_time_ms   • Transcript Player   |
|  • Buffers in local IndexedDB     • Compresses to WebP      • Multi-Note Tabs     |
+-----------------+----------------------------+----------------------+-------------+
                  | 1. Direct Presigned Upload |                      | 2. REST / SSE
                  v                            v                      v
+--------------------------------------------------------+  +-----------------------+
|          OBJECT STORAGE (Cloudflare R2 / S3)           |  |   API GATEWAY LAYER   |
|  • /sessions/{id}/chunks/chunk_001.opus ...            |  |   FastAPI (Python)    |
|  • /sessions/{id}/photos/snap_004215.webp              |  |   • Auth Middleware   |
|  • /sessions/{id}/docs/lecture_slides.pdf              |  |   • Presigned URLs    |
+---------------------------+----------------------------+  +-----------+-----------+
                            |                                           |
                            | 3. Trigger Event: "session.finalized"     |
                            v                                           v
+-----------------------------------------------------------------------------------+
|               ASYNC ORCHESTRATION ENGINE (Inngest / Redis Queue)                  |
|                                                                                   |
|  Step 1: Audio Stitch & VAD  ---> FFmpeg merges chunks -> Silero VAD strips       |
|                                   dead silence -> normalizes 16kHz mono audio     |
|                                                                                   |
|  Step 2: Parallel Multimodal Extraction                                           |
|     ├── [A] STT & Diarization Router:                                             |
|     │       • Hinglish/Indic -> Sarvam AI Saaras v4 API (₹45/hr w/ Diarization)   |
|     │       • English/Global -> Deepgram Nova-3 API ($0.26/hr Batch)              |
|     ├── [B] Visual Snapshot Processor:                                            |
|     │       • Gemini 2.5 Flash Vision extracts whiteboard equations, diagrams,    |
|     │         and slide text at exact [relative_time_ms]                          |
|     └── [C] Document Parser:                                                      |
|             • IBM Docling parses PDF/PPTX handouts into structured Markdown       |
|                                                                                   |
|  Step 3: Temporal Multimodal Fusion & Indexing                                    |
|     • Merges [Transcript Segments] + [Time-Synced Whiteboard Photos] + [PDF]      |
|     • Generates embeddings -> Writes to Supabase PostgreSQL + pgvector            |
|                                                                                   |
|  Step 4: On-Demand Artifact Synthesis (Gemini 2.5 Flash w/ Context Caching)       |
|     • Generates user-selected lenses: Quick Revision | Deep Theory | Quiz | MoM   |
+-----------------------------------------------------------------------------------+
                                            |
                                            v
+-----------------------------------------------------------------------------------+
|                  DATA PERSISTENCE LAYER (Supabase PostgreSQL)                     |
|  • Relational Tables: users, folders (self-referencing parent_id), sessions       |
|  • Master Context: transcripts, transcript_segments, media_assets                 |
|  • Generated Outputs: note_artifacts (N artifacts per 1 session)                  |
|  • Hybrid Search Index: pgvector (semantic) + tsvector (BM25 keyword search)      |
+-----------------------------------------------------------------------------------+
```

### 5.2 Deep-Dive: Solving the 3 Hardest Engineering Problems

#### Problem 1: How to Record 2–3 Hours of Audio Without Data Loss or Memory Crashes
If a student records a 2-hour lecture in a single in-memory blob and their phone battery dies at minute 115, or they accidentally refresh the tab, **everything is lost**.
* **The Production Solution (Chunked Local-First Streaming):**
  1. Configure the browser's `MediaRecorder` to record in **Opus codec at 24–32 kbps, 16kHz mono** (`audio/webm;codecs=opus`). Why? Speech recognition models downsample all audio to 16kHz mono anyway ([Fora Soft Guide](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/pyannote-speaker-diarization-production)). At 32 kbps, a **full 2-hour lecture is only ~28 MB** (compared to ~1.2 GB for uncompressed WAV)!
  2. Call `mediaRecorder.start(30000)` so it emits a `dataavailable` event every **30 seconds**.
  3. Immediately write each 30-second chunk to the browser's local **`IndexedDB`** (`chunk_0001`, `chunk_0002`...).
  4. A background uploader worker picks up saved chunks from `IndexedDB` and uploads them to **Cloudflare R2** using presigned URLs. Once uploaded (`HTTP 200`), mark `uploaded = true` in `IndexedDB`. If classroom Wi-Fi drops, chunks queue safely on disk and upload automatically when connection returns.

#### Problem 2: Temporal Synchronization of Audio, Live Photos, and PDFs
How do we connect what the teacher **said** with what the student **photographed** on the blackboard and what was in the **PDF handout**?
* **The Production Solution (The Unified Timeline Graph):**
  1. When the recording starts, record `session_start_epoch_ms`. Ignore pauses when computing `recording_offset_ms`.
  2. When the user taps **"Snap Board Photo"** at minute `42:15` of the recording, save the photo with metadata `recording_offset_ms = 2535000`.
  3. During Step 3 of the background pipeline, your Python worker builds a **Multimodal Context Timeline**:
     ```json
     [
       {
         "time_range": "00:41:30 - 00:43:00",
         "speaker": "Prof. Sharma (Speaker 0)",
         "transcript": "Ab dekho, jab hum Kirchhoff's current law node A pe lagate hain, toh I1 + I2 equals I3...",
         "attached_visuals": [
           {
             "type": "whiteboard_photo",
             "timestamp": "00:42:15",
             "image_url": "r2://sessions/99/snap_4215.webp",
             "vision_extracted_latex": "\\sum I_{in} = \\sum I_{out} \\Rightarrow I_1 + I_2 = I_3",
             "visual_description": "Hand-drawn circuit diagram showing Node A with three resistor branches R1, R2, R3."
           }
         ],
         "matched_pdf_slide": "Slide 14: Kirchhoff's Current Law (KCL) & Nodal Analysis"
       }
     ]
     ```
  4. When [Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/long-context) generates notes from this fused timeline, it embeds the actual whiteboard snapshot and LaTeX equation right inside the generated notes at the exact section where KCL is explained!

#### Problem 3: Hierarchical Folders & "One Transcript → Infinite Notes" Database Schema
You want users to organize notes into folders and subfolders (e.g., `Semester 5 → Operating Systems → Unit 2: Deadlocks`) and generate multiple note types from a single saved recording. Here is the clean PostgreSQL schema for **Supabase**:

```sql
-- 1. Hierarchical Folders (supports infinite nesting via parent_folder_id)
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    parent_folder_id UUID REFERENCES folders(id) ON DELETE CASCADE, -- NULL = Root folder
    name TEXT NOT NULL,
    use_case_type TEXT DEFAULT 'classroom', -- 'classroom', 'meeting', 'pitch', 'general'
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Recording Sessions (The Container for a Class or Meeting)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    language_mode TEXT DEFAULT 'hinglish', -- 'hinglish', 'hindi', 'english'
    duration_seconds INT DEFAULT 0,
    status TEXT DEFAULT 'recording', -- 'recording', 'processing', 'ready', 'failed'
    master_audio_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Immutable Master Transcript Segments (Diarized & Timestamped)
CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    speaker_label TEXT NOT NULL,      -- e.g., 'Speaker 0' or 'Prof. Verma'
    start_ms INT NOT NULL,            -- e.g., 2530000
    end_ms INT NOT NULL,              -- e.g., 2545000
    raw_text TEXT NOT NULL,           -- Original Hinglish/Hindi/English text
    fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', raw_text)) STORED,
    embedding VECTOR(768)             -- For Hybrid RAG Search across sessions/folders
);

-- 4. Multimodal Assets (Live Photos & Uploaded PDFs)
CREATE TABLE session_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL,         -- 'live_photo', 'pdf_handout', 'slide_deck'
    file_url TEXT NOT NULL,
    capture_timestamp_ms INT,         -- Populated for live photos taken during recording
    extracted_markdown TEXT,          -- OCR / Docling / Vision output
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Multi-Lens Note Artifacts (Many Notes from One Session!)
CREATE TABLE note_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,      -- 'quick_revision', 'deep_theory', 'practice_quiz', 
                                      -- 'flashcards', 'meeting_mom', 'action_reminders'
    output_language TEXT DEFAULT 'english', -- Can generate clean English notes from Hinglish lecture!
    content_markdown TEXT NOT NULL,
    structured_json JSONB,            -- Used for interactive quizzes, flashcards, or reminders
    created_at TIMESTAMPTZ DEFAULT now()
);
```

## 6. High-Impact Features & Product Ideas to Make Lazy Note Stand Out

Since you asked to brainstorm deeper ideas that will make students and professionals love this product, consider these **6 killer features**:

1. **"Hinglish Spoken → Clean English Written" Toggle (With Original Quote Popovers):**
   * In Indian colleges, teachers explain concepts in Hinglish (*"Iska intuition samjho, gradient descent pahad se neeche utarne jaisa hai"*), which is great for understanding, but students have to write exams in **formal academic English**.
   * Give users a toggle when generating notes:
     * **Mode A (Exam-Ready English):** Translates and formalizes Hinglish explanations into textbook-grade English while keeping a small *"Intuition Box"* quoting the teacher's exact Hinglish analogy!
     * **Mode B (Conversational Hinglish):** Keeps the friendly Hinglish tone for fast personal revision.
2. **"Wait, What Did They Just Say?" Bookmark Button (`📌 Mark Important`):**
   * Even in a "Lazy Note" app, a teacher will frequently say *"Yeh topic mid-sem exam mein 10 marks ka aayega"* (This topic will be worth 10 marks in the midterm). Give the user a giant **1-tap `📌 Exam Alert / Star` button** on the recording screen. It logs the exact timestamp and tells the LLM to highlight that 2-minute window in a dedicated **"High-Priority Exam/Action Alerts"** callout box at the top of the notes.
3. **"Board-Snap Auto-Enhancer" (CamScanner-Style Perspective Crop + Vision LaTeX):**
   * Classroom photos are often taken from an angle at the back bench under tube-light glare. Run a lightweight perspective crop/contrast filter (or pass directly to Gemini 2.5 Flash Vision) to extract both a **clean cropped image** and **editable LaTeX formulas / Mermaid.js diagrams** so the student gets both the real photo and a clean digital diagram in their notes.
4. **Multi-Lens Note Templates (1 Click, 0 Re-transcription Cost):**
   * Because the fused multimodal transcript is saved in `transcript_segments` and `session_assets`, users can click **`+ Generate New Lens`** anytime:
     * **⚡ 5-Minute Quick Revision Sheet:** Bullet points, formulas, definitions, and "Exam Alerts" only.
     * **📘 Deep Theory Textbook Chapter:** Complete step-by-step derivations, conceptual intuition, linked PDF slide extracts, and embedded whiteboard photos.
     * **🎯 Practice & Viva Generator:** 10 MCQs, 5 short-answer conceptual questions, and 3 numerical/coding problems based *strictly* on what the professor taught that day, complete with a hidden answer key.
     * **🤝 Meeting / Pitch Deck Lens:** Executive Summary, Decisions Made, Objections Raised (great for startup pitches!), and **Action Items with Assignee + Due Date** (`Speaker B committed to sending the financial model by Friday`).
5. **Folder-Level "Ask My Semester" RAG Chat:**
   * Because `folders` have a `parent_folder_id` hierarchy and `transcript_segments` use [Supabase Hybrid Search (`pgvector` + `tsvector`)](https://supabase.com/docs/guides/ai/hybrid-search), a student can click on their `Database Management Systems (DBMS)` folder containing 25 recorded lectures and ask: *"Where did the professor explain B+ Tree insertion vs B-Tree, and what example did he draw on the board?"* Lazy Note retrieves the exact lecture date, timestamp (`Lecture 12, 34:10`), audio snippet, and the whiteboard photo!
6. **Smart Gap Detector ("What the Teacher Skipped from the PDF"):**
   * Professors often upload a 50-slide PDF but only teach 30 slides in class, or skip a proof saying *"Read Slide 28 on your own."* Because Lazy Note has both the **PDF handout** and the **audio transcript**, it can automatically add a section: **🔍 Covered in PDF Handout vs. Taught in Class**—flagging which PDF slides were emphasized heavily and which ones the professor skipped!

## 7. Unit Economics & Production Cost Modeling (Can You Afford Real Users?)

To make this a real deployable SaaS, you must know what 1 hour of lecture processing costs you:

| Cost Component (Per 1-Hour Lecture Session) | Provider / Spec | Cost in USD | Cost in INR (`~₹85/$`) |
| :--- | :--- | :--- | :--- |
| **Audio Storage (1 hr @ 32kbps Opus = ~14 MB + 5 Photos)** | Cloudflare R2 (`$0.015/GB/mo`, $0 egress) | `$0.0003 / mo` | `₹0.03 / mo` |
| **Speech-to-Text + Speaker Diarization (Hinglish Mode)** | [Sarvam AI Saaras v4](https://smallest.ai/blog/sarvam-ai-speech-to-text-pricing) (`₹45/hr` with diarization) | `~$0.53` | **`₹45.00`** |
| **Speech-to-Text + Speaker Diarization (English Mode)** | [Deepgram Nova-3 Batch](https://convertaudiototext.com/blog/deepgram-nova-3-explained) (`$0.0043/min`) | `~$0.26` | **`₹22.00`** |
| **Multimodal Vision + 3 Note Lenses (15k input tokens + 5 photos + 4k output tokens)** | [Gemini 2.5 Flash](https://www.requesty.ai/models/google/gemini-2.5-flash) (`$0.30/1M in`, `$2.50/1M out`) | `~$0.016` | **`₹1.35`** |
| **TOTAL COST PER 1-HOUR SESSION** | **Hinglish Mode / English Mode** | **`$0.55` / `$0.28`** | **`~₹46.40` / `~₹23.40`** |

* **How to Price & Protect Your Wallet:**
  * Notice that **96% of your cost is STT**, while LLM note generation (even generating 4 different note styles!) costs barely `₹1.35`! That validates your core product thesis: **transcribe once, generate unlimited note styles for almost free**.
  * **Free Tier:** Give new users **90 minutes of free recording** (costs you ~`₹69` total—and Sarvam AI gives you ₹100 free signup credits and Deepgram gives $200 free credits to start!).
  * **Student Pro Plan (`₹299–₹499/month`):** Include 10–15 hours of recording per month, or let power users buy top-up hour packs (`₹60/hour`).

## 8. Crucial Production Pitfalls to Keep in Mind (First-Time Builder Checklist)

1. **Never Send Raw Silence to STT APIs:** In a 2-hour classroom lecture, 20–30 minutes might be silence while students copy notes from the board or take a break. Run **`Silero VAD`** (Voice Activity Detection) in your Python worker to strip silent intervals >2 seconds *before* calling Sarvam AI or Deepgram, whilst keeping an offset map so original timestamps stay intact. This cuts your STT bill by 20–30% and prevents ASR hallucinations.
2. **Prevent Mobile Screen-Lock Termination:** Mobile browsers pause JavaScript timers when the screen turns off. Use the **[Screen Wake Lock API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API)** (`navigator.wakeLock.request('screen')`) with a dimmed dark-mode "Classroom Recording Screen" so the phone stays awake at 5% brightness on the student's desk while allowing 1-tap photo capture.
3. **Audio Quality & Acoustics Reality Check:** Far-field audio in an echoing classroom is hard. Add a simple onboarding tip in your UI: *"Sit in the first 3 rows or place your phone flat on the desk pointing toward the speaker for 2x better transcription."* Also apply `ffmpeg` high-pass/low-pass filters (`afftdn` / `highpass=f=80,lowpass=f=8000`) to strip ceiling-fan hum before transcription.
4. **Privacy, Consent & Academic Integrity:** Always display a clear recording indicator and include a Terms of Use prompt reminding users to follow their institution's or meeting participants' recording consent policies.

## 9. Step-by-Step 16-Week First-Project Roadmap

Since this is your first major engineering project, **do not try to build everything in Week 1**. Build vertically in 4 structured phases so you have a working product at every milestone.

### Phase 1: The Core Pipeline Prototype (Weeks 1–4)
* **Goal:** Upload a 10-minute Hinglish audio file + 2 whiteboard photos + 1 PDF on your laptop and get back a structured Markdown note.
* **Milestones:**
  * **Week 1:** Set up a Python **FastAPI** repo and a **Supabase** project. Create the `sessions`, `transcript_segments`, and `note_artifacts` tables.
  * **Week 2:** Integrate **[Sarvam AI Saaras v4 API](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/overview)** and **[Deepgram Nova-3 API](https://developers.deepgram.com/docs/models-languages-overview)**. Write a Python script using `ffmpeg` to split long audio into 10-minute segments (if needed by batch limits) and stitch the diarized JSON segments back together with continuous timestamps.
  * **Week 3:** Integrate **[IBM Docling](https://github.com/docling-project/docling)** for PDF text/table extraction and **[Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models)** for multimodal synthesis (passing transcript + timestamped photo + PDF text).
  * **Week 4:** Build the 4 core prompt templates (*Quick Revision Sheet*, *Deep Theory Notes*, *Practice Quiz*, *Meeting Action Items*) using Structured Outputs (JSON Schema) and Markdown.

### Phase 2: The Resilient Web/PWA Recorder & Folder Workspace (Weeks 5–8)
* **Goal:** Record a live 1-hour lecture on your phone browser without losing data, snap photos mid-recording, and organize sessions into folders.
* **Milestones:**
  * **Week 5:** Scaffold the **Next.js (App Router) + Tailwind CSS** frontend with Supabase Auth (Google Sign-In). Build the recursive Folder/Subfolder sidebar (`Workspace → Folder → Subfolder → Session`).
  * **Week 6:** Build the **Chunked Audio Recorder** using `MediaRecorder` (`audio/webm;codecs=opus`) + `Dexie.js` (`IndexedDB`) + **Cloudflare R2** presigned URL uploads every 30 seconds.
  * **Week 7:** Add the **In-Session Camera Snapshot** button (`<input type="file" accept="image/*" capture="environment">` on mobile web) that tags `recording_offset_ms` and uploads the photo to R2 without interrupting the audio recording.
  * **Week 8:** Wire up **[Inngest](https://www.inngest.com/docs/patterns/jobs/keeping-your-api-fast)** background jobs so clicking "Finish Recording" triggers the async pipeline and updates the UI via real-time status polling or Supabase Realtime.

### Phase 3: Multi-Lens Note Studio, Speaker Renaming & RAG Chat (Weeks 9–12)
* **Goal:** Make the workspace interactive—audio playback synced with transcript words, 1-click multi-note generation, and Q&A chat.
* **Milestones:**
  * **Week 9:** Build the **Interactive Transcript Player** (click any paragraph or whiteboard photo in the notes to jump the audio player to that exact `start_ms` timestamp).
  * **Week 10:** Add **1-Click Speaker Renaming** (`Speaker 0` → `Prof. Sharma`) and the **`+ Generate Note Lens`** tab bar so users can generate Quizzes, Flashcards, or Quick Revision sheets from the saved transcript in 5 seconds.
  * **Week 11:** Implement **[Supabase Hybrid Search (`pgvector` + `tsvector`)](https://supabase.com/docs/guides/ai/hybrid-search)** over `transcript_segments` and `session_assets` to power **"Chat with this Lecture / Chat with this Folder"**.
  * **Week 12:** Add the **Action Item & Reminder Extractor** for meetings/class announcements, with 1-click export to PDF/Markdown.

### Phase 4: Production Hardening, Beta Testing & Deployment (Weeks 13–16)
* **Goal:** Deploy to the cloud and onboard your first 50 college classmates for real-world stress testing.
* **Milestones:**
  * **Week 13:** Deploy Next.js frontend to **Vercel**, FastAPI + FFmpeg worker container to **Railway** or **Render**, and configure **Cloudflare R2** CORS + lifecycle rules.
  * **Week 14:** Add **Silero VAD** silence stripping and usage quota tracking (`minutes_used_this_month` column in Supabase) so no single user can drain your API credits.
  * **Week 15:** Run a closed beta in **5 real college lectures** (2 hours each, Hinglish + blackboard photos). Measure Word Error Rate, photo alignment quality, and battery usage.
  * **Week 16:** Polish UI, add "Share Read-Only Note Link" (so students can share generated notes on WhatsApp class groups—your #1 free growth loop!), and launch publicly!
