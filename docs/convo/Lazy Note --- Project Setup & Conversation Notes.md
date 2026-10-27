

**Purpose:** This document captures the project structure, decisions,  
commands, current server status, and next steps discussed while  
beginning development of Lazy Note.

**Status at the end of this conversation:** The FastAPI development  
server starts successfully from the `backend/` directory. The `/` and  
`/docs` routes return HTTP 200. `/health` has not yet been implemented.  
Audio upload has not yet been implemented or tested.

---

## 1. Product context

Lazy Note is intended to turn lecture and meeting recordings into useful  
notes, with particular attention to Hindi-English mixed speech  
(Hinglish). The broader product direction includes:

- Audio recording and upload.
- Timestamped speech-to-text transcripts.
- AI-generated study notes and other output formats.
- Timestamped photos and supporting PDFs/handouts.
- A web interface for uploading recordings and reviewing results.
- Later, search/chat over notes and other advanced features.

The immediate engineering goal is deliberately smaller: get a working  
backend, implement an audio-upload endpoint, connect the existing  
Next.js frontend, and then add transcription and note generation.

## 2. Existing repository structure

The project root is named `lazynote`. The screenshots showed this  
general structure:

```
lazynote/
├── .agents/
├── backend/
│   ├── .venv/
│   ├── notebooks/
│   ├── scripts/
│   ├── src/
│   │   └── lazynote/
│   │       ├── __init__.py
│   │       └── main.py
│   ├── tests/
│   │   └── sample/
│   │       └── ai for autonomous sample.m4a
│   ├── .env
│   ├── .env.example
│   ├── .python-version
│   ├── pyproject.toml
│   ├── README.md
│   ├── requirements.txt
│   └── uv.lock
├── dist/
├── docs/
├── web/
│   ├── app/
│   ├── public/
│   ├── package.json
│   ├── next.config.ts
│   └── ...
├── .gitignore
└── AGENTS.md
```

This is based on the visible screenshots; the complete contents of every  
directory have not been inspected.

### Key observations

- `backend/` is the Python project directory.
- The backend uses `uv` for Python environment and dependency  
    management. A `.venv/`, `pyproject.toml`, and `uv.lock` are present.
- The importable Python package is now named `lazynote`, under  
    `backend/src/lazynote/`.
- `backend/src/lazynote/main.py` is the FastAPI entry point used to  
    start the development server.
- `web/` is an existing Next.js frontend. Do not create a second  
    frontend.
- `backend/tests/sample/ai for autonomous sample.m4a` is a sample  
    audio file available for future upload/transcription testing.
- `.env` and `.env.example` exist. Secret values in `.env` must not be  
    committed to Git or pasted into public logs.
- An `app/` directory was initially visible under `backend/` and was  
    described as empty. The later screenshot no longer showed it, and  
    the source package had been renamed to `src/lazynote/`.
- `dist/` exists at the repository root. Its purpose and tracking  
    status were not verified.
- `requirements.txt` exists alongside `pyproject.toml`;  
    `pyproject.toml` should be treated as the primary dependency/project  
    configuration for the `uv` project unless the repository  
    intentionally maintains requirements separately.

## 3. Python package naming decision

Initially, the backend had a path similar to:

```
backend/src/backend/__init__.py
```

This is valid in a Python `src` layout, but it can be confusing because  
the outer directory and import package are both called `backend`.

The project was reorganized to use:

```
backend/src/lazynote/__init__.py
backend/src/lazynote/main.py
```

This separates the concepts:

- `backend/`: Python project directory, virtual environment,  
    `pyproject.toml`, and lockfile.
- `backend/src/lazynote/`: importable Python application package.
- `web/`: Next.js frontend application.

The package rename is a naming choice, not a technical requirement. If  
any code or project configuration still references the old package name,  
it should be updated. The current successful server startup indicates  
that the `lazynote.main:app` import works in the current environment.

## 4. Why `uv build` failed

The command was run from the repository root:

```
uv build
```

It failed with an error saying the root directory did not appear to be a  
Python project because it did not contain `pyproject.toml` or  
`setup.py`.

The reason: `pyproject.toml` is inside `backend/`, not the repository  
root.

To build the Python package, run:

```
cd backend
uv build
```

`uv build` creates distributable package artifacts. It is not required  
every time application code changes. During development, run the FastAPI  
development server instead.

## 5. Current development server command and status

The command that successfully started the server was run from  
`backend/`:

```
uv run fastapi dev src/lazynote/main.py
```

FastAPI reported the import string:

```
lazynote.main:app
```

It started the development server at:

```
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```
http://127.0.0.1:8000/docs
```

The logs included:

```
Application startup complete.
127.0.0.1:... - "GET / HTTP/1.1" 200
127.0.0.1:... - "GET /favicon.ico HTTP/1.1" 404
127.0.0.1:... - "GET /health HTTP/1.1" 404
127.0.0.1:... - "GET /helth HTTP/1.1" 404
127.0.0.1:... - "GET /docs HTTP/1.1" 200
127.0.0.1:... - "GET /openapi.json HTTP/1.1" 200
```

### Interpretation

- `GET /` → HTTP 200: the root endpoint exists and responds.
- `GET /docs` → HTTP 200: FastAPI Swagger UI is working.
- `GET /openapi.json` → HTTP 200: the OpenAPI schema is being served.
- `GET /health` → HTTP 404 at that point: a health route had not yet  
    been defined.
- `GET /helth` → HTTP 404: this path is misspelled and had not been  
    defined.
- `GET /favicon.ico` → HTTP 404: no favicon is configured; this is  
    optional and not a server failure.

The server is running locally, not yet deployed publicly.

## 6. Suggested minimal `main.py`

The exact current file contents were not shared. A minimal FastAPI app  
could look like this, but compare with the existing file before  
replacing anything:

```
from fastapi import FastAPI

app = FastAPI(title="Lazy Note API")


@app.get("/")
def home():
    return {"message": "Lazy Note API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

If the root route already exists, do not duplicate it. Add only the  
missing `/health` route.

After saving, the FastAPI development server should reload  
automatically. Verify by opening:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

Expected health response:

```
{"status": "ok"}
```

## 7. Frontend and backend responsibilities

A frontend is not necessary to begin testing the backend. FastAPI's  
`/docs` interface can submit requests directly, including multipart file  
uploads once an upload endpoint exists.

### Frontend (`web/`)

The Next.js frontend will eventually provide:

- A file picker and upload button.
- Upload and processing status.
- A transcript viewer.
- A note viewer/editor.
- Later, recording controls, timestamped photo capture, session  
    history, and other product features.

### Backend (`backend/`)

The FastAPI backend will provide:

- HTTP API endpoints.
- File validation and upload coordination.
- Session creation and status tracking.
- Transcription and note-generation orchestration.
- Database access and persistence.
- Later, authentication, authorization, quotas, and background job  
    management.

### Storage and AI services

For the first prototype, an uploaded file can be stored locally. For  
production, the intended direction is object storage such as Cloudflare  
R2 or S3, with session/transcript metadata in PostgreSQL (for example,  
Supabase). Speech-to-text and LLM providers can be integrated after  
upload works.

## 8. Next implementation milestone: audio upload

The next feature should be a minimal upload endpoint:

```
POST /api/v1/uploads
```

It should eventually:

1. Accept a file using multipart form data.
2. Validate the file extension, content, and maximum size.
3. Save the file locally during development.
4. Return a generated file ID, saved filename, size, and status.
5. Be testable from `http://127.0.0.1:8000/docs`.

The existing sample file can be used:

```
backend/tests/sample/ai for autonomous sample.m4a
```

### Dependency note

If needed, from inside `backend/`, add FastAPI, Uvicorn, and multipart  
parsing support through `uv`:

```
uv add fastapi "uvicorn[standard]" python-multipart
```

Do not add duplicate dependencies before inspecting `pyproject.toml`;  
the current server already starts, so some or all dependencies are  
likely installed.

### Local upload prototype considerations

For a quick development-only prototype, files may be saved to a local  
`uploads/` directory. Use generated filenames rather than trusting  
user-provided filenames. Enforce a size limit and clean up partial files  
after failures.

A production implementation also needs stronger content validation,  
authentication, per-user quotas, storage lifecycle management, safe  
error handling, and durable object storage. Avoid sending large audio  
files through the API server indefinitely; a later production design can  
use presigned uploads to object storage.

## 9. Connecting the Next.js frontend

After the upload endpoint works in `/docs`, connect the existing  
frontend. A browser request can use `FormData`:

```
const formData = new FormData();
formData.append("file", selectedFile);

const response = await fetch(
  "http://127.0.0.1:8000/api/v1/uploads",
  {
    method: "POST",
    body: formData,
  }
);

const result = await response.json();
```

`selectedFile` should be a `File` object from an HTML file input. Do not  
manually set the multipart `Content-Type` header; the browser will add  
the correct boundary.

During local development, the frontend and backend may use different  
origins, so configure FastAPI CORS to allow the actual Next.js  
development origin. Do not use an unrestricted production CORS policy.

## 10. Recommended development sequence

Follow this order to keep the scope manageable:

1. Confirm `backend/pyproject.toml` and the current `main.py`.
2. Keep the development server running from `backend/`.
3. Add `/health` and verify it returns HTTP 200.
4. Add `POST /api/v1/uploads`.
5. Upload the sample `.m4a` from FastAPI `/docs`.
6. Verify the saved file and response.
7. Connect the existing Next.js upload form.
8. Add session metadata and persistent storage.
9. Integrate one speech-to-text provider and test Hinglish recordings.
10. Generate structured notes from the transcript.
11. Move long-running processing to a durable background job system  
    before production.
12. Add resilient chunked recording, photo/PDF timeline alignment, RAG,  
    and advanced features incrementally.

The first useful end-to-end milestone is:

**Select an audio file → upload it → receive an upload ID → persist it →  
transcribe it → display transcript and notes in the web app.**

Do not build the entire architecture at once.

## 11. Items not yet verified

These details still need inspection before making more structural  
changes:

- The complete contents of `backend/pyproject.toml`.
- The current full contents of `backend/src/lazynote/main.py`.
- Whether `uv` dependencies are declared consistently between  
    `pyproject.toml` and `requirements.txt`.
- Whether the root `dist/` directory is generated output and whether  
    it is ignored by Git.
- Whether `.env` is excluded in `.gitignore`.
- Whether the frontend has an existing upload page or API client.
- Whether the `/health` endpoint has since been added.
- Whether audio upload has been implemented.

## 12. Immediate next actions

Run commands from the correct directory:

```
cd backend
uv run fastapi dev src/lazynote/main.py
```

Then:

1. Open `/docs`.
2. Add and verify `/health`.
3. Inspect `pyproject.toml` and `main.py` before changing dependencies  
    or replacing code.
4. Implement the upload endpoint.
5. Test with the existing sample `.m4a`.

**Current state:** The development server startup is confirmed  
successful. Audio upload, transcription, note generation, database  
persistence, and frontend integration remain future implementation tasks  
unless they have been completed since this conversation.