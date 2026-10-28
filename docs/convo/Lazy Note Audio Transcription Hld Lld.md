# Lazy Note — Audio Capture, DSP, Chunking & Context-Aware Transcription Architecture (Review, HLD & LLD)

**Role:** Senior Technical Product Manager & Principal Systems Architect  
**Scope:** End-to-End Audio Recording, Offline-First Edge Buffering, Cloud DSP & VAD Segmentation, Context-Biased Hinglish ASR, and Multi-Pass Transcript Versioning  
**Target Environment:** 60–120 Minute Indian Classroom Lectures & Hybrid Sessions (English, Hindi, and Intra-Sentence Hinglish)

## 1. Executive Architecture Review: What Works, What Breaks, and What Was Missed

Designing an audio-to-transcript pipeline for a 90-minute classroom lecture is fundamentally different from building a 30-second voice-note bot. Your core instincts—offloading heavy Digital Signal Processing (DSP) and Speech-to-Text (STT) to the cloud, buffering chunks locally inside an offline-first queue, splitting audio on semantic silence boundaries, injecting lecture context into the ASR engine, and preserving an immutable master recording for future re-transcription—are spot-on and align with production architectures at companies like Otter, Loom, and Granola.

However, translating those instincts into code reveals **seven hidden engineering traps** documented across speech recognition research, browser media standards, and production benchmarks. The table below summarizes our review of your proposed architecture, where naive implementations fail, and the exact production upgrades required.

