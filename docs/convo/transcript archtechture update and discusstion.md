In the context of the **Lazy Note** architecture, deciding how to slice and send a 90-minute classroom lecture for transcription is one of the most critical architectural decisions you will make.

  

First, you must obey **Architectural Principle 5.1: Separate Transport Chunks from Transcription Windows**:

  

- **Uploading (Transport Slicing):** On the student's phone/browser, you should **never** wait 90 minutes to upload a single giant file. If the phone battery dies at minute 85 or the tab crashes, the entire lecture is lost. Instead, the client always slices audio into **30-second transport blobs** (`MediaRecorder.start(30000)`), saves them in local IndexedDB, and uploads them serially. However, because browser WebM recording only puts the EBML container header in `chunk_0` (leaving `chunk_1` through `chunk_180` as headerless clusters), **you cannot send raw uploaded chunks directly to an STT API** without getting `Invalid Data` crashes. You must always stitch them into a verified master file in the cloud first.
    
      
    
- **Transcribing (Semantic Segmentation):** Once the 90-minute master recording is reconstructed in the cloud, how you slice it for the Speech-to-Text (STT) engine determines your **Word Error Rate (WER), speaker diarization consistency, cost, and timestamp accuracy**.
    
      
    

Below is the detailed performance comparison of the 5 duration strategies for a 90-minute lecture, backed by your project's engineering benchmarks, open-source reports (WhisperX, Silero VAD), and provider documentation (Sarvam AI Saaras v4, Deepgram Nova-3).

  

### High-Level Performance Comparison Matrix (90-Minute Lecture)

|**Segmentation Strategy**|**Speaker Diarization ("Who spoke when?")**|**Acoustic / Semantic Accuracy (WER)**|**Cost & Silence Hallucinations**|**Best Fit in Lazy Note Architecture**|
|---|---|---|---|---|
|**1. Full 90-Min File**|**Excellent** on Cloud Batch APIs (Global speaker IDs); **Fails (GPU OOM)** on self-hosted `pyannote`.|**High** on Cloud Batch APIs; **Poor** on raw Whisper (timestamp drift & repetition loops).|**Worst** if raw (you pay for 20–30 mins of silence); **Best** if VAD-compacted first.|**Best for Cloud Batch APIs** (_Sarvam Saaras v4_ / _Deepgram Nova-3_) **ONLY AFTER** stripping silence via Silero VAD.|
|**2. 30–30–30 Min (3 Macro-Blocks)**|**Broken across boundaries** (`SPEAKER_00` in Block 1 $\neq$ `SPEAKER_00` in Block 2 without embedding stitch).|**Good** (Fits within API file-size limits while keeping long conversational context).|**High cost** unless VAD-cleaned; low API request overhead (only 3 requests).|Good macro-window fallback if a provider has a strict 30-min or file-size limit, paired with voiceprint stitching.|
|**3. 10 × 9 Min (9-Min Windows)**|**Fragmented** across 9 splits unless stitched via speaker embeddings (`WeSpeaker`/`pyannote`).|**Very High for Post-ASR LLM Repair** (10-min windows fit LLM context & slide alignment).|Moderate API overhead; prevents complete job loss if one segment fails.|**Ideal for Phase 1 Prototype** & **Post-ASR LLM Phonetic Repair** windows.|
|**4. 5-Min or 1-Min Files**|**Poor** (18 to 90 isolated speaker clusters; loses track of student vs. professor).|**Moderate** (Fixed cuts every 60s slice sentences in half and lose cross-sentence context).|High HTTP overhead; fixed boundaries still include dead board-writing silence.|**Selective Retry Only:** Used to re-transcribe specific _low-confidence_ intervals (~4 mins) with heavy models.|
|**5. 15–30 Sec Chunks**|**Catastrophic ("Diarization Amnesia")** if sent as 270 isolated API calls.|**Worst** if cut at fixed 15–30s (cuts words in half); **Best for Whisper** if cut dynamically on silence via VAD.|**Saves 20–35% STT Cost** when packed via Silero VAD (drops >2s silence).|**Mandatory for Self-Hosted WhisperX** (using dynamic 15–28s VAD pauses + 0.5s overlap) & **30s Edge Transport**.|

