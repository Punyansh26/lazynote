# Lazy Note Phase 2 — Product Strategy, Knowledge Workspace, Multi-Lens Note Studio, Hybrid RAG & Android Omnichannel Clipper Architecture (Review, HLD & LLD)

**Role:** Principal Systems Architect & Senior Technical Product Manager\
**Scope:** Phase 2 Post-Transcription Knowledge Architecture — Hidden-Transcript Workspace UX, Folder/Loose-File Taxonomy, Multi-Version Transcript & Multi-Lens Note Studio, Notes-First Hybrid RAG + Agentic Bot, and Android Share-Sheet "Second Brain" Clipper\
**Target Domain:** Hinglish/Hindi/English Lectures, Meetings, Pitches & Omnichannel Knowledge Capture

## 1. Executive Product & Engineering Review: Phase 2 Vision vs. Hidden Reality

In Phase 1, we solved the hardest acoustic problem: capturing 90-to-120-minute Hinglish classroom lectures and meetings reliably, stripping dead silence with [Silero VAD](https://www.forasoft.com/blog/article/speech-recognition-accuracy-noisy-environments), conditioning audio with [DeepFilterNet3](https://github.com/rikorose/deepfilternet), and generating time-aligned, speaker-diarized transcripts via [Sarvam AI Saaras v4](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/batch-api) and [Deepgram Nova-3](https://developers.deepgram.com/docs/models-languages-overview).

Phase 2 is where **Lazy Note transforms from a utility recorder into a daily-habit "Second Brain" workspace**. Your product instincts for Phase 2 are spot-on and mirror the exact trajectory of breakout AI workspace leaders like [Granola](https://www.granola.ai/blog/chat-with-meetings-search-analyze-ai-2026), [Notion AI](https://zackproser.com/blog/granola-vs-notion-ai), and Readwise Reader:

1. **Hiding the Raw Transcript by Default:** Raw transcripts are messy, repetitive, and full of spoken filler. Users do not come to read a 15,000-word verbatim log—they come for structured, scannable notes, while keeping the raw transcript and audio accessible via a `⋯` ("View Transcript") drawer or a chronological **Transcripts & Recordings Vault** tab.
2. **Flexible Organization (Nested Folders + Loose Root Files):** Forcing every quick voice memo into a rigid 4-level folder tree creates friction. Allowing **standalone "Loose Notes"** alongside structured folders (`Semester 5 → Operating Systems → Unit 2`) matches how humans actually work.
3. **1 Recording → $N$ Named Transcripts → $M$ Editable Note Lenses:** Allowing users to re-run transcription with different settings/models (named clearly, e.g., `v1 - Fast Hinglish`, `v2 - Exam Verified`) and generate multiple editable lenses (_Detailed Slide-by-Slide Explanation_, _Executive Summary_, _Flashcards_, _Interactive Quiz_, _Minutes of Meeting_) turns one recording into an entire study or project kit.
4. **Notes-Only RAG + Search + Future Agentic Actions:** Running RAG over **curated notes** rather than noisy raw transcripts dramatically increases signal-to-noise ratio—provided you engineer a safety hatch for granular details.
5. **Android Share-Sheet "Smart Knowledge Store" (Future Scope):** Letting users share Instagram Reels, YouTube videos/playlists, X/LinkedIn posts, blogs, and WhatsApp messages directly into Lazy Note from Android's native Share Sheet—along with a **"Why I saved this" user context note**—bridges classroom learning with everyday self-study.

However, when engineering these five pillars, **six subtle architectural traps** cause 90% of AI note apps to fail in production. Below is our executive review of what works, what breaks, and the exact State-of-the-Art (SOTA) fix for each pillar.

| Phase 2 Pillar                                           | Your Proposed Design                                                                                                                     | Why Your Instinct Is Spot-On                                                                                                                                                                    | The Hidden Engineering / UX Trap                                                                                                                                                                                                                                                                                                                                                                                | SOTA Production Upgrade (The Fix)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Hidden Transcript & Note-First UX**                 | Present the structured Note first; tuck the raw transcript into the `⋯` menu + a dedicated dated Transcripts/Recordings tab.             | Eliminates cognitive overload; matches [Granola's](https://zackproser.com/blog/granola-vs-notion-ai) industry-leading UX where notes take center stage and transcripts act as backing evidence. | **The "Dead Citation" Problem:** If the transcript is completely hidden in a separate menu, users reading a note bullet (_"Prof. Sharma derived the KCL equation"_) cannot verify _how_ he explained it without losing their reading scroll position.                                                                                                                                                           | **Slide-Over Evidence Drawer + Inline Timestamp Pills:** Keep the transcript hidden by default, but embed clickable `[▶ 42:15]` pills on every note heading/bullet. Clicking a pill opens a **bottom audio mini-player + right-hand slide-over transcript drawer** synced to `42:15`, while keeping the `⋯ → View Full Transcript` and global **Recordings & Transcripts Vault** tab.                                                                                                                                                                                            |
| **2. Folders, Subfolders & Loose Files**                 | Users can organize files in folders/subfolders by subject/need, OR leave them as standalone loose files in their profile.                | Zero-friction capture ("record now, organize later") while supporting semester-long or project-long deep hierarchies.                                                                           | **Recursive SQL Bottlenecks & Orphan Chaos:** Naive `parent_id` trees require expensive recursive CTEs to check permissions or filter RAG by folder; "Loose Files" quickly turn into an unsearchable 200-file junk drawer.                                                                                                                                                                                      | **`ltree` Materialized Path + Smart Auto-Filing Inbox:** Store folder paths using PostgreSQL `ltree` (`root.sem5.dbms.unit2`) so subtree queries run in `<1ms` via GiST index. Give Loose Files (`folder_id IS NULL`) a **"Smart Quick-File Banner"** where Gemini suggests: _"Move to `Sem 5 > DBMS`?"_ in 1 tap.                                                                                                                                                                                                                                                               |
| **3. Multi-Transcript & Editable Multi-Lens Notes**      | Keep multiple named transcripts per recording; generate Detailed Notes, Summaries, Flashcards, Quizzes, or MoM; allow full user editing. | Different formats need different data structures; user edits make the notes truly _theirs_.                                                                                                     | **The "AI Regeneration Wipes User Edits" Disaster:** If a student spends 30 minutes editing a Detailed Note and then clicks _"Regenerate with Transcript v2"_ or _"Add Slide Details"_, naive markdown replacement overwrites all their manual edits! Also, Quizzes/Flashcards stored as plain text cannot be practiced interactively.                                                                          | **Block-Based Editor (**[**Tiptap**](https://tiptap.dev/)**<!----> / <!---->**[**BlockNote**](https://www.blocknotejs.org/)**) + Polymorphic JSONB Schemas:** Store textual notes (Detailed, Summary, MoM) as **Block JSON + Markdown** with block-level locking (`is_user_edited: true`), and store **Flashcards/Quizzes as typed JSONB schemas** rendered in interactive UI cards (flip cards, MCQ grading, spaced repetition).                                                                                                                                                    |
| **4. "Notes-Only" RAG Bot & Search**                     | Build search and a RAG bot that answers questions strictly from stored **Notes** (with future agentic triggers like Email/Reminders).    | Notes are distilled, clean, and free of ASR stuttering, making RAG answers 3x more concise and coherent.                                                                                        | **The "Summarization Loss" Blind Spot:** A summary note inevitably omits tiny spoken details (e.g., _"The exam is in Room 304, not 302"_). If RAG _only_ searches notes, it says _"Not found"_ even though the answer is in the recording! Also, standard chunking loses document context ([Anthropic Contextual Retrieval](https://blog.vectorchord.ai/optimize-rag-with-contextual-retrieval-in-postgresql)). | **Two-Tier "Notes-Primary, Transcript-Fallback" Contextual RAG:** Default RAG retrieval (`Tier 1`) searches **Notes + User Edits** using [Supabase Hybrid Search (BM25 `tsvector` + `pgvector` HNSW + Reciprocal Rank Fusion)](https://supabase.com/docs/guides/ai/hybrid-search). If retrieval confidence is `< 0.65`, automatically trigger a `Tier 2` deep lookup into `transcript_segments` and badge the answer: _"Found in raw lecture transcript at [18:40]"_.                                                                                                            |
| **5. Agentic Future Scope (Email, Reminders, Research)** | Future bot should trigger actions like sending emails, setting reminders, or doing web research.                                         | Turns passive notes into an active executive assistant.                                                                                                                                         | **Retrofitting Agentic State Later Is Painful:** If your database and chat loop only support text-in/text-out (`role: user/assistant`), adding tool execution, human approval cards, and calendar/email OAuth later requires rewriting your entire chat backend.                                                                                                                                                | **Design the "Tool-Call & Approval Outbox" Envelope Now:** Structure chat messages with a `tool_calls JSONB` and `pending_actions` table from Day 1. Even in Phase 2 MVP, extract action items into `pending_actions` so turning on 1-click Gmail/Google Calendar/Web Research in Phase 3 is a zero-migration plug-in.                                                                                                                                                                                                                                                           |
| **6. Android Share-Sheet Omnichannel Clipper**           | Share Reels, YouTube videos/playlists, social posts, blogs, or messages from Android into Lazy Note with user context.                   | Solves "Bookmark Graveyard Syndrome"—people save links across 6 apps and never find them again.                                                                                                 | **Android OS Process Timeout & Social Media Anti-Bot Walls:** Android kills Share Extension activities that take `>3–5 seconds`. Scraping a YouTube video or Instagram Reel inside the mobile app will freeze the user's screen and fail on login walls.                                                                                                                                                        | **Instant Optimistic Share Sheet (`<300ms`) + Cloud Extractor Router:** Use [`expo-share-intent`](https://github.com/0xkaz/agentclip-mobile) to pop a lightweight bottom sheet where the user types a 1-line context note (_"Great animation of B+ Trees"_) and taps Save in `0.5s`. The cloud worker asynchronously routes URLs to [**Jina Reader (`r.jina.ai`)**](https://jina.ai/reader/) for blogs/articles and [**`yt-dlp`**](https://www.socialkit.dev/blog/how-to-build-youtube-transcript-scraper-python)**<!----> + Sarvam/Gemini Vision** for Reels/YouTube transcripts! |

## 2. Pillar 1: Information Architecture — Hidden Transcripts, Folders & Loose Files

### 2.1 The "Note-First, Transcript-Backed" Workspace UX

Why did [Granola](https://www.granola.ai/blog/chat-with-meetings-search-analyze-ai-2026) win over power users from Otter.ai and Fireflies? Because Otter dumps a giant wall of raw, error-prone transcript text on the screen, whereas Granola treats the **Note as the primary canvas** and treats the **Transcript + Audio as the underlying source code**.

In Lazy Note Phase 2, we implement a **Three-Path Access Pattern** for recordings and transcripts:

```
+--------------------------------------------------------------------------------------------------+
| LAZY NOTE WORKSPACE — SESSION VIEW ("Lecture 14: Deadlocks & Banker's Algorithm")             |
| Path: 📁 Semester 5 / 📁 Operating Systems                              [🔊 Audio Player] [⋯] |
+--------------------------------------------------------------------------------------------------+
| LENS TABS: [📘 Detailed Study Note *] [⚡ Executive Summary] [🗂️ 18 Flashcards] [🎯 Quiz] [+] |
+--------------------------------------------------------------------------------------------------+
|                                                              | SLIDE-OVER DRAWER (Hidden    |
| ## 1. Four Necessary Conditions for Deadlock     [▶ 12:04]   | by default; opens via `⋯`    |
| For a deadlock to occur in an operating system, all four     | or clicking `[▶ 12:04]`)     |
| Coffman conditions must hold simultaneously:                 | --------------------------   |
|                                                              | Transcript: [v2 - Verified▼] |
| * **Mutual Exclusion:** Only one process can hold a resource | Script: [CodeMix             | Latin | EN] |
| at a time.                                                   | [00:11:58] Prof. Sharma:     |
| * **Hold and Wait:** A process holding resources requests... | "Ab dekho, Coffman ke char   |
|                                                              | conditions hote hain..."     |
| > 💡 **Prof's Hinglish Intuition [▶ 14:22]:**                | [🔄 Generate New Transcript] |
| > *"Socho do train ek hi single track pe aamne-saamne..."*   | [⬇️ Download Raw Audio]      |
+--------------------------------------------------------------------------------------------------+
```

1. **Path A — Contextual Inline Inspection (Zero Context Switching):** Every generated note section carries a subtle timestamp pill (`[▶ 12:04]`). Clicking it plays the cleaned audio from `12:04` in a persistent bottom bar and optionally slides open the right-hand **Transcript & Recording Inspector** scrolled to `12:04`.
2. **Path B — The Session `⋯` Overflow Menu:** Clicking `⋯` in the top-right of any Note opens:
   - `📜 View Full Transcript` (opens the slide-over or split-screen transcript viewer)
   - `🔀 Switch Transcript Version (v1 Fast / v2 Verified)`
   - `✨ Re-Transcribe Recording...` (triggers a new STT run on the master audio with custom keyterms or a heavier model, saving it as a newly named transcript version)
   - `🎧 Manage Original Recording` (listen to raw vs. DSP-cleaned audio, view attached whiteboard snaps/PDFs)
1. **Path C — The Global "Recordings & Transcripts Vault" Tab:** In the main left sidebar (alongside `🏠 Home`, `📁 Folders`, `📄 Loose Notes`, and `🔖 Saved Clips`), a dedicated **`🎙️ Recordings & Transcripts`** tab displays a chronological, calendar-grouped table (`Today`, `Yesterday`, `Oct 2026`) of every raw audio recording and its child named transcripts (`Lecture14_Raw_Hinglish_v1`, `Lecture14_Heavy_English_v2`). From here, a user can play any old recording, generate a brand-new transcript, or spin up a new Note from an existing transcript in one click.

### 2.2 Folder Hierarchy vs. Standalone Loose Files (`ltree` + Polymorphic Workspace)

Users fall into two archetypes: **"Filers"** (who carefully create `Semester 5 → Computer Networks → Lab Manuals`) and **"Pilers"** (who hit record or create a quick note and leave 50 loose files on the desktop). Lazy Note must delight both without letting the database turn into spaghetti.

#### How to Architect Folders + Loose Files Cleanly in PostgreSQL

Instead of only using a naive `parent_folder_id` (which requires slow recursive queries when a user asks the RAG bot: _"Search everything inside Semester 5 and all its subfolders"_), combine `parent_folder_id` with PostgreSQL's built-in **`ltree` extension**:

- **Loose Files (`folder_id IS NULL`):** Any Session, Note, or Clipped Item created without choosing a folder has `folder_id = NULL` and `folder_path = 'loose'`. It appears immediately in the user's **"Loose Notes / Quick Capture"** view and the main workspace feed.
- **Organized Folders (`folder_id = UUID`):** When placed inside `Semester 5` (`id: f1`) $\rightarrow$ `DBMS` (`id: f2`) $\rightarrow$ `Unit 2` (`id: f3`), its `folder_path` is stored as `'root.f1.f2.f3'::ltree`.
- **Why `ltree` is a Superpower for RAG & Search:** When the user opens the `Semester 5` folder and asks the RAG chatbot a question, filtering 100,000 vector chunks across 15 nested subfolders takes **one single line of indexed SQL** (`WHERE folder_path <@ 'root.f1'`) and executes in `< 1.5 ms`!
- **Auto-Organization Assistant (For Loose Files):** Whenever a user creates a Loose Note, a background Gemini 2.5 Flash-Lite hook compares the note's title and summary against the user's existing folder tree and displays a non-intrusive pill at the top of the note: `✨ Suggested Folder: Semester 5 / Operating Systems [Move Here] [Dismiss]`.

### 2.3 Complete Phase 2 PostgreSQL Database Schema (Multi-Transcript + Multi-Note + Clips)

```sql
-- Enable required PostgreSQL extensions in Supabase
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Hierarchical Folders (with ltree Materialized Path for instant subtree RAG filtering)
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    parent_folder_id UUID REFERENCES folders(id) ON DELETE CASCADE, -- NULL = Top-level folder
    name TEXT NOT NULL,
    icon TEXT DEFAULT '📁',
    color_hex TEXT DEFAULT '#4F46E5',
    path LTREE NOT NULL,                     -- e.g., 'root.u123_sem5.u123_os.u123_unit2'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_folders_path_gist ON folders USING GIST (path);
CREATE INDEX idx_folders_user_parent ON folders (user_id, parent_folder_id);

-- 2. Workspace Items (Unified Container for Recordings, Standalone Notes & Shared Clips)
-- If folder_id IS NULL, the item is a "Loose File" (Standalone) in the user's profile!
CREATE TABLE workspace_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE SET NULL, -- NULL = Loose Standalone File!
    folder_path LTREE NOT NULL DEFAULT 'loose'::ltree,
    item_type TEXT NOT NULL CHECK (item_type IN ('recording_session', 'standalone_note', 'web_clip')),
    title TEXT NOT NULL,
    is_pinned BOOLEAN DEFAULT false,
    is_archived BOOLEAN DEFAULT false,
    suggested_folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_workspace_items_user_loose ON workspace_items (user_id) WHERE folder_id IS NULL;
CREATE INDEX idx_workspace_items_path_gist ON workspace_items USING GIST (folder_path);

-- 3. Named Transcript Revisions (1 Recording -> N Named Transcripts!)
CREATE TABLE transcript_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_item_id UUID NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,              -- e.g., "v1 - Fast Hinglish", "v2 - Exam Verified (Sarvam v4)"
    revision_number INT NOT NULL,
    is_default BOOLEAN DEFAULT false,
    stt_model TEXT NOT NULL,                 -- 'sarvam-saaras-v4', 'deepgram-nova-3', 'whisper-v3-heavy'
    language_mode TEXT NOT NULL DEFAULT 'codemix',
    custom_keyterms TEXT[] DEFAULT '{}',
    word_count INT DEFAULT 0,
    avg_confidence REAL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Multi-Lens Note Artifacts (1 Recording/Transcript -> M Editable Notes, Quizzes, Flashcards!)
CREATE TABLE note_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_item_id UUID NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    source_transcript_id UUID REFERENCES transcript_revisions(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,                     -- e.g., "Detailed Slide Explanation", "Midterm Flashcards"
    lens_type TEXT NOT NULL CHECK (lens_type IN (
        'detailed_explanation',              -- Deep slide-by-slide + whiteboard walkthrough
        'executive_summary',                 -- High-level 1-page TL;DR & key takeaways
        'minutes_of_meeting',                -- Decisions, discussion points, owners & deadlines
        'flashcard_deck',                    -- Interactive Front/Back/Hint active recall cards
        'interactive_quiz',                  -- MCQs + Short Answer + Viva questions w/ grading
        'custom_freeform'                    -- User-defined prompt or manual note
    )),
    editor_blocks_json JSONB,                -- Tiptap / BlockNote AST (for rich editing & block locking)
    structured_payload_json JSONB,           -- Strictly typed schema for Flashcards, Quizzes & MoM tables
    markdown_mirror TEXT NOT NULL,           -- Clean Markdown serialized from blocks/payload for export & RAG
    has_user_edits BOOLEAN DEFAULT false,    -- Protects user edits from accidental overwrite
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 3. Pillar 2: The Multi-Lens Note Studio & Rich Editing Architecture

### 3.1 Why Plain Markdown Textareas Fail—And Why Block Editors Win

You emphasized two requirements for the Notes experience:

1. **Liberty to choose the note format** (_Detailed Slide Explanation_, _Summary_, _Flashcards_, _Quiz_, _Minutes of Meeting_).
2. **Full liberty to edit the generated notes** (adding personal thoughts, fixing a formula, deleting a section, or asking AI to expand a specific slide).

If you build your note viewer as a simple Markdown string inside a `<textarea>`, two things break immediately:

- First, students cannot easily interact with **Flashcards** (flipping cards, marking "Easy / Hard") or **Quizzes** (selecting option B, checking the explanation, tracking score `8/10`) inside a raw text file.
- Second, if a user manually edits Paragraph 3 of their _Detailed Slide Explanation_, and then clicks **"✨ Ask AI to Expand Slide 5"**, replacing the whole Markdown string wipes out their manual edit in Paragraph 3!

#### The Production Solution: Hybrid Block Editor ([BlockNote](https://www.blocknotejs.org/) or [Tiptap](https://tiptap.dev/)) + Polymorphic JSONB Renderers

Use [**Tiptap**](https://tiptap.dev/) (with its [official bidirectional Markdown extension](https://tiptap.dev/blog/release-notes/introducing-bidirectional-markdown-support-in-tiptap)) or [**BlockNote**](https://www.blocknotejs.org/) (built on ProseMirror/Tiptap with out-of-the-box Notion-style `/` slash menus and drag-and-drop blocks).

Every paragraph, heading, LaTeX equation, or embedded whiteboard photo is stored as an addressable **Block Node** with a unique `block_id` and custom metadata attributes:

```json
{
  "type": "heading",
  "attrs": {
    "id": "blk_9921a",
    "level": 2,
    "source_start_ms": 2535000,
    "source_end_ms": 2610000,
    "source_slide_no": 14,
    "is_user_edited": true
  },
  "content": [{ "type": "text", "text": "Kirchhoff's Current Law (KCL) — Nodal Analysis" }]
}
```

- **Block-Level Edit Protection (`is_user_edited: true`):** Whenever the user types inside a block, the editor flips `is_user_edited = true` on that block. If the user later clicks _"Regenerate Note from Transcript v2"_, your backend performs a **Smart Block Merge**: it updates untouched AI blocks while preserving (or showing a side-by-side diff for) any block where `is_user_edited == true`!
- **Inline AI Slash Commands (`/expand`, `/hinglish-analogy`, `/diagram`):** Inside the editor, highlighting any bullet and clicking **`✨ Explain Slide in Detail`** sends _only that block's `source_start_ms..source_end_ms` transcript window + matched PDF slide image_ to **Gemini 2.5 Flash**, streaming a deep derivation directly below the cursor.

### 3.2 Technical Specifications for the 5 Core Note Lenses

Different note lenses require fundamentally different prompt engineering, input grounding, and UI renderers:

| Lens Type                                                          | Target User Scenario                                                                                     | Grounding Inputs Passed to Gemini 2.5 Flash                                                                                                                                          | Storage & UI Rendering Format                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Detailed Slide & Board Explanation (`detailed_explanation`)** | Student missed a complex proof or wants a textbook-grade walkthrough of a 40-slide lecture deck + audio. | • Full Transcript (`source_transcript_id`)• [IBM Docling](https://github.com/docling-project/docling) parsed Markdown + page images of each PDF slide• Timestamped Whiteboard Photos | **Block Editor Canvas:** Renders slide thumbnail on the left/top, followed by _What’s on the Slide_, _What the Professor Explained Verbally (with Hinglish Intuition quotes)_, step-by-step LaTeX math (`KaTeX`), and `[▶ mm:ss]` audio pills.                                                                                        |
| **2. Executive Summary / 5-Min Cheat Sheet (`executive_summary`)** | Quick pre-exam revision or pre-meeting catch-up.                                                         | • Full Transcript + High-Priority `📌 Exam Alert` pins + Slide Titles                                                                                                                | **Block Editor Canvas:** Scannable TL;DR callout box, Core Concepts table, Key Formulas/Definitions list, and Highlighted Exam/Important Alerts.                                                                                                                                                                                      |
| **3. Minutes of Meeting (`minutes_of_meeting`)**                   | Startup team syncs, client pitches, project standups, club meetings.                                     | • Diarized Transcript (with Speaker Names)• Shared docs/agenda                                                                                                                       | **Structured Hybrid View:** 1) Agenda & Attendees badge list, 2) Key Decisions Made, 3) Open Blockers/Objections, and 4) an **Interactive Action Item Table** (`Task`, `Assignee`, `Due Date`, `Status Checkbox`, `[▶ Proof Timestamp]`).                                                                                             |
| **4. Active Recall Flashcards (`flashcard_deck`)**                 | Memorizing definitions, theorems, formulas, or interview Q\&As.                                          | • Existing Detailed Note + Transcript                                                                                                                                                | **JSONB Schema + Interactive Deck UI:** Stored in `structured_payload_json` as `{cards: [{id, front_md, back_md, hint, difficulty, next_review_at, source_ms}]}`. User can **edit any card inline**, flip cards with Spacebar/Swipe, rate `Again / Good / Easy` (FSRS / SM-2 algorithm), or export to Anki `.apkg`.                   |
| **5. Interactive Practice Quiz (`interactive_quiz`)**              | Self-testing before midterms, gate exams, or viva voce.                                                  | • Existing Detailed Note + Transcript + Past Exam style rules                                                                                                                        | **JSONB Schema + Quiz Player UI:** Stored as `{questions: [{id, type: 'mcq'\|'short_answer'\|'numerical', question_md, options: [], correct_index, step_by_step_solution_md, source_ms}]}`. Users can **edit/add questions**, take the quiz in "Timed Exam Mode" or "Instant Feedback Mode", and ask AI to grade typed short answers! |

#### Enforcing Zero-Error JSON Schemas with Gemini 2.5 Structured Outputs

To guarantee that **Flashcards**, **Quizzes**, and **Minutes of Meeting Action Items** never break your frontend UI, use **Pydantic `response_schema`** with the [Gemini 2.5 Flash API](https://ai.google.dev/gemini-api/docs/models):

```python
# schemas/note_lenses.py — Strict Pydantic Schemas for Gemini 2.5 Structured Outputs
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class FlashcardItem(BaseModel):
    card_id: str = Field(description="Unique short ID, e.g., fc_01")
    front_prompt: str = Field(description="Question, concept, or cloze deletion (supports Markdown & LaTeX)")
    back_answer: str = Field(description="Concise, accurate answer (supports Markdown & LaTeX)")
    hinglish_memory_hook: Optional[str] = Field(description="Optional memorable analogy used by the speaker")
    bloom_taxonomy_level: Literal["remember", "understand", "apply", "analyze"]
    source_timestamp_ms: int = Field(description="Millisecond offset in recording where this was taught")

class FlashcardDeckOutput(BaseModel):
    deck_title: str
    cards: List[FlashcardItem]

class QuizQuestionItem(BaseModel):
    question_id: str
    question_type: Literal["mcq", "numerical", "short_answer_viva"]
    question_Text_md: str = Field(description="Question stem with LaTeX math if applicable")
    options: Optional[List[str]] = Field(description="4 distinct options if mcq, else null")
    correct_answer: str = Field(description="Exact matching option or numerical/short answer")
    common_trap_explanation: str = Field(description="Why students pick the wrong option and step-by-step derivation")
    source_timestamp_ms: int

class MinutesOfMeetingActionItem(BaseModel):
    action_id: str
    task_description: str
    assignee_speaker: str = Field(description="Speaker name or role who committed to this action")
    due_date_iso_or_text: Optional[str] = Field(description="Extracted deadline, e.g., '2026-10-30' or 'By Friday EOD'")
    priority: Literal["high", "medium", "low"]
    exact_quote: str = Field(description="Verbatim quote from transcript proving commitment")
    source_timestamp_ms: int
```

## 4. Pillar 3: The "Notes-First" Hybrid RAG Bot, Global Search & Agentic Future

### 4.1 Solving the "Notes-Only RAG" Paradox

You specified a critical design constraint:

> _"Next he will have a RAG-based bot that can answer your questions based on what data is stored (notes only)... and a search feature should be there."_

Let's examine why your instinct to index **Notes Only** as the primary knowledge base is brilliant—and the one edge case we must guard against:

- **Why Notes-First RAG Beats Raw-Transcript RAG:** Raw transcripts are full of disfluencies, false starts (_"No wait, sorry, write minus $2x$, not plus $2x$"_), and conversational tangents. If you embed raw transcript chunks directly into a vector DB, the RAG bot often retrieves the professor's _mistake_ before they corrected themselves! By indexing the **synthesized, verified, and user-edited Notes**, the RAG bot retrieves clean, self-contained concepts and respects any manual corrections the student made in the editor.
- **The Edge Case (And the Two-Tier Escalation Fix):** What if the user generated a short _Executive Summary_ note for Lecture 8, and two weeks later asks the bot: _"What exact textbook page number did Prof. Verma tell us to solve for homework in Lecture 8?"_ If that minor detail wasn't included in the 1-page summary, a strictly blind Notes-Only bot fails.
  - **The SOTA Solution (`Notes-Primary + On-Demand Transcript Deep Dive`):**
    1. **Vector Index Footprint (100% Notes & Clips Only):** Your vector index (`note_knowledge_chunks`) **only embeds curated Notes (`note_artifacts`) and Saved Web Clips**. This keeps your `pgvector` index **80% smaller, 5x cheaper, and free of raw transcript noise**.
    2. **Tool-Assisted Transcript Fallback (`search_backing_transcript_fts`):** Give the RAG LLM a lightweight PostgreSQL Full-Text Search (`tsvector`) tool over `transcript_segments` strictly as a **fallback tool**. The bot answers from Notes first; if—and only if—a specific detail (like a room number, date, or verbatim quote) is missing from the Note, the bot queries the underlying transcript of the matched note via free Postgres keyword search and explicitly tells the user: _"This wasn't in your summary note, but I checked the backing transcript for Lecture 8 at [48:12]..."_

### 4.2 SOTA Retrieval Architecture: Anthropic Contextual Retrieval + Hybrid RRF

Standard naive chunking breaks badly on student notes. Imagine a note chunk that says:

> _"Step 3: Multiply the learning rate $\alpha$ by the gradient vector and subtract from weights."_

If the student asks _"How does weight update work in Lecture 6's Neural Networks note?"_, that chunk doesn't contain the words `"Lecture 6"` or `"Neural Networks"`!

To achieve **State-of-the-Art retrieval accuracy**, implement [**Anthropic's Contextual Retrieval pattern**](https://blog.vectorchord.ai/optimize-rag-with-contextual-retrieval-in-postgresql) combined with [**Supabase Hybrid Search (BM25/tsvector + pgvector + Reciprocal Rank Fusion)**](https://supabase.com/docs/guides/ai/hybrid-search) ([Dataaspirant 2026 Benchmark](https://dataaspirant.com/blog/hybrid-search/)):

1. **Markdown-AST Structural Chunking (Never Split Mid-Table or Mid-Formula):** Split `note_artifacts.markdown_mirror` by Heading hierarchy (`H1 > H2 > H3`), keeping LaTeX blocks (`$$...$$`), code blocks, and Markdown tables intact inside a `300–600 token` window.
2. **Contextual Header Prefixing (Zero-LLM-Cost Variant + Flash-Lite Context):** Before generating the embedding or `tsvector` for any note chunk, prepend its **Breadcrumb & Context Header**:

   ```
   [Folder: Semester 5 > Operating Systems | Note: Lecture 14 - Deadlocks (Detailed Explanation) | Date: 26 Oct 2026 | Section: Banker's Algorithm > Safety State Check]
   Chunk Content: To determine if the system is in a safe state, we check if Need[i] <= Work...
   ```

   Research shows that prepending document/hierarchy context before both dense embedding and lexical indexing reduces retrieval failure rates by **49% to 67%** ([VectorChord / Anthropic Contextual Retrieval](https://blog.vectorchord.ai/optimize-rag-with-contextual-retrieval-in-postgresql)).

1. **Incremental Re-Indexing on User Edits (Debounced Block Sync):** When a user edits a note in the UI, do not re-embed on every keystroke. Use a **10-second idle debounce** (or trigger on tab blur/close). Compare SHA-256 hashes of the markdown sections and **only re-embed the modified section chunks**!

#### Production SQL for Hybrid Search with Reciprocal Rank Fusion (RRF) & Folder Filtering

This single PostgreSQL function powers **both** the instant `Cmd+K` Global Search Bar and the RAG Bot's retrieval step, supporting scoped queries (_"Search all my notes"_, _"Search only my OS Folder"_, or _"Search only Loose Files"_):

```sql
-- 1. Knowledge Chunks Table (Indexes ONLY Curated Notes & Saved Clips)
CREATE TABLE note_knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    workspace_item_id UUID NOT NULL REFERENCES workspace_items(id) ON DELETE CASCADE,
    note_artifact_id UUID REFERENCES note_artifacts(id) ON DELETE CASCADE,
    folder_path LTREE NOT NULL DEFAULT 'loose'::ltree,
    section_heading_path TEXT NOT NULL,      -- e.g., "Deadlocks > Banker's Algorithm"
    chunk_markdown TEXT NOT NULL,            -- Clean chunk text displayed in citations
    contextualized_text TEXT NOT NULL,       -- Breadcrumb + Metadata + Chunk Text
    source_start_ms INT,                     -- Preserves jump-to-audio timestamp!
    content_hash TEXT NOT NULL,              -- SHA-256 for diff-only re-embedding on user edits
    fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', contextualized_text)) STORED,
    embedding VECTOR(768) NOT NULL           -- text-embedding-004 / multilingual-e5-large
);

CREATE INDEX idx_kc_embedding_hnsw ON note_knowledge_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_kc_fts_gin ON note_knowledge_chunks USING gin (fts);
CREATE INDEX idx_kc_folder_gist ON note_knowledge_chunks USING gist (folder_path);

-- 2. Hybrid Search Function (Semantic pgvector + Keyword tsvector + Reciprocal Rank Fusion)
CREATE OR REPLACE FUNCTION hybrid_search_notes(
    p_user_id UUID,
    p_query_text TEXT,
    p_query_embedding VECTOR(768),
    p_folder_scope LTREE DEFAULT NULL,       -- Pass 'root.sem5.os' for folder scope, or NULL for global
    p_only_loose_files BOOLEAN DEFAULT FALSE,
    p_match_count INT DEFAULT 10,
    p_rrf_k INT DEFAULT 60
)
RETURNS TABLE (
    chunk_id UUID,
    workspace_item_id UUID,
    note_artifact_id UUID,
    section_heading_path TEXT,
    chunk_markdown TEXT,
    source_start_ms INT,
    rrf_score REAL
)
LANGUAGE sql STABLE AS $$
WITH filtered_pool AS (
    SELECT *
    FROM note_knowledge_chunks
    WHERE user_id = p_user_id
      AND (p_folder_scope IS NULL OR folder_path <@ p_folder_scope)
      AND (NOT p_only_loose_files OR folder_path = 'loose'::ltree)
),
semantic_search AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> p_query_embedding) AS rank_ix
    FROM filtered_pool
    ORDER BY embedding <=> p_query_embedding
    LIMIT p_match_count * 3
),
keyword_search AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(fts, websearch_to_tsquery('simple', p_query_text)) DESC) AS rank_ix
    FROM filtered_pool
    WHERE fts @@ websearch_to_tsquery('simple', p_query_text)
    ORDER BY ts_rank_cd(fts, websearch_to_tsquery('simple', p_query_text)) DESC
    LIMIT p_match_count * 3
)
SELECT
    pool.id AS chunk_id,
    pool.workspace_item_id,
    pool.note_artifact_id,
    pool.section_heading_path,
    pool.chunk_markdown,
    pool.source_start_ms,
    (
        COALESCE(1.0 / (p_rrf_k + sem.rank_ix), 0.0) * 0.65 +
        COALESCE(1.0 / (p_rrf_k + kw.rank_ix), 0.0) * 0.35
    )::REAL AS rrf_score
FROM semantic_search sem
FULL OUTER JOIN keyword_search kw ON sem.id = kw.id
JOIN filtered_pool pool ON pool.id = COALESCE(sem.id, kw.id)
ORDER BY rrf_score DESC
LIMIT p_match_count;
$$;
```

### 4.3 Future-Proofing the Agentic Bot (Human-in-the-Loop Action Architecture)

You mentioned that in the future, the bot should evolve from a passive Q\&A assistant into an **Agentic Bot** capable of triggering actions like **sending emails**, **setting reminders/calendar events**, or **running web research**.

Here is the #1 architectural insight from senior engineers who build production agents: **Do not wait until Phase 3 to design the Action State Machine.** If you build your Phase 2 RAG chat using a unified **Tool-Call + Confirmation Card Envelope**, adding Gmail, Google Calendar, and Deep Research later requires **zero database schema changes**.

```
+-----------------------------------------------------------------------------------+
| LAZY NOTE AGENTIC RAG LOOP (Phase 2 -> Phase 3)                              |
|                                                                              |
| User Prompt: "What were my action items from Friday's pitch sync, and draft  |
| an email to Rohan with the financial summary?"                               |
|                                                                              |                                |
| v                                                                            |
| [Gemini 2.5 Flash Router w/ Function Calling Tools]                          |
| /                                                                            | \                              |
| (Phase 2 Active)       (Phase 2 Active)      (Phase 3 Plug-In)               |
| /                                                                            | \                              |
| [Tool 1: search_notes]   [Tool 2: get_note_artifact]  [Tool 3: stage_action] |
| • Runs Hybrid RRF SQL    • Reads MoM / Quiz / Deck    • `create_reminder`    |
| • Optional transcript    • Extracts exact context     • `draft_email`        |
| fallback if needed                                  • `web_research`         |
| \                                                                            | /                              |
| +----------------------+-----------------------+                             |
|                                                                              |                                |
| v                                                                            |
| [Human-in-the-Loop Action Outbox (`agent_pending_actions`)]                  |
| • Renders an interactive Confirmation Card directly inside the Chat stream:  |
| [📧 Draft Email to Rohan                                                     | Subject: Pitch Sync Follow-Up] |
| [Edit Draft]  [✅ Approve & Send]  [❌ Cancel]                                 |
+-----------------------------------------------------------------------------------+
```

- **Why Confirmation Cards Are Mandatory for Agentic Notes:** An LLM should _never_ silently send an email to a professor or co-founder without user approval. By having the agent emit a structured `stage_action(action_type="email_draft" | "reminder" | "web_research", payload={...})` call that renders an **Interactive Approval Card** in the chat UI:
  - **In Phase 2 (Right Now):** A `reminder` card can immediately trigger a local device notification or `mailto:` / `.ics` calendar download with zero OAuth complexity!
  - **In Phase 3 (Future):** Clicking `[✅ Approve & Send]` on that exact same UI card invokes your backend Gmail API / Google Calendar API / Tavily Web Search worker!

## 5. Pillar 4: Android Share-Sheet "Second Brain" Omnichannel Clipper (Future Scope Blueprint)

### 5.1 Why This Feature Can Make Lazy Note Go Viral

You brainstormed:

> _"If made into an Android app, maybe you can share things to this app from different platforms and it will keep a context of the content along with the content (maybe a link to a Reel, a post on social media, YouTube video or playlist, a blog or article, message or email, whatever) — this can be used as a knowledge base or smart notes store for quick lookup."_

**Product Manager Verdict:** This is a **10/10 product expansion**. Today, every student and developer suffers from **"WhatsApp Self-Chat & Bookmark Graveyard Syndrome"**:

- They watch an Instagram Reel explaining a coding interview pattern or a YouTube lecture playlist, tap _Share → WhatsApp (Message Yourself)_, and **never find it again** because WhatsApp only stores the raw URL (`https://www.instagram.com/reel/Cx9...`) with zero transcript, zero extracted content, and zero searchable tags.
- By turning Lazy Note into an **Android Share Target**, when a user shares a Reel, YouTube video, X post, or blog to Lazy Note, Lazy Note doesn't just save the bookmark—it **extracts the spoken audio/transcript, scrapes the article text, captures the user's personal "Why I saved this" voice/text note, auto-files it into the right subject folder, and indexes it into the same Hybrid RAG brain** as their classroom lectures!

### 5.2 The Golden Rule of Android Share Intents: The `< 500ms` Capture Overlay

On Android, when a user is inside Instagram or YouTube and taps **Share $\rightarrow$ Lazy Note**, Android launches your Share Receiver activity on top of the current app.

- **The Trap:** If your app boots up the full main UI, waits 8 seconds to scrape the YouTube video, and forces the user to pick a nested folder before returning them to Instagram, **they will stop using it after Day 2**.
- **The SOTA UX Pattern ("1-Tap Context Overlay Sheet"):**
  1. Using React Native / Expo with [**`expo-share-intent`**](https://github.com/0xkaz/agentclip-mobile) (or a native Kotlin transparent `BottomSheetDialogActivity` registered for `android.intent.action.SEND` with `text/plain` and `image/*`), sharing a link opens a **instant, translucent 35%-height Bottom Sheet** over YouTube/Instagram in `< 250ms`.
  2. The sheet displays:
     - The auto-detected platform icon (`📸 Instagram Reel`, `▶️ YouTube Video`, `📰 Web Article`, `💬 Shared Text/Message`)
     - A pre-focused input box (with a 1-tap `🎙️ Voice Note` mic button!): **"Add context: Why are you saving this?"** (e.g., _"Great visual animation of Dijkstra's algorithm for Sem 5 exam"_)
     - A smart folder chip: `[📁 Auto-Route (AI)]` or `[📁 Sem 5 > DAA]`
  3. The user taps **Save** (or swipes down—saving automatically after 3 seconds!). The payload is queued in local SQLite/IndexedDB, the overlay closes immediately so the user is right back in Instagram/YouTube, and the **Cloud Omnichannel Ingestion Pipeline** does all the heavy lifting in the background!

### 5.3 The Omnichannel Content Extraction Router (How to Extract Every Platform)

Once the backend receives `{ shared_url, shared_raw_text, user_context_note, user_voice_memo_url }`, an **Inngest / Celery URL Router** inspects the domain and dispatches the appropriate extraction worker:

```
+----------------------------------------------------------------------------------------+
| ANDROID SHARE SHEET ("SEND" Intent: URL / Text / Image)                         |
| User adds quick context: "Great explanation of B+ Tree node splitting for DBMS" |
+-------------------------------------------+--------------------------------------------+
                                            | (Queued locally -> POST /api/v1/clips/ingest)
                                            v
+----------------------------------------------------------------------------------------+
| CLOUD OMNICHANNEL INGESTION ROUTER (FastAPI + Inngest) |
+-------------------------------------------+--------------------------------------------+
       |                       |                        |                        |
       v                       v                        v                        v
+--------------+      +-----------------+      +-----------------+      +----------------+
| 1. YOUTUBE    |     | 2. SHORT VIDEO  |     | 3. BLOGS, DOCS   |     | 4. SOCIAL &    |
| Video /       |     | IG Reels,       |     | & ARTICLES       |     | MESSAGES       |
| Playlist      |     | YT Shorts,      |     | Medium, Substack |     | X/Twitter,     |
|               |     | TikTok          |     | ArXiv, DevBlogs  |     | LinkedIn,      |
| • Fetch Capt. |     |                 |     |                  |     | WhatsApp/Email |
| via yt-dlp    |     | • yt-dlp pulls  |     | • Primary:       |     |                |
| / Transcript  |     | audio +         |     | Jina Reader      |     | • X/Twitter:   |
| API           |     | caption meta    |     | (r.jina.ai)      |     | FxTwitter /    |
| • Fallback:   |     | • Sarvam Saaras |     | or Trafilatura   |     | Syndication    |
| Audio-only    |     | v4 / Deepgram   |     | / Defuddle       |     | JSON API       |
| stream ->     |     | transcribes     |     | converts HTML    |     | • WhatsApp /   |
| Sarvam STT    |     | 30-90s audio    |     | to clean MD      |     | Email: Parse   |
| • Playlist:   |     | • Keyframe OCR  |     | • Extracts OG    |     | forwarded      |
| Map into      |     | via Gemini 2.5  |     | title, author,   |     | text +         |
| Folder of     |     | Flash Vision!   |     | code blocks      |     | attachments    |
| Child Notes   |     | (Reads on-      |     | & diagrams       |     | directly       |
|               |     | screen text!)   |     |                  |     |                |
+------+-------+      +--------+--------+      +--------+--------+      +--------+-------+
       |                       |                        |                        |
       +-----------------------+------------------------+------------------------+
                                            |
                                            v
+----------------------------------------------------------------------------------------+
| UNIFIED "SMART CLIP" SYNTHESIZER (Gemini 2.5 Flash)                              |
| • Fuses: [User's "Why I Saved This" Context] + [Extracted Transcript/Article MD] |
| + [Visual Keyframe OCR]                                                          |
| • Generates:                                                                     |
| 1. Structured Smart Note (TL;DR, Key Takeaways, Code/Formulas, Actionable Steps) |
| 2. Auto-Folder Classification (Matches against User's `folders` tree)            |
| 3. Contextual Embeddings -> Indexed into `note_knowledge_chunks` for RAG!        |
+----------------------------------------------------------------------------------------+
```

#### Deep-Dive Technical Methods by Source Type:

1. **Instagram Reels, YouTube Shorts & TikTok (The "Silent Text-on-Screen" Trap):**
   - _Why standard audio transcription fails on Reels:_ Half of educational Instagram Reels have background music playing while the actual code snippet, roadmap, or cheat sheet is shown as **on-screen text overlays** or in the **post caption**!
   - _The Technical Method:_
     1. Run [**`yt-dlp`**](https://www.socialkit.dev/blog/how-to-build-youtube-transcript-scraper-python) (`yt-dlp --dump-json --extract-audio`) to pull both the **post caption/description** and the **audio track**.
     2. Run `ffmpeg` scene-change detection (`select='gt(scene,0.35)'`, capped at max 6 keyframes for a 60s Reel) and pass those 6 thumbnail frames + audio to **Gemini 2.5 Flash** in a single multimodal call (`~$0.0008` per Reel!). Gemini reads both the spoken Hinglish/English voiceover _and_ every on-screen text slide or code snippet!
     3. _Fallback for Private/Rate-Limited IG Reels:_ If Instagram blocks server-side datacenter IPs on a specific Reel, the Android Share overlay also lets the user share a screenshot or screen-clip, or falls back to extracting the OpenGraph meta description + user's context note so the save never fails.
1. **YouTube Videos & Full YouTube Playlists:**
   - _Single Video:_ First check for existing subtitles/auto-captions via `youtube-transcript-api` or `yt-dlp --write-auto-sub --skip-download` (instant, free, takes `<2 seconds`). If captions are disabled or poor-quality Hinglish, stream the `m4a/opus` audio track into your Phase 1 **Sarvam Saaras v4 / Deepgram** pipeline.
   - _YouTube Playlists (Killer Feature for Students!):_ When a student shares a 25-video NPTEL or Striver DSA YouTube playlist, do **not** transcribe all 25 hours immediately (which would cost ₹1,000!). Instead:
     - Fetch the playlist metadata JSON (`video titles, durations, URLs, descriptions`) in 2 seconds.
     - Automatically create a **Dedicated Playlist Folder** (`📁 [Playlist] Striver Graph Series (25 Videos)`) containing 25 lightweight **Stub Cards**.
     - Extract transcripts/notes **lazily on demand** as the student watches each video, or extract free captions first!
1. **Blogs, Medium Articles, Substack & Documentation URLs:**
   - Pass the URL through [**Jina Reader (`https://r.jina.ai/<URL>`)**](https://jina.ai/reader/) or self-hosted **`trafilatura` / `Defuddle` / Playwright Readability**. These strip ads, navbars, and cookie banners and return clean, LLM-ready Markdown preserving code blocks, tables, and image links.
1. **Messages, WhatsApp Forwards & Emails (`text/plain` / `message/rfc822`):**
   - When a user selects 5 messages in WhatsApp or an email in Gmail and taps _Share $\rightarrow$ Lazy Note_, Android passes the raw text directly in `Intent.EXTRA_TEXT` (no scraping needed!).
   - Your pipeline parses sender/timestamp patterns, pairs them with the user's context note (_"Professor's syllabus changes announced on WhatsApp group"_), and links it directly into the relevant Subject Folder!

### 5.4 Why "User Context + Extracted Content" Is the Secret Sauce for Retrieval

In most bookmarking apps, if you save an article titled _"A Gentle Introduction to Paxos"_ because the author drew a great diagram comparing Paxos vs. Raft, and 3 months later you search _"Raft comparison diagram"_, you won't find it if the article barely mentions Raft.

In Lazy Note's **Smart Clip Schema**, the user's personal context note (`user_intent_context`) is treated as a **First-Class Weighted Field**:

- When building the `contextualized_text` for `note_knowledge_chunks` (Section 4.2), the user's context note is placed **at the very top of every chunk** and weighted **`2.0x` (`setweight(to_tsvector(...), 'A')`)** in PostgreSQL Full-Text Search!
- That means the user can search **by how they remember it** (_"that reel about B+ tree splitting I saved from Instagram last week"_) OR **by what was inside the content** (_"minimum degree $t$ in B+ tree node"_), and Hybrid RRF Search surfaces it instantaneously.

## 6. Prioritized Engineering Roadmap & Build Sequence (Phase 2 → Phase 3)

As both your Senior Product Manager and Principal Architect, here is my strongest recommendation on **how to sequence these features** so you ship a polished, high-retention product without drowning in scope creep:

| Milestone                                                                     | Scope Tier                   | What to Build                                                                                                                                                                                                                                                                                                                  | Key Technical Stack & Deliverables                                                                                                                                                                                                                                                                                                                                                              |
| ----------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Stage 2A (Weeks 1–3): Workspace, Loose Files & Multi-Lens Studio**          | **CORE PHASE 2 (Build Now)** | • **Folder (`ltree`) + Loose Files** workspace UI• **Hidden Transcript Drawer (`⋯`)** + Inline `[▶ mm:ss]` audio pills + **Global Recordings/Transcripts Vault** tab• **Multi-Transcript Naming & Versioning** (`v1`, `v2`)• **5 Editable Note Lenses** (_Detailed Slide Explanation_, _Summary_, _MoM_, _Flashcards_, _Quiz_) | • **Supabase PostgreSQL** (`ltree`, `workspace_items`, `transcript_revisions`, `note_artifacts`)• [**Tiptap**](https://tiptap.dev/)**<!----> / <!---->**[**BlockNote**](https://www.blocknotejs.org/) block editor for rich notes + block-level edit locking• **Gemini 2.5 Flash Structured Outputs** for interactive Flashcard & Quiz JSONB schemas                                                |
| **Stage 2B (Weeks 4–6): Global Hybrid Search & Notes-First RAG Bot**          | **CORE PHASE 2 (Build Now)** | • **`Cmd+K` Instant Hybrid Search** (filter by Folder, Loose Files, Lens Type, or Date)• **Notes-First Contextual RAG Bot** (with automatic fallback tool to check backing transcript when granular details are missing)• **Action Item Extractor** into `agent_pending_actions` table                                         | • **Anthropic Contextual Retrieval** chunker (breadcrumb + heading injection)• **Supabase Hybrid Search (`pgvector` HNSW + `tsvector` + Reciprocal Rank Fusion SQL)**• **Debounced SHA-256 Chunk Diffing** when users edit notes                                                                                                                                                                |
| **Stage 3A (Weeks 7–10): Android App & Share-Sheet Clipper ("Second Brain")** | **FUTURE SCOPE EXPANSION 1** | • **Android Share Target Overlay** (`<300ms` bottom sheet with text/voice _"Why I saved this"_ context input)• **Omnichannel Cloud Extractor** for YouTube videos/playlists, Instagram Reels, X/LinkedIn posts, Blogs, and WhatsApp forwards• **Auto-Folder Routing** into existing workspace folders                          | • **React Native / Expo** with [`expo-share-intent`](https://github.com/0xkaz/agentclip-mobile)• [**Jina Reader (`r.jina.ai`)**](https://jina.ai/reader/) + `trafilatura` for web/blog Markdown extraction• [**`yt-dlp`**](https://www.socialkit.dev/blog/how-to-build-youtube-transcript-scraper-python)**<!----> + FFmpeg Keyframe Scene Detection + Gemini 2.5 Flash Vision** for Reels/Shorts |
| **Stage 3B (Weeks 11–12): Agentic Actions & External Integrations**           | **FUTURE SCOPE EXPANSION 2** | • Turn on live execution for the **Chat Confirmation Cards** (`Send Email via Gmail`, `Add Reminder to Google Calendar`, `Run Deep Web Research to Supplement Lecture Note`)                                                                                                                                                   | • **Google OAuth (`gmail.compose`, `calendar.events`)**• **Search Grounding / Tavily API** for live research synthesis directly into a Note block                                                                                                                                                                                                                                               |

## 7. Reference Bibliography & Technical Sources

- **Rich Block Editors & AI Note Workspace Architectures:**
  - Tiptap Engineering (Oct 2025), [_Introducing Bidirectional Markdown & JSON AST Support in Tiptap_](https://tiptap.dev/blog/release-notes/introducing-bidirectional-markdown-support-in-tiptap)
  - BlockNote Open-Source Project, [_BlockNote: Extensible React Block-Based Rich Text Editor on ProseMirror/Tiptap_](https://www.blocknotejs.org/)
  - Granola Engineering & Product Analysis (May–Aug 2026), [_Chat with Your Meetings: How to Search and Analyze Meeting Notes Across Folders_](https://www.granola.ai/blog/chat-with-meetings-search-analyze-ai-2026) and [_Granola vs. Notion AI Meeting Notes Architecture_](https://zackproser.com/blog/granola-vs-notion-ai)
  - IBM Research, [_Docling: Open-Source Document Parsing for Academic PDFs, Tables & Slide Layouts_](https://github.com/docling-project/docling)
- **Contextual RAG, Hybrid Search & Vector Indexing:**
  - VectorChord Engineering (May 2025), [_Optimize RAG with Anthropic Contextual Retrieval in PostgreSQL (BM25 + pgvector)_](https://blog.vectorchord.ai/optimize-rag-with-contextual-retrieval-in-postgresql)
  - Supabase Official AI Documentation, [_Hybrid Search in Postgres: Combining pgvector Semantic Search and tsvector Full-Text Search with Reciprocal Rank Fusion (RRF)_](https://supabase.com/docs/guides/ai/hybrid-search)
  - Dataaspirant Engineering (Aug 2026), [_Hybrid Search — BM25 + Vectors + RRF Production Guide_](https://dataaspirant.com/blog/hybrid-search/)
  - Roshis Rai (July 2026), [_Building a RAG Pipeline from Scratch: Hybrid Search with pgvector, HNSW, and Supabase_](https://www.roshis.dev/blog/building-a-rag-pipeline-from-scratch-hybrid-search-with-pgvector-and-supabase)
- **Android Share-Sheet Ingestion & Omnichannel Content Extraction:**
  - AgentClip Mobile Architecture, [_Expo + React Native Share-Sheet Capture via `expo-share-intent` with Hybrid Search_](https://github.com/0xkaz/agentclip-mobile)
  - Expo Share Extension Config Plugin, [_MaxAst/expo-share-extension_](https://github.com/MaxAst/expo-share-extension)
  - Jina AI Documentation (2026), [_Jina Reader API (`r.jina.ai`): Converting Web URLs to LLM-Friendly Markdown for RAG_](https://jina.ai/reader/) and [_Web-to-Markdown API Benchmarks_](https://thedrive.ai/blog/drive-ai-vs-jina-reader-vs-firecrawl-markdown-api)
  - SocialKit & Python Video Extraction Guides (Sept 2026), [_Building a YouTube & Short-Video Transcript Pipeline in Python with `yt-dlp`_](https://www.socialkit.dev/blog/how-to-build-youtube-transcript-scraper-python)