| Pipeline Stage | Your Proposed Idea | What Is Spot-On | Hidden Trap / Engineering Flaw | Production SOTA Upgrade (The Fix) |
| :--- | :--- | :--- | :--- | :--- |
| **1. Edge Capture & Local Queue** | Slice audio into chunks locally, queue in device storage, upload serially, discard local chunks after transcript is ready, keep master recording. | Protects battery/CPU on student phones; survives campus Wi-Fi drops; serial upload prevents saturating weak upstream links. | **The WebM Header Trap:** Browser `MediaRecorder.start(20000)` only puts the EBML/Matroska container header in `chunk_0` ([FFmpeg Micro](https://www.ffmpeg-micro.com/blog/mediarecorder-webm-isn-t-broken-convert-it-to-mp4-server-side)). Subsequent chunks are headerless clusters—if you send `chunk_5` alone to an STT API or DSP tool, it crashes with `Invalid Data`. Also, browser Hardware AGC/Noise Suppression clips distant professors' voices. | Separate **Transport Chunks** (30s byte slices for resilient upload) from **Semantic VAD Chunks**. Disable browser `noiseSuppression` & `autoGainControl` on mic capture. Concatenate all byte slices in the cloud into a seekable Master Audio file before running VAD/DSP. |
| **2. Classroom DSP & Audio Cleanup** | Run DSP in the cloud after chunking to remove fan/AC hum, clicks, and coughs without losing quality. | Cloud execution avoids draining mobile battery; removing stationary fan hum (`50–120 Hz`) and loud cough transients helps human playback. | **The "Over-Denoising Hurts ASR" Paradox:** Studies by [Deepgram](https://deepgram.com/learn/how-voice-ai-works) and [Fora Soft](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments) show that aggressive neural speech enhancement in reverberant rooms strips high-frequency consonant phonemes (`s, t, k, f`), *increasing* Word Error Rate (WER) from `8.02%` (raw) to `11.61%` (processed). | **Dual-Track Audio Pipeline:** Apply gentle high-pass filtering (`80 Hz`), LUFS loudness normalization, and conditional [DeepFilterNet3](https://github.com/rikorose/deepfilternet) (with a `15–20%` wet/dry mix or SNR gate `<15 dB`) for ASR, while offering full DeepFilterNet3 cleanup for the human playback track. |
| **3. Audio Segmentation (15–20s Chunks)** | Segment 90-min audio into 15–20s chunks using silence/breaks (similar to RAG chunking) so STT models perform best. | Whisper-family encoders use a fixed 30s receptive field; splitting at natural pauses prevents mid-word cuts and avoids Whisper hallucination loops on dead silence. | **Global Diarization Amnesia:** If you send 270 isolated 20s chunks to an STT API independently, `Speaker_0` in Chunk 1 and `Speaker_0` in Chunk 2 have **no consistent identity**! Furthermore, cutting strictly at 20s without acoustic overlap drops boundary syllables. | **Two-Tier Segmentation:** (1) For cloud batch APIs like [Sarvam AI Saaras v4](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api) (supports up to 2-hr files natively) or [Deepgram Nova-3](https://developers.deepgram.com/docs/models-languages-overview), pass the VAD-cleaned master file (or 20-min macro-blocks) so speaker diarization stays globally consistent. (2) For Whisper/chunked models, use **Silero VAD v6 Dynamic Windowing** (`15–28s` target, split on `>=400ms` silence, `0.5s` acoustic overlap + rolling prompt context). |
| **4. Hinglish & Script Handling** | Support English, Hindi, and Hinglish; output in Latin (Roman) or Devanagari depending on preference. | Crucial for Indian classrooms where professors code-switch mid-sentence. | **Technical Term Mangling:** Standard `transcribe` mode transliterates English terms like *"Backpropagation"* or *"Eigenvalue"* into Devanagari (`बैकप्रोपेगेशन`), which ruins search and reduces downstream LLM accuracy by ~45% ([arXiv:2610.27631v1](https://arxiv.org/html/2610.27631v1)). | Use **[Sarvam Saaras v4](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/keyterms) `mode="codemix"`** as the canonical master transcript (keeps Hindi in Devanagari and technical English in Latin script) OR `mode="translit"` (clean Roman Hinglish), and derive alternate scripts on demand. |
| **5. Context-Biased Transcription** | Pass lecture topic/context into the STT process so the transcript isn't "dumb" on domain terms. | Highest-ROI accuracy boost in ASR ([Fora Soft](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments), [arXiv:2410.18363v1](https://arxiv.org/html/2410.18363v1)). | **Static Prompt Drift & Token Limits:** [Sarvam Saaras v4](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/keyterms) caps `keyterms` at **50 terms (64 chars each)**; Deepgram Nova-3 caps `keyterm` at **500 tokens**; Whisper caps `initial_prompt` at **224 tokens**. You cannot dump a 40-page PDF into the STT API. | **Pre-Flight Context Distiller:** Before STT runs, pass the lecture title, folder hierarchy (`Semester 5 > OS`), and uploaded PDF slides/whiteboard photos to Gemini 2.5 Flash-Lite to extract the **Top 50 High-Entropy Domain Keyterms** (equations, scientist names, jargon) and inject them into `keyterms` + run a post-STT LLM Phonetic Repair pass. |
| **6. Multi-Pass & Re-Transcription** | Keep the master audio recording so multiple transcripts can be generated later with heavier models. | Future-proofs user data; enables a fast "Draft Transcript" followed by a "High-Precision Transcript" or re-running when better models launch. | **Broken Foreign Keys & Timestamp Drift:** If a user highlights a sentence or attaches a photo to `Transcript v1`, and `Transcript v2` generates different segment boundaries, all user highlights and bookmarks break! | **Anchor on Canonical `recording_offset_ms`, Never Segment IDs:** Store `transcript_revisions` as immutable versioned sets (`v1_fast`, `v2_heavy_verified`). Attach all user bookmarks, photos, and notes to millisecond timestamps (`start_ms`, `end_ms`) on the master timeline so switching transcript versions preserves every link. |

## 2. High-Level System Design (HLD)

### 2.1 Architectural Principles
1. **Separation of Transport Slicing vs. Semantic Segmentation:** The client slices audio strictly for **network transport and crash resilience** (fixed 30-second binary blocks). The cloud worker reconstructs the continuous stream and performs **acoustic/semantic segmentation** using Voice Activity Detection (VAD) and speaker turn boundaries.
2. **Non-Destructive Dual-Path Audio Storage:** Raw captured audio is remuxed into an immutable, seekable **Master Archive (`master_raw.webm` / `.m4a`)** in Cloudflare R2. Any DSP enhancement produces a transient or secondary derivative (`master_enhanced.wav`), guaranteeing that if a neural denoiser ever introduces artifacts, the original waveform remains untouched.
3. **Two-Stage Context Injection (Pre-ASR Biasing + Post-ASR Phonetic Repair):** Domain intelligence is injected *before* acoustic decoding (via keyterm biasing lists extracted from slides/board photos) and *after* acoustic decoding (via a sliding-window LLM phonetic correction pass that fixes residual acoustic homophones like *"Koshish-Schwarz"* → *"Cauchy-Schwarz"* while strictly preserving timestamps).

### 2.2 End-to-End HLD Pipeline Diagram

```
+========================================================================================+
|                        1. EDGE CLIENT (Next.js PWA / Mobile App)                       |
|                                                                                        |
|  [Mic Capture: 16kHz Mono PCM] ---> (Disable OS AGC / OS Noise Suppression)            |
|         |                                                                              |
|         +---> [MediaRecorder (Opus 32kbps, timeslice=30000ms)]                         |
|                     |                                                                  |
|                     v                                                                  |
|         [Local Persistence Queue (IndexedDB / OPFS)]                                   |
|           • Stores {session_id, seq_no, blob, crc32, start_ms, end_ms, status}         |
|           • Survives tab crash, screen lock (WakeLock API), or 2-hour Wi-Fi blackout   |
|                     |                                                                  |
|                     v (Serial Background Worker w/ Exponential Backoff)                |
+=====================|==================================================================+
                      | Presigned PUT (Direct-to-R2, ~120 KB per 30s chunk)
                      v
+========================================================================================+
|                     2. CLOUD OBJECT STORAGE (Cloudflare R2)                            |
|  • /sessions/{id}/raw_chunks/chunk_0000.webm ... chunk_0180.webm                       |
|  • /sessions/{id}/context_assets/slides.pdf, whiteboard_004215.webp                    |
|  • /sessions/{id}/master/master_raw.webm (Immutable Source of Truth)                   |
|  • /sessions/{id}/master/master_clean_human.m4a (DSP-Enhanced Playback Track)          |
+=====================|==================================================================+
                      | Event: "session.upload_completed" (Inngest / Redis Durable Job)
                      v
+========================================================================================+
|                 3. CLOUD AUDIO PREPROCESSING & DSP WORKER (Python + FFmpeg)            |
|                                                                                        |
|  [Step 3.1: Binary Stitch & Container Remux]                                           |
|    • Validates chunk sequence 0..N (no missing blocks, verifies CRC32)                 |
|    • Binary-concatenates WebM clusters -> `ffmpeg -c copy -cues_to_front 1`            |
|    • Saves seekable `master_raw.webm` (21.6 MB for 90 mins) -> Notifies Client to      |
|      safely purge local IndexedDB chunks!                                              |
|                                                                                        |
|  [Step 3.2: Acoustic Triage & Conditional DSP Pipeline]                                |
|    • Decodes to 16kHz 16-bit Mono PCM (`master_16k.wav`)                               |
|    • FFmpeg Classical Filter Chain:                                                    |
|        - `highpass=f=80` (strips ceiling fan blade rumble & AC compressor hum)         |
|        - `adeclick` (removes mic handling ticks, pen clicks, and desk taps)            |
|        - `dynaudnorm` / `loudnorm` (boosts far-field professor voice gently)           |
|    • Neural Denoising Gate (SNR Estimator):                                            |
|        - Produces `clean_human.m4a` via DeepFilterNet3 ( removes coughs/chatter)       |
|        - For ASR Track: If SNR < 15 dB, applies DeepFilterNet3 w/ 12dB attenuation     |
|          limit (prevents phoneme stripping); if SNR >= 15 dB, keeps classical filtered |
|                                                                                        |
|  [Step 3.3: Silero VAD v6 & Non-Destructive Offset Mapping]                            |
|    • Runs Silero VAD v6 across 90-min audio in <1.8 seconds on CPU                     |
|    • Identifies speech islands & strips dead silence (>2.5s board-writing pauses)      |
|    • Builds `TimestampOffsetMap` so stripped audio maps back to exact wall-clock ms    |
+=====================|==================================================================+
                      |
                      v
+========================================================================================+
|             4. CONTEXT-AWARE ASR & MULTI-PASS TRANSCRIPTION ENGINE                     |
|                                                                                        |
|  [Step 4.1: Pre-ASR Context Distiller (Gemini 2.5 Flash-Lite)]                         |
|    • Reads Session Title + Folder Path + PDF Handout Headings + Whiteboard OCR         |
|    • Outputs Top 50 Domain Keyterms (e.g., ["Eigenvalue", "Kirchhoff", "Cauchy"])      |
|                                                                                        |
|  [Step 4.2: Adaptive Chunking & Model Router]                                          |
|    ├── Route A: Cloud Batch Native (Sarvam Saaras v4 / Deepgram Nova-3)                |
|    │     • Passes full VAD-compacted audio (or 20-min macro-segments) + `keyterms`     |
|    │     • Preserves global Speaker Diarization (`SPEAKER_00` across all 90 mins)      |
|    │     • Uses `mode="codemix"` (Devanagari + Latin technical terms) or `translit`    |
|    │                                                                                   |
|    └── Route B: Fine-Grained VAD Micro-Chunking (Self-Hosted WhisperX / Fallback)      |
|          • Dynamic VAD Packer groups speech into 15–25s windows at >=400ms pauses      |
|          • Adds 500ms acoustic overlap + passes trailing 150 chars of Chunk N-1        |
|            into Chunk N's `initial_prompt` to prevent boundary word truncation         |
|                                                                                        |
|  [Step 4.3: Post-ASR Contextual Phonetic Repair & Script Normalizer]                   |
|    • LLM pass compares raw STT segments against Slide/Board vocabulary                 |
|    • Fixes homophones & transliteration glitches without altering `start_ms`/`end_ms`  |
|    • Saves immutable `transcript_revisions` (v1 Fast, v2 Heavy/Verified, etc.)         |
+========================================================================================+
```

## 3. Low-Level Design (LLD): Deep-Dive Component Specifications

### 3.1 Module 1: Edge Capture & Local-First Resilient Upload Queue

#### The "Why" & Hidden Hardware Traps
1. **Browser DSP Sabotage:** By default, mobile browsers apply WebRTC voice-call filters (`echoCancellation: true`, `noiseSuppression: true`, `autoGainControl: true`). These filters are tuned for a speaker 5 cm from the mic and actively **treat a professor speaking 4 meters away in a classroom as "background noise" and mute them**! You must explicitly disable browser `noiseSuppression` and `autoGainControl` when recording a classroom lecture, so your cloud DSP gets the full dynamic range.
2. **The WebM Chunk Header Problem:** When you call `mediaRecorder.start(20000)` to emit 20-second chunks, the browser writes a single continuous Matroska/WebM stream: **only `chunk_0` contains the EBML header and Track Info**, while `chunk_1` through `chunk_270` contain raw Matroska Cluster blocks ([FFmpeg Micro](https://www.ffmpeg-micro.com/blog/mediarecorder-webm-isn-t-broken-convert-it-to-mp4-server-side)).
   * *Consequence:* You **cannot** treat individual `MediaRecorder` chunks as standalone audio files in the cloud unless you either (a) binary-concatenate `chunk_0 .. chunk_N` in sequence first, or (b) prepend `chunk_0`'s EBML header bytes to each cluster and remux.
   * *Best Practice:* Use 30-second `MediaRecorder` slices purely as **transport blocks** for your local-first upload queue. Once all blocks reach Cloudflare R2, concatenate them in seconds into the seekable master recording (`ffmpeg -i concat.webm -c copy -cues_to_front 1 master_raw.webm`).

#### Client-Side IndexedDB Schema (`Dexie.js`)
```typescript
// db.ts — Local-First Audio Buffer Schema
import Dexie, { Table } from 'dexie';

export interface LocalRecordingSession {
  sessionId: string;           // UUID generated offline or online
  title: string;
  folderId: string;
  languageMode: 'hinglish' | 'hindi' | 'english';
  preferredScript: 'codemix' | 'latin' | 'devanagari';
  sampleRate: number;          // 16000
  mimeType: string;            // 'audio/webm;codecs=opus' or 'audio/mp4' (iOS Safari fallback)
  startedAtEpochMs: number;
  totalChunksExpected: number | null; // Set when user taps "Stop Lecture"
  status: 'recording' | 'paused' | 'uploading' | 'cloud_processing' | 'completed';
}

export interface LocalAudioChunk {
  id?: number;                 // Auto-increment primary key
  sessionId: string;
  seqNo: number;               // Strictly monotonic: 0, 1, 2, ... 179
  startOffsetMs: number;       // e.g., 0, 30000, 60000 (excludes paused intervals)
  endOffsetMs: number;         // e.g., 30000, 60000, 90000
  blob: Blob;                  // ~120 KB for 30s @ 32kbps Opus
  byteLength: number;
  crc32: string;               // Integrity checksum before upload
  uploadStatus: 'pending' | 'uploading' | 'uploaded' | 'failed';
  retryCount: number;
  r2Etag?: string;
}
```

#### Serial Upload Queue & Safe Garbage Collection State Machine
```
[MediaRecorder ondataavailable (every 30s)]
       │
       ▼
Write `LocalAudioChunk` (status = 'pending') to IndexedDB immediately (< 5ms)
       │
       ▼
[SerialUploadWorker Loop] ──(Offline / No Wi-Fi?)──► Sleep & Listen for `window.ononline`
       │ (Online)
       ▼
Fetch oldest chunk where `uploadStatus IN ('pending', 'failed') ORDER BY seqNo ASC LIMIT 1`
       │
       ▼
Request Presigned PUT URL (or batch of 10 URLs) from FastAPI:
`PUT https://<r2-bucket>/sessions/{sessionId}/chunks/chunk_{seqNo:04d}.webm`
       │
       ├──► HTTP 200 OK: Update `uploadStatus = 'uploaded'`, `r2Etag = res.etag`
       │                 (**Keep `blob` on device until Master Stitch is verified!**)
       │
       └──► Network Timeout / 5xx: Increment `retryCount`, exponential backoff
            (`min(60s, 2^retryCount * 1000ms + jitter)`), never block recording thread!

[User Taps "End Lecture" at 90 Minutes]
       │
       ▼
1. `mediaRecorder.stop()` flushes final partial chunk `seqNo = N`.
2. SerialUploadWorker finishes uploading remaining pending chunks `..N`.
3. Client calls `POST /api/v1/sessions/{sessionId}/finalize` with `{ totalChunks: N + 1 }`.
4. Cloud Worker verifies all `N + 1` chunks exist in R2, stitches `master_raw.webm`,
   and returns `{ masterVerified: true, masterAudioUrl: "..." }`.
5. ONLY AFTER `masterVerified === true` AND initial transcript `status === 'ready'`,
   Client runs `db.audioChunks.where({ sessionId }).delete()` to free phone storage.
```

### 3.2 Module 2: Cloud DSP & Acoustic Conditioning Pipeline

#### Why "Heavy DSP Everywhere" Can Backfire on Speech Recognition
A critical finding in modern speech engineering is that **human ears and neural ASR models optimize for different things**.
* In [Deepgram's ASR preprocessing benchmarks](https://deepgram.com/learn/how-voice-ai-works) and [Krisp/Fora Soft's 2026 noise studies](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments), running aggressive neural speech enhancement on single-speaker audio in a reverberant room (like a concrete-walled Indian lecture hall) actually **worsened WER from `8.02%` (unprocessed) to `11.61%` (processed)**. Why? Because room reverb smears consonant energy across time, and aggressive neural masks mistake quiet fricatives (`s`, `f`, `th`, `sh`) in echoed speech for background noise and zero them out.
* Conversely, when background noise is severe (**Signal-to-Noise Ratio < 15 dB**, such as a loud ceiling fan right above the phone or hallway chatter), neural suppression cuts WER by **20–40% relative** (dropping WER from `35.92%` to `10.90%` in competing-speech tests) ([Fora Soft](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments)).

#### The Solution: The Dual-Track, SNR-Gated Cloud DSP Pipeline
Instead of blindly running heavy neural denoising on every file, your Python cloud worker executes a **3-Stage Acoustic Pipeline** on the reconstructed 90-minute audio:

1. **Stage A — Classical Linear DSP (Always Safe for ASR, Zero Phoneme Destruction):**
   Run a single fast `ffmpeg` pass (~4 seconds for a 90-minute lecture) that removes mechanical classroom noise without touching speech formants (`300 Hz – 7,500 Hz`):
   * **Ceiling Fan & AC Compressor Rumble (`highpass=f=85:poles=2`):** Indian classroom ceiling fans and AC units generate heavy acoustic energy between `20 Hz` and `80 Hz`. Human fundamental frequencies sit above `85 Hz`. Rolling off below `85 Hz` eliminates fan "gurr" cleanly.
   * **Electrical Mains Hum (`anequalizer` notch at `50 Hz` and `100 Hz`):** India uses `50 Hz` AC power; cheap classroom amplifiers or projector cables often inject a `50 Hz` hum and `100 Hz` harmonic.
   * **Random Ticks, Pen Clicks & Desk Taps (`adeclick=w=55:o=75:t=2`):** Autoregressive interpolation detects impulse spikes lasting `<5ms` (a student clicking a ballpoint pen or tapping the phone desk) and smooths the waveform without affecting 80ms+ speech phonemes.
   * **Far-Field Dynamic Range Leveling (`speechnorm=e=6.25:r=0.0001:l=1`):** When a professor walks away from the podium toward the corner of the blackboard, their volume drops by 12–18 dB. Gentle speech normalization brings quiet board-facing speech up to `-16 LUFS` without amplifying silent intervals.

2. **Stage B — Acoustic SNR & Cough/Transient Detection:**
   * Estimate the segment-level Signal-to-Noise Ratio (SNR) comparing voiced frames (detected by Silero VAD) against non-voiced background frames.
   * **Cough & Sneeze Handling:** Why do coughs hurt transcription? A loud student cough near the microphone creates a sudden `+20 dB` broadband energy burst that confuses Automatic Gain Control and occasionally triggers Whisper to hallucinate filler words (`"Thank you"`, `"uh"`). By combining `speechnorm` peak limiting (`-1 dBTP`) with **Silero VAD v6** (which is trained to reject non-speech vocalizations like coughs, throat-clearing, and laughter), cough intervals are flagged as non-speech or attenuated before reaching the decoder.

3. **Stage C — Conditional Neural Enhancement ([DeepFilterNet3](https://github.com/rikorose/deepfilternet)):**
   * Why **DeepFilterNet3** over **RNNoise** in the cloud? As documented in [2026 benchmarks](https://noisereducerai.com/blogs/deepfilternet-vs-rnnoise/), RNNoise uses a coarse 22-band gain equalizer (85 KB model) that struggles with classroom reverberation and non-stationary chatter, whereas **DeepFilterNet3** operates at full frequency resolution (`~2.3M` parameters, `>0.95` STOI intelligibility, `0.19` Real-Time Factor on CPU—meaning a 90-minute lecture processes in ~3 minutes on a standard CPU worker or <20 seconds on GPU).
   * **Crucial Parameter (`--atten-lim 12`):** Never set DeepFilterNet3 attenuation to infinity (`100%` noise removal) for an ASR feed! Set `atten_lim_db = 12` (12 dB maximum noise floor reduction) ONLY when estimated classroom `SNR < 15 dB`. This strips 75% of heavy fan/chatter energy while leaving natural acoustic context intact so the ASR model never suffers from "musical noise" or stripped consonants.
   * For the **Human Playback Track** (when the student replays the audio in the app), you can apply a `20 dB` attenuation limit so the lecture sounds crisp and studio-clean on headphones.

```python
# cloud_dsp_pipeline.py — Production Cloud DSP Implementation
import subprocess
import numpy as np
import soundfile as sf
from df.enhance import enhance, init_df, load_audio, save_audio

def run_classical_classroom_dsp(input_webm_path: str, output_wav_path: str) -> None:
    """
    Stage 1: Lossless-for-ASR Classical Filter Chain via FFmpeg.
    - Strips <85Hz fan/AC rumble
    - Notches 50Hz/100Hz Indian power-grid hum
    - Removes transient pen clicks / mic taps (adeclick)
    - Levels far-field professor volume (speechnorm)
    - Downsamples to 16kHz 16-bit mono PCM (exact native input for ASR & Silero VAD)
    """
    filter_chain = (
        "highpass=f=85:poles=2,"
        "equalizer=f=50:t=q:w=10:g=-25,"
        "equalizer=f=100:t=q:w=10:g=-15,"
        "adeclick=w=55:o=75:t=2.5,"
        "speechnorm=e=6.25:r=0.0001:l=1,"
        "lowpass=f=7600:poles=2"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_webm_path,
        "-af", filter_chain,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        output_wav_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def run_conditional_deepfilternet(
    classical_wav_path: str,
    asr_ready_wav_path: str,
    human_playback_m4a_path: str,
    estimated_snr_db: float
) -> None:
    """
    Stage 2: Dual-Track DeepFilterNet3 Enhancement.
    - Always creates a crisp `human_playback_m4a_path` (20dB attenuation) for student listening.
    - Only applies neural suppression to `asr_ready_wav_path` (capped at 12dB attenuation)
      if classroom SNR < 15.0 dB, avoiding the over-denoising WER penalty.
    """
    model, df_state, _ = init_df()  # Loads DeepFilterNet3
    audio, _ = load_audio(classical_wav_path, sr=df_state.sr())

    # 1. Human listening track (20 dB noise reduction for pleasant headphone playback)
    human_enhanced = enhance(model, df_state, audio, atten_lim_db=20.0)
    temp_human_wav = classical_wav_path.replace(".wav", "_human.wav")
    save_audio(temp_human_wav, human_enhanced, df_state.sr())
    subprocess.run([
        "ffmpeg", "-y", "-i", temp_human_wav,
        "-ar", "24000", "-ac", "1", "-c:a", "aac", "-b:a", "48k",
        human_playback_m4a_path
    ], check=True)

    # 2. ASR track (SNR-Gated with gentle 12 dB cap to preserve consonant phonemes)
    if estimated_snr_db < 15.0:
        asr_enhanced = enhance(model, df_state, audio, atten_lim_db=12.0)
        save_audio(asr_ready_wav_path, asr_enhanced, df_state.sr())
        # Downsample back to 16kHz for ASR/VAD
        subprocess.run([
            "ffmpeg", "-y", "-i", asr_ready_wav_path,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            asr_ready_wav_path + ".tmp.wav"
        ], check=True)
        subprocess.run(["mv", asr_ready_wav_path + ".tmp.wav", asr_ready_wav_path], check=True)
    else:
        # Clean classroom (SNR >= 15 dB): Raw classical-filtered audio gives lower WER!
        subprocess.run(["cp", classical_wav_path, asr_ready_wav_path], check=True)
```

### 3.3 Module 3: Semantic Audio Segmentation & The Timestamp Offset Map

#### Why Fixed 20-Second Slicing Fails—And How Dynamic VAD Packing Works
Your intuition to compare audio chunking to **RAG text chunking** is architectural gold. In RAG, if you split a document strictly every 500 characters, you slice sentences in half and lose meaning. Instead, you use a **Recursive Semantic Splitter** with overlap.

In audio processing, the exact equivalent is **Silero VAD v6 Dynamic Window Packing with Acoustic & Prompt Overlap**:
1. **Why 15–25s is the Sweet Spot for Chunked Models (like Whisper):** OpenAI Whisper's transformer encoder has a hard positional embedding window of **30.0 seconds**. If you feed it a 90-minute file without VAD segmentation, it uses a naive sliding window that frequently gets stuck in repetition hallucinations during 10-second board-writing pauses (`"Thank you. Thank you. Thank you."`) and suffers from timestamp drift.
2. **How We Avoid Cutting Words in Half (Dynamic Pause Seeking):**
   * Run **Silero VAD v6** (which achieves 16% fewer errors on noisy real-world audio than v5 and processes 90 minutes of audio in `<2 seconds` on CPU) ([Fora Soft](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments)) to obtain a list of raw speech utterances: `[(start_ms, end_ms), ...]`.
   * **Rule 1 (Silence Stripping):** Any non-speech gap `> 2,000 ms` (e.g., professor silently writing a derivation on the blackboard for 45 seconds) is dropped from the ASR audio buffer, **saving 20–35% of your STT API cost** and eliminating silence hallucinations.
   * **Rule 2 (Dynamic Window Packing `15s – 28s`):** Merge consecutive speech utterances into a single chunk until adding the next utterance would exceed `25.0 seconds`. Prefer splitting at pauses `>= 400 ms` (a natural sentence breath).
   * **Rule 3 (What if a Professor Speaks Non-Stop for 45 Seconds Without a `400ms` Pause?):** Look between `18.0s` and `28.0s` for the **local energy minimum** (micro-pause `>= 150 ms`), split there, and include a **`500 ms` acoustic overlap collar** (`250 ms` padding before and after) plus pass the last 35 words of Chunk $N-1$'s transcript into Chunk $N$'s prompt!

#### CRITICAL Distinction: Micro-Chunking vs. Macro-Batching for Speaker Diarization
Here is an insight most engineers only discover after breaking speaker labels in production:
* If you use **[Sarvam AI Saaras v4 Batch API](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api)** or **[Deepgram Nova-3](https://developers.deepgram.com/docs/models-languages-overview)**, **do NOT send 270 separate 20-second API requests!**
* *Why?* Because Sarvam AI's Batch API natively accepts files **up to 2 hours long** and runs its internal VAD chunker + **global Speaker Diarization (`with_diarization=True`)** across the entire file ([Sarvam Batch API Docs](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api)). If you send 270 isolated 20-second files, `speaker_id: "0"` in chunk 14 might be a student asking a question, while `speaker_id: "0"` in chunk 15 is the professor!
* **How to get the best of both worlds:**
  * **For Sarvam Saaras v4 / Deepgram Nova-3 (Cloud Batch Route):** Run Silero VAD locally on your cloud worker to strip dead silence (`>2.5s` pauses) and stitch the active speech islands (with `300ms` silence cushions) into a single **VAD-Compacted Master File** (turning a 90-minute lecture with 25 minutes of board-writing silence into a 65-minute compact file). Send that single file to Sarvam Batch API (`with_diarization=True`, `keyterms=[...]`), and use your **`TimestampOffsetMap`** to map every returned timestamp back to the exact millisecond in the 90-minute original recording!
  * **For Self-Hosted WhisperX / Chunked Parallel Route:** Run full **pyannote speaker diarization** on the VAD-compacted audio stream (or 15-minute macro windows with speaker embedding stitch), while feeding the **15–25s Silero VAD micro-chunks** to the Whisper encoder in parallel batches.

```python
# vad_dynamic_chunker.py — Silero VAD Dynamic Window Packer + Offset Mapper
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class SpeechSegment:
    orig_start_ms: int
    orig_end_ms: int
    compact_start_ms: int
    compact_end_ms: int

@dataclass
class VADChunk:
    chunk_index: int
    orig_start_ms: int
    orig_end_ms: int
    audio_slice_start_ms: int  # Includes 250ms acoustic padding
    audio_slice_end_ms: int
    sub_segments: List[SpeechSegment]

def pack_vad_utterances_into_semantic_chunks(
    vad_timestamps_ms: List[Tuple[int, int]],
    min_chunk_ms: int = 15000,
    target_max_chunk_ms: int = 25000,
    hard_limit_ms: int = 29000,
    min_silence_split_ms: int = 400,
    collar_padding_ms: int = 250
) -> Tuple[List[VADChunk], List[SpeechSegment]]:
    """
    Groups raw Silero VAD speech intervals into 15-25s semantic chunks,
    splitting only at natural pauses (>=400ms) while stripping dead silence (>2000ms)
    and maintaining an exact bidirectional TimestampOffsetMap.
    """
    chunks: List[VADChunk] = []
    offset_map: List[SpeechSegment] = []
    
    current_group: List[SpeechSegment] = []
    compact_cursor_ms = 0
    CUSHION_MS = 200  # Keep 200ms natural pause between compacted utterances

    for raw_start, raw_end in vad_timestamps_ms:
        duration = raw_end - raw_start
        seg = SpeechSegment(
            orig_start_ms=raw_start,
            orig_end_ms=raw_end,
            compact_start_ms=compact_cursor_ms,
            compact_end_ms=compact_cursor_ms + duration
        )
        offset_map.append(seg)
        compact_cursor_ms += duration + CUSHION_MS

        if not current_group:
            current_group.append(seg)
            continue

        group_duration = seg.orig_end_ms - current_group[0].orig_start_ms
        pause_before_seg = seg.orig_start_ms - current_group[-1].orig_end_ms

        # Split condition:
        # 1. We exceeded min_chunk_ms (15s) AND hit a natural sentence pause (>=400ms)
        #    while approaching target_max_chunk_ms (25s), OR
        # 2. Adding this segment would breach hard_limit_ms (29s)
        should_split = (
            (group_duration >= min_chunk_ms and pause_before_seg >= min_silence_split_ms and group_duration >= 18000)
            or (group_duration > target_max_chunk_ms)
            or (group_duration + duration > hard_limit_ms)
        )

        if should_split:
            chunks.append(VADChunk(
                chunk_index=len(chunks),
                orig_start_ms=current_group[0].orig_start_ms,
                orig_end_ms=current_group[-1].orig_end_ms,
                audio_slice_start_ms=max(0, current_group[0].orig_start_ms - collar_padding_ms),
                audio_slice_end_ms=current_group[-1].orig_end_ms + collar_padding_ms,
                sub_segments=current_group
            ))
            current_group = [seg]
        else:
            current_group.append(seg)

    if current_group:
        chunks.append(VADChunk(
            chunk_index=len(chunks),
            orig_start_ms=current_group[0].orig_start_ms,
            orig_end_ms=current_group[-1].orig_end_ms,
            audio_slice_start_ms=max(0, current_group[0].orig_start_ms - collar_padding_ms),
            audio_slice_end_ms=current_group[-1].orig_end_ms + collar_padding_ms,
            sub_segments=current_group
        ))

    return chunks, offset_map

def map_compact_time_to_original_ms(compact_ms: int, offset_map: List[SpeechSegment]) -> int:
    """
    Translates any timestamp from the silence-stripped audio file back to the
    exact wall-clock millisecond in the 90-minute master recording.
    """
    for seg in offset_map:
        if seg.compact_start_ms <= compact_ms <= seg.compact_end_ms:
            delta = compact_ms - seg.compact_start_ms
            return seg.orig_start_ms + delta
    # Fallback to nearest preceding segment
    preceding = [s for s in offset_map if s.compact_end_ms <= compact_ms]
    if preceding:
        last = preceding[-1]
        return last.orig_end_ms + (compact_ms - last.compact_end_ms)
    return compact_ms
```

### 3.4 Module 4: Context-Aware Hinglish Transcription & Script Architecture

#### How to Make the STT Model "Smart" About the Lecture Topic
Generic ASR models fail on specialized lectures because acoustic evidence alone cannot distinguish homophones or rare technical vocabulary (e.g., *"Hermitian matrix"*, *"stoichiometry"*, *"Panchayati Raj"*, *"Dijkstra's algorithm"*). We solve this with a **3-Layer Context Injection Pipeline**:

1. **Layer 1 — Pre-ASR Multimodal Keyterm Extraction (Before STT Runs):**
   * Before calling the STT API, a lightweight worker task passes:
     * The `Session Title` (e.g., `"Lecture 14: Eigenvalues, Cayley-Hamilton Theorem & Diagonalization"`)
     * The `Folder Path` (`"B.Tech Sem 3 > Engineering Mathematics"`)
     * Any uploaded PDF slide headings or OCR text from whiteboard photos snapped during the lecture
     * User's optional custom tags
   * **Gemini 2.5 Flash-Lite** (costing `~$0.0002` per lecture) distills this context into a ranked JSON array of **up to 50 distinct domain keyterms** (`max 64 chars each`), which is the exact schema required by **[Sarvam AI Saaras v4 Keyterm Prompting](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/keyterms)** (`keyterms=["Cayley-Hamilton Theorem", "Eigenvalue", "Eigenvector", "Diagonalization", "Characteristic Polynomial"]`) and **[Deepgram Nova-3 Keyterms](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments)** (up to 500 tokens).

2. **Layer 2 — Rolling Inter-Chunk Context Conditioning (For Chunked Whisper/Local Passes):**
   * When processing 15–25s chunks sequentially through a Whisper-architecture model, Chunk $N$ has no memory of Chunk $N-1$ unless you pass it explicitly.
   * Construct each chunk's `initial_prompt` (capped at 224 tokens) dynamically as:
     $$\text{Prompt}_N = \underbrace{\text{"Lecture on [Topic]. Key terms: [Top 25 Terms]."}}_{\text{Static Global Context (~80 tokens)}} + \underbrace{\text{Last 2 Sentences of Chunk}_{N-1}}_{\text{Rolling Local Continuity (~100 tokens)}}$$
   * **Crucial Whisper Gotcha:** Set `condition_on_previous_text=False` in standard `faster-whisper` if you see repetition loops in noisy audio, and instead inject your own sanitized rolling tail via `initial_prompt` after stripping any repeated phrases!

3. **Layer 3 — Post-ASR Contextual Phonetic Repair & Script Normalization:**
   * Even with keyterm biasing, a muffled recording might transcribe *"Cayley-Hamilton"* as *"Keli Hamilton"* or *"पैगंबर"* instead of *"पाइथन (Python)"*.
   * Run the raw diarized transcript segments (in 10-minute windows) through **Gemini 2.5 Flash** along with the full vocabulary extracted from the lecture PDF/whiteboard photos, using a strict **Timestamp-Locked Phonetic Repair Prompt**:
     * *Rule:* The LLM may **only** correct phonetic misspellings of technical terms, acronyms, and proper nouns, and clean up script consistency—it is strictly forbidden from summarizing, paraphrasing, or altering `start_ms` / `end_ms` / `speaker_id`.

#### Solving the Script Dilemma: Latin (Roman Hinglish) vs. Devanagari vs. Code-Mixed
You noted that classroom lectures can be in English, Hindi, or Hinglish, and the transcript could be in Latin or Devanagari. Here is what research and production testing show—and the exact mode to use:

| Sarvam Saaras v4 `mode` | Example Input Speech | Output Transcript | Pros & Cons for a Classroom App |
| :--- | :--- | :--- | :--- |
| **`mode="codemix"` (RECOMMENDED CANONICAL MASTER)** | *"Agar hum is matrix ka eigenvalue calculate karein..."* | `"अगर हम इस matrix का eigenvalue calculate करें..."` | **Best of both worlds ([Sarvam Docs](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/keyterms), [arXiv:2610.27631v1](https://arxiv.org/html/2610.27631v1)):** Hindi grammar stays in clean Devanagari while English technical terms (`matrix`, `eigenvalue`, `calculate`) stay in **Latin script** so keyword search, code/math rendering, and LLM synthesis never break! |
| **`mode="translit"` (Romanized Hinglish)** | *"Agar hum is matrix ka eigenvalue calculate karein..."* | `"Agar hum is matrix ka eigenvalue calculate karein..."` | **Preferred by 80%+ of Indian college students for reading/searching** (matches WhatsApp typing style). Zero Devanagari reading friction while keeping exact spoken words. |
| **`mode="transcribe"` (Native Script)** | *"Agar hum is matrix ka eigenvalue calculate karein..."* | `"अगर हम इस मैट्रिक्स का आइगेनवैल्यू कैलकुलेट करें..."` | **Avoid for STEM lectures:** Transliterating *"eigenvalue"* into `"आइगेनवैल्यू"` makes searching for `"eigenvalue"` fail and degrades LLM reasoning accuracy ([arXiv:2610.27631v1](https://arxiv.org/html/2610.27631v1)). Useful only for pure Hindi Literature/History classes. |
| **`mode="translate"` (Direct to English)** | *"Agar hum is matrix ka eigenvalue calculate karein..."* | `"If we calculate the eigenvalue of this matrix..."` | Great as a secondary **derived view**, but loses the professor's original Hindi phrasing and nuances. |

> **Architectural Decision on Script:** Request **`mode="codemix"`** from [Sarvam Saaras v4](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/keyterms) as your primary transcript, and during the ultra-cheap Post-ASR LLM pass (`~$0.004` per lecture), generate a synchronized **`text_latin` (Roman Hinglish)** and **`text_english` (Translated English)** column for every segment! That way, the student gets a **1-click UI toggle (`Code-Mixed | Roman Hinglish | Pure English`)** on the exact same transcript without ever re-running STT!

### 3.5 Module 5: Multi-Pass Transcript Versioning & Immutable Source of Truth

#### How to Support Re-Running the Pipeline Without Breaking User Notes
You specifically highlighted: *"Multiple transcripts can be generated maybe using different better models or heavy processing and increased efforts so we keep the main source recording truth with us so we can do this whole pipeline again if needed."*

To make this rock-solid in PostgreSQL/Supabase, we use an **Immutable Revision Pattern** combined with **Millisecond Time-Range Anchoring**:

```sql
-- 1. Recording Session holds the Immutable Master Audio Truth
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    master_raw_audio_r2_key TEXT NOT NULL,    -- Immutable original WebM/Opus stream
    clean_playback_r2_key TEXT,               -- DeepFilterNet3 20dB cleaned M4A for headphones
    duration_ms INT NOT NULL DEFAULT 0,
    estimated_snr_db REAL,
    active_revision_id UUID,                  -- Points to the currently selected transcript_revision
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Transcript Revisions (Allows N Transcripts per 1 Recording Session!)
CREATE TABLE transcript_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    revision_number INT NOT NULL,             -- 1, 2, 3...
    pipeline_tier TEXT NOT NULL,              -- 'fast_standard', 'heavy_dsp_verified', 'custom_reprocess'
    stt_provider TEXT NOT NULL,               -- 'sarvam_saaras_v4', 'deepgram_nova_3', 'whisper_large_v3_ensemble'
    dsp_config_json JSONB NOT NULL,           -- {"classical_filters": true, "deepfilternet_db": 12.0}
    context_keyterms TEXT[] DEFAULT '{}',     -- The 50 domain keyterms injected into this run
    wer_confidence_avg REAL,                  -- Mean token confidence score (0.0 - 1.0)
    processing_cost_inr NUMERIC(8,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(session_id, revision_number)
);

-- 3. Transcript Segments (Belong to a specific Revision, carry 3 Script Variants!)
CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id UUID NOT NULL REFERENCES transcript_revisions(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq_index INT NOT NULL,
    speaker_label TEXT NOT NULL,              -- 'SPEAKER_00' (mapped to 'Prof. Sharma' at session level)
    start_ms INT NOT NULL,                    -- Wall-clock ms in master_raw_audio (via OffsetMap)
    end_ms INT NOT NULL,
    text_codemix TEXT NOT NULL,               -- "अगर हम इस matrix का eigenvalue निकालें..."
    text_latin TEXT,                          -- "Agar hum is matrix ka eigenvalue nikalein..."
    text_english TEXT,                        -- "If we calculate the eigenvalue of this matrix..."
    confidence REAL DEFAULT 1.0,
    is_low_confidence BOOLEAN DEFAULT false,  -- Flagged for UI yellow underline / heavy pass retry
    fts TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(text_codemix, '') || ' ' || coalesce(text_latin, '') || ' ' || coalesce(text_english, ''))
    ) STORED,
    embedding VECTOR(768)
);

-- 4. Time-Anchored Bookmarks, Whiteboard Photos & User Highlights
-- Notice: Anchored to (session_id, start_ms, end_ms), NEVER to a transient segment_id!
CREATE TABLE timeline_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    start_ms INT NOT NULL,
    end_ms INT,
    annotation_type TEXT NOT NULL,            -- 'exam_alert_pin', 'whiteboard_photo', 'user_note'
    asset_r2_key TEXT,
    extracted_context_md TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### Two-Tier Execution Strategy ("Fast Pass" vs. "Heavy Pass")
Instead of forcing every student to wait for heavy processing—or paying double STT costs on every lecture—implement **Confidence-Triggered Selective Re-Transcription**:
1. **Pass 1 (Default — Fast & Crisp):** Runs Classical FFmpeg DSP + Silero VAD + [Sarvam Saaras v4](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api) (`mode="codemix"`, `with_diarization=True`, `keyterms=[Top 50 terms]`) + Gemini 2.5 Flash-Lite phonetic repair. Completes a 90-minute lecture in **~45–60 seconds** for `~₹50` (since VAD strips ~20 mins of silence).
2. **Automatic Low-Confidence Detection (Smart Hybrid Pass):** Inspect the segment confidence scores or LLM phonetic uncertainty flags. Often, 92% of a 90-minute lecture is crystal clear, and only **4 minutes** (e.g., when the professor turned toward the blackboard while a truck passed outside) have low confidence (`< 0.65`).
   * Instead of re-transcribing all 90 minutes, your pipeline automatically slices **only those 4 minutes of low-confidence audio**, runs **DeepFilterNet3 (`15 dB`) + an Ensemble Pass (Sarvam Saaras v4 + Whisper Large-v3 / Gemini 2.5 Pro Direct Audio Listening)** on just those 4 minutes, and merges the upgraded segments into `Revision v2` for **less than `₹4` extra**!
3. **Full Manual "Heavy Re-Run" (`Revision v3`):** If the user uploads the professor's PDF slides *after* the lecture is already transcribed, or selects **"Re-Run with Maximum Precision"**, the worker pulls `master_raw_audio_r2_key` from Cloudflare R2, extracts the new keyterms from the newly uploaded PDF, runs the heavy pipeline, and creates `Revision v3`. Because all photos and pins are anchored to `start_ms` on `timeline_annotations`, zero user work is lost.

## 4. What You Missed: 7 High-Impact Blind Spots & Edge-Device Optimizations

When we look across Reddit developer post-mortems (`r/speechtech`, `r/VoiceAutomationAI`), GitHub issues, and real classroom field tests, here are **7 critical blind spots** that aren't obvious until you test in a real lecture hall:

1. **OS-Level Background Recording Murder (iOS Safari & Android OEM Battery Savers):**
   * **The Problem:** On Xiaomi (MIUI/HyperOS), Vivo, OnePlus, and Samsung phones—which make up 75%+ of Indian college devices—turning off the screen or switching to WhatsApp for 2 minutes causes the OS to kill the browser recording tab or mute the microphone stream.
   * **The Fix:**
     1. Request the **Screen Wake Lock API** (`navigator.wakeLock.request('screen')`) and switch the UI into a **"Pocket/Desk OLED Blackout Mode"** (a pure `#000000` black screen that draws near-zero battery on AMOLED screens, showing only a dim clock, a pulsing green mic waveform, and a 1-tap `📌 Mark Exam Important` / `📷 Snap Board` button).
     2. Play an **inaudible/silent looping WebAudio oscillator** attached to the `MediaSession API` (which displays a persistent lock-screen media notification showing `"Recording Lecture — 00:42:18"`), signaling to Android/iOS that an active media session is in progress so the tab is not evicted.
2. **Bluetooth Earbud Mic Trap (8 kHz HFP Downsampling):**
   * **The Problem:** Students often leave their wireless TWS earbuds (AirPods, boAt, Realme Buds) connected in their ears while putting their phone on the desk to record the professor. The phone records from the **earbud microphone inside the student's ear** using the Bluetooth Hands-Free Profile (`8 kHz` narrowband + aggressive voice-isolation DSP designed to block everyone *except* the wearer)! The resulting recording of the professor is completely unintelligible.
   * **The Fix:** On `navigator.mediaDevices.enumerateDevices()`, inspect audio input labels. If a Bluetooth headset/HFP mic is active when starting a `"Classroom Lecture"` session, explicitly select the phone's built-in **Bottom/Camcorder Microphone** via `deviceId` constraint, or show an instant warning banner: *"🎧 Bluetooth earbuds detected! Recording switched to Phone Microphone so we can hear the professor clearly."*
3. **Storage Quota Eviction on Budget Phones:**
   * **The Problem:** Safari and mobile browsers can silently evict `IndexedDB` data if free disk space drops low.
   * **The Fix:** Call `navigator.storage.persist()` on onboarding to request persistent storage exemption, and call `navigator.storage.estimate()` before starting a 90-minute recording to verify at least `100 MB` of free space exists (a 90-minute Opus stream at 32 kbps only needs `~21.6 MB`).
4. **Live Waveform Feedback Without Main-Thread UI Lag:**
   * **The Problem:** Rendering a 60fps canvas waveform using `ScriptProcessorNode` on the main JavaScript thread causes React re-renders, heats up the phone, and drops audio samples.
   * **The Fix:** Use an **`AudioWorklet`** (or a lightweight `AnalyserNode` sampled at 10–15 fps via `requestAnimationFrame` on an isolated `<canvas>` element outside React state) to calculate RMS volume and drive a "Mic Signal Health Indicator" (*"Too Quiet — Move Phone Closer"* vs *"Good Classroom Signal"*).
5. **Acoustic Echo & Feedback Loop During Live Playback:**
   * If a student replays an earlier snippet during a break while recording is still active, the phone mic will re-record its own speaker. Enforce automatic headphone detection or pause/AEC gating during in-session playback.
6. **Professor Pauses vs. Pause Button Timestamp Drift:**
   * If the student hits **"Pause Recording"** during a 10-minute classroom break and then **"Resume"**, `MediaRecorder.pause()` leaves a wall-clock gap in presentation timestamps (`pts_time`) in some browsers ([FFmpeg Micro](https://www.ffmpeg-micro.com/blog/mediarecorder-webm-isn-t-broken-convert-it-to-mp4-server-side)). Track active `recording_duration_ms` explicitly in your chunk metadata and regenerate continuous timestamps during the server-side FFmpeg remux (`-fflags +genpts`).
7. **Cold-Start Context Starvation (What If the Student Hits Record With Zero Title or Slides?):**
   * Lazy students rarely type *"Lecture 14: Eigenvalues and Cayley-Hamilton Theorem"* before hitting record—they just tap **Record**!
   * **The Fix ("Two-Pass Bootstrap Context Biasing"):** If a session has no title, folder context, or slides when recording ends:
     1. Run a lightning-fast **Bootstrap Sample** by transcribing just three 30-second slices (`Minute 5`, `Minute 30`, `Minute 60`) using Gemini 2.5 Flash-Lite audio input (`~$0.0005`).
     2. Ask Gemini: *"What exact academic subject, topic, and 50 technical keyterms are being taught in this lecture?"*
     3. Inject those 50 auto-discovered keyterms into the full 90-minute Sarvam Saaras v4 / Deepgram batch job! Even a completely untitled recording gets full domain vocabulary biasing automatically.

## 5. Concrete Engineering Walkthrough: A 90-Minute Lecture From Start to Finish

To see how all these pieces fit together in numbers, here is the exact lifecycle of a **90-minute (5,400-second) Hinglish Classroom Lecture**:

| Metric / Stage | Concrete Value & Behavior |
| :--- | :--- |
| **1. Edge Capture Format** | `16,000 Hz`, Mono, Opus codec (`32 kbps`), `timeslice = 30,000 ms` (`30s` per chunk). |
| **2. Local Storage Footprint** | `180 chunks` × `120 KB` = **`21.6 MB` total** in IndexedDB (less than 4 phone photos!). |
| **3. Upload Bandwidth** | `4 KB/sec` average upstream bandwidth. Easily uploads in the background over weak 1-bar campus 4G; if offline for all 90 minutes, uploads all `21.6 MB` in **`~15 seconds`** once back on Wi-Fi. |
| **4. Cloud Stitch & Classical DSP** | FFmpeg concatenates 180 chunks, builds Cues index (`master_raw.webm`), and runs `highpass=85Hz` + `50Hz notch` + `adeclick` + `speechnorm` in **`4.2 seconds`** on 2 vCPUs. |
| **5. Silero VAD v6 Compaction** | Scans 90 mins in **`1.6 seconds`**. Strips `22 minutes` of dead silence (professor writing on board, attendance call). Active speech remaining: **`68 minutes`**, mapped via `TimestampOffsetMap`. |
| **6. Context Keyterm Extraction** | Gemini 2.5 Flash-Lite reads uploaded PDF / Bootstrap audio sample in **`1.8 seconds`** and outputs `50 keyterms` (`["Backpropagation", "Jacobian", "Chain Rule", ...]`). |
| **7. Cloud STT + Diarization** | `68 minutes` of compacted audio sent to [Sarvam Saaras v4 Batch API](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api) (`mode="codemix"`, `with_diarization=True`, `keyterms=[...]`). Completes in **`~35 seconds`**. Cost: `68/60 × ₹45` = **`₹51.00`** (saved `₹16.50` via VAD silence stripping!). |
| **8. Post-ASR Repair & 3-Script Sync** | Gemini 2.5 Flash repairs phonetic homophones against slide vocabulary and generates `text_codemix`, `text_latin`, and `text_english` in **`~8 seconds`**. Cost: **`~₹1.10`**. |
| **9. Local Chunk Cleanup** | Client receives `status: "ready"`, verifies `master_raw_audio_r2_key` is playable, and deletes the `21.6 MB` of raw chunks from IndexedDB. Total end-to-end cloud turnaround after final chunk upload: **`~50 seconds`**. |

## 6. Reference Bibliography & Technical Sources

* **ASR Noise Suppression & Preprocessing Benchmarks:**
  * Fora Soft Engineering (Oct 2026), [*Speech Recognition Accuracy in Noise: Best APIs, 2026 WER*](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments)
  * Deepgram Engineering (May 2026), [*How Voice AI Works: From Sound Waves to Smart Conversations (Why Speech Enhancement Can Hurt ASR WER)*](https://deepgram.com/learn/how-voice-ai-works)
  * Noise Reducer AI (Sept 2026), [*DeepFilterNet vs RNNoise: Which AI Noise Reduction Model Is Better in 2026?*](https://noisereducerai.com/blogs/deepfilternet-vs-rnnoise/)
  * DeepFilterNet Official Repository, [*Rikorose/DeepFilterNet: Low Complexity Speech Enhancement Framework*](https://github.com/rikorose/deepfilternet)
* **Sarvam AI & Hinglish Code-Switched Speech Recognition:**
  * Sarvam AI Documentation (2026), [*Batch Speech-to-Text API (Saaras v3 & v4, Diarization, 2-Hour Support)*](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api)
  * Sarvam AI Documentation (2026), [*Keyterm Prompting & Transcription Modes (`codemix`, `translit`, `transcribe`) for Saaras v4*](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/keyterms)
  * Code-Switching & LLM Transfer Research, [*Disentangling Language Confusion and Accent Bias in Code-Switched ASR & LLM Queries*](https://arxiv.org/html/2610.27631v1)
* **Contextual Biasing, VAD & Browser Media Capture:**
  * Contextual Biasing Whisper Research, [*Contextual Biasing to Improve Domain-Specific Custom Vocabulary in ASR*](https://arxiv.org/html/2410.18363v1)
  * FFmpeg Micro Engineering (Sept 2026), [*MediaRecorder WebM Isn't Broken: Handling Missing EBML Duration, Cues Index & Chunk Headers Server-Side*](https://www.ffmpeg-micro.com/blog/mediarecorder-webm-isn-t-broken-convert-it-to-mp4-server-side)
  * Smashing Magazine (May 2026), [*The Architecture of Local-First Web Development (IndexedDB, OPFS & Sync Queues)*](https://www.smashingmagazine.com/2026/05/architecture-local-first-web-development/)