### Deep-Dive Analysis of Each Strategy

#### 1. Full 90-Minute File (1 × 90 mins)

**How it behaves in the literature & production:**

  

- **Advantages:**
    
      
    - **Global Speaker Diarization:** Cloud batch engines like **Sarvam AI Saaras v4** (which natively supports files up to 2 hours long) and **Deepgram Nova-3** run their internal VAD and speaker clustering across the entire file at once. This guarantees that `SPEAKER_00` (e.g., Prof. Sharma) remains `SPEAKER_00` from minute 1 to minute 90.
        
          
        
    - **Zero Boundary Truncation:** Because the file isn't arbitrarily chopped, no words or sentences are sliced in half at chunk boundaries.
        
          
        
    - **Single Context Injection:** You only need to inject your Top 50 domain keyterms (extracted by Gemini 2.5 Flash-Lite) once for the entire job.
        
          
        
- **Limitations & Traps:**
    
      
    - **Paying for Dead Classroom Silence:** In a 90-minute lecture, 20 to 25 minutes are often dead silence (the professor writing derivations on the blackboard or taking attendance). Sending the raw 90-minute file bills you for all 90 minutes (~₹67.50 on Sarvam instead of ~₹51.00).
        
          
        
    - **Whisper Hallucination Loops & Timestamp Drift:** As documented across Reddit (`r/speechtech`, `r/VoiceAutomationAI`) and Whisper benchmarks, feeding a raw 90-minute file with long silent gaps into Whisper-based models causes the decoder to get stuck in repetitive hallucination loops during silence (_"Thank you. Thank you. Thank you."_) and causes timestamps to drift.
        
          
        
    - **GPU Out-Of-Memory (OOM) on Self-Hosted Models:** According to GitHub reports (`WhisperX Issue #274`), running `pyannote.audio` speaker diarization on multi-hour raw audio in a single pass triggers GPU OOM crashes.
        
          
        
- **Lazy Note Verdict:** Use a "VAD-Compacted" Full File for Cloud APIs. Run Silero VAD v6 locally on your worker (<2 seconds for 90 mins) to strip pauses >2.5s, stitch the active speech islands into a single **68-minute VAD-Compacted Master File**, send that single file to Sarvam Saaras v4 Batch API, and map timestamps back using a `TimestampOffsetMap`.
    
      
    

#### 2. 30–30–30 Minutes (3 × 30 mins)

**How it behaves in the literature & production:**

  

- **Advantages:**
    
      
    - **Bypasses Hard API Duration/Payload Limits:** If an STT provider caps uploads at 30–60 minutes or imposes strict HTTP payload size limits, 20-to-30-minute macro-blocks safely stay under the ceiling while still preserving long conversational context.
        
          
        
    - **Fault Isolation:** If a network glitch fails one batch job, you only retry 30 minutes rather than 90 minutes (especially when paired with R2 response caching).
        
          
        
- **Limitations & Traps:**
    
      
    - **Cross-Block Diarization Reset:** In Block 1 (0–30m), the professor might be labeled `SPEAKER_00` and a student `SPEAKER_01`. In Block 2 (30–60m), if a student speaks first, the API may label the student `SPEAKER_00` and the professor `SPEAKER_01`.
        
          
        
- **Lazy Note Verdict:** Use 20–30 minute macro-blocks **only if** an API's file limit forces you to split a long lecture, or to prevent OOM when running `pyannote` diarization on self-hosted GPUs. If you do this, you must stitch speaker identities across blocks using cosine similarity on speaker embeddings (`WeSpeaker` / `pyannote`).
    
      
    

#### 3. 10 × 9 Minutes (10-Minute Segments)

**How it behaves in the literature & production:**

  

- **Advantages:**
    
      
    - **The Sweet Spot for Post-ASR LLM Repair & Multimodal Sync:** While 10-minute splits are suboptimal for raw diarization, your architecture explicitly uses **10-minute windows** in **Step 6 (Post-ASR Contextual Phonetic Repair)**. Passing 10 minutes of raw transcript segments alongside the corresponding whiteboard photos (e.g., snapped at `00:42:15`) and PDF slide text to **Gemini 2.5 Flash** prevents LLM output truncation while giving it enough local context to fix homophones (_"Keli Hamilton"_ $\rightarrow$ _"Cayley-Hamilton"_).
        
          
        
    - **Easy Phase 1 Prototyping:** In your Week 2 prototype roadmap, splitting long audio via `ffmpeg` into 10-minute segments is a simple way to test APIs before building dynamic VAD compaction.
        
          
        
- **Limitations & Traps:**
    
      
    - **9× Diarization Fragmentation:** Sending 9 separate files to a diarized STT API creates 9 disconnected sets of anonymous speaker labels.
        
          
        
    - **8 Hard Boundary Cuts:** Cutting blindly at `09:00`, `18:00`, `27:00` will slice right through whatever sentence the professor is speaking at that exact second unless you split on a silence pause.
        
          
        
- **Lazy Note Verdict:** Avoid blind 10-minute audio splits for the primary Sarvam/Deepgram STT call in production (use the VAD-compacted full file instead), **but definitely use 5-to-10-minute windows for your Post-ASR LLM phonetic repair and multimodal vision alignment**.
    
      
    

#### 4. 5-Minute or 1-Minute Files (18 × 5 mins or 90 × 1 min)

**How it behaves in the literature & production:**

  

- **Advantages:**
    
      
    - **Targeted "Smart Hybrid Pass" Re-Transcription:** In Lazy Note's Two-Tier Execution Strategy, 92% of a 90-minute lecture is usually crystal clear, and only **~4 minutes** (e.g., when a truck passed outside while the professor faced the board) have low confidence (`< 0.65`). Slicing out just those **1-to-4-minute low-confidence intervals** to run heavy DeepFilterNet3 (15 dB) + an ensemble pass (Sarvam + Whisper Large-v3 / Gemini 2.5 Pro) upgrades transcript quality for less than **₹4 extra** instead of paying ₹50+ to re-run all 90 minutes.
        
          
        
- **Limitations & Traps:**
    
      
    - **Severe Context Starvation & Boundary Cuts (if used for the whole file):** Slicing a 90-minute lecture into 90 separate 1-minute files creates 89 mid-sentence cuts, destroys speaker diarization across the lecture, and floods the STT provider with 90 HTTP requests (triggering rate limits).
        
          
        
- **Lazy Note Verdict:** Never slice an entire 90-minute lecture into 1-minute or 5-minute files for initial transcription. Reserve 1-to-5-minute slicing strictly for **Confidence-Triggered Selective Re-Transcription** of noisy segments.
    
      
    

#### 5. 15-Second or 30-Second Files (180 × 30s or 360 × 15s)

This is the strategy you originally proposed in your notes (_"many STT work better on short time audio like 15 or 20s instead of working on whole big 90 min audio, similar to chunking in RAG"_). Research and production benchmarks show that this instinct is **100% right for Encoder-Decoder models (Whisper) and Network Upload, but dangerous if implemented naively**:

  

- **Where 15–30s Chunks Excel (The Advantages):**
    
      
    1. **Matches Whisper's Native 30-Second Receptive Field:** OpenAI Whisper's Transformer encoder has a hard positional embedding window of **30.0 seconds**. Feeding it pre-segmented 15–28s audio chunks completely eliminates sliding-window timestamp drift and silence hallucination loops.
        
          
        
    2. **Parallel GPU Batching (`WhisperX`):** Self-hosted `faster-whisper` / `WhisperX` achieves up to **70× real-time speed** specifically because it packs 15–30s VAD chunks into parallel GPU batches.
        
          
        
    3. **Resilient Edge Upload (30s Transport Slices):** On the client side, emitting 30-second Opus chunks (~120 KB each at 32 kbps) means only 4 KB/s bandwidth is needed, surviving campus Wi-Fi blackouts.
        
          
        
    4. **Bootstrap Context Sampling:** Transcribing just **three 30-second slices** (at Minute 5, Minute 30, and Minute 60) with Gemini 2.5 Flash-Lite (~$0.0005) allows you to auto-discover the lecture's academic topic and 50 technical keyterms when a lazy student hits "Record" without typing a title.
        
          
        
- **Where Naive 15–30s Chunks Fail (The 3 Hidden Traps):**
    
      
    1. **Global Diarization Amnesia (Cloud APIs):** If you send 270 isolated 20-second files to Sarvam AI or Deepgram, the API has zero memory between requests. `SPEAKER_00` in Chunk 14 might be a student asking a question, while `SPEAKER_00` in Chunk 15 is the professor!
        
          
        
    2. **Mid-Word Syllable Destruction (Fixed-Time Slicing):** If you cut strictly at `00:15.000`, `00:30.000`, `00:45.000` without Voice Activity Detection, you will slice technical words like _"Eigen-value"_ in half, causing the ASR model to misrecognize both halves.
        
          
        
    3. **Loss of Cross-Chunk Semantic Context:** In isolated 15s chunks, Chunk $N$ doesn't know what sentence started in Chunk $N-1$.
        
          
        

### Final Architectural Recommendation for Lazy Note

To get the best accuracy, lowest cost, and cleanest speaker labels for a 90-minute lecture, your pipeline should combine these lengths across **three distinct layers** rather than using one fixed length everywhere:

  

1. **Layer 1 — Client Upload (Fixed 30-Second Transport Blobs):**
    
      
    - Record in `16kHz Mono Opus` at `32 kbps` with `timeslice = 30000ms` (180 chunks × 120 KB = 21.6 MB).
        
          
        
    - Queue in IndexedDB and upload to Cloudflare R2. **Do not send these raw 30s chunks to STT**—stitch them with FFmpeg in the cloud into `master_raw.webm` first so the Matroska/EBML headers are valid.
        
          
        
2. **Layer 2 — Cloud STT Routing (Depends on Your Engine):**
    
      
    - **Route A — Primary Cloud Batch APIs (Sarvam Saaras v4 / Deepgram Nova-3):** Use **1 VAD-Compacted Full File (~65–70 mins)**. Run **Silero VAD v6** on the 90-minute master to strip silent intervals >2.5s (saving 20–35% on your STT bill), stitch the active speech islands into one compact file, pass it in a **single Batch API call** with `with_diarization=True` and your 50 `keyterms`, and use a `TimestampOffsetMap` to restore exact wall-clock milliseconds.
        
          
        
    - **Route B — Self-Hosted WhisperX / Chunked Fallback:** Use **Dynamic 15–28 Second VAD Micro-Chunks**. Pack speech utterances using Silero VAD up to 25–28s, split only at natural breath pauses ($\ge 400\text{ ms}$) or local energy minima ($\ge 150\text{ ms}$), add a **500 ms acoustic overlap collar**, and pass the trailing 2 sentences (~35 words) of Chunk $N-1$ into Chunk $N$'s `initial_prompt` alongside your top domain terms. Run speaker diarization globally on the compacted stream (or 15-min macro windows) rather than per 20s chunk.
        
          
        
3. **Layer 3 — Post-Processing & Retry:**
    
      
    - Use **10-Minute Transcript Windows** for the Gemini 2.5 Flash phonetic repair & 3-script synchronization pass (`text_codemix`, `text_latin`, `text_english`).
        
          
        
    - Use **1-to-4-Minute Audio Slices** to selectively re-transcribe low-confidence noisy segments without re-billing the entire 90-minute lecture.