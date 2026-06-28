# White-Label RAG Chatbot

A fully customizable, self-hosted AI chatbot powered by Azure OpenAI and pgvector. Deploy your own knowledge-based assistant — just upload your data and set your prompt.

## What You Get

- **RAG Chat Engine** — Hybrid vector + BM25 search with cross-encoder reranking
- **Document Upload** — Upload PDFs, DOCX, PPTX, CSV, TXT, images (OCR) to build your knowledge base
- **Admin Dashboard** — Edit system prompt, manage corrections, block words, review flagged answers
- **pgvector Storage** — Persistent Supabase-powered vector database
- **Docker Ready** — One-command deployment with `docker-compose`

## Quick Start

> Important: Do not commit `.env` files or secret keys to GitHub. Use the provided `.env.example` templates and keep local secrets private.

### 1. Configure Environment

```bash
cd backend
cp .env.example .env
# Edit .env with your Azure OpenAI credentials and Supabase keys
```

### 2. Run Locally (Development)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Run with Docker

```bash
docker-compose up --build -d
```

Visit `http://localhost:8000` to access the chatbot.

## Configuration

All configuration is done via the `.env` file:

| Variable | Required | Description |
|---|---|---|
| `FOUNDRY_ENDPOINT` | ✅ | Azure OpenAI endpoint URL |
| `FOUNDRY_API_KEY` | ✅ | Azure OpenAI API key |
| `FOUNDRY_DEPLOYMENT` | ✅ | Azure OpenAI deployment name |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Supabase service role key |
| `BOT_NAME` | ❌ | Your bot's name (default: "Assistant") |
| `BOT_DESCRIPTION` | ❌ | Bot description shown in the API docs |
| `ADMIN_EMAIL` | ❌ | Default admin email for seeding |

## Customization

### System Prompt
Edit the system prompt directly from the Admin Dashboard (`/api/admin/system-prompt`) or via the frontend settings panel.

### Knowledge Base
Upload your own documents via the `/api/upload` endpoint or the Admin Dashboard. Supported formats:
- PDF, DOCX, PPTX
- TXT, MD, JSON, CSV
- Images (PNG, JPG, etc. — requires Tesseract for OCR)

### Corrections & Moderation
- Flag incorrect responses and create corrections
- Block specific words/phrases from being answered
- Full audit trail of all admin actions

## API Endpoints

### Chat
- `POST /api/chat` — Send a question and get a RAG-powered answer

### Admin
- `GET/POST /api/admin/system-prompt` — View/update system prompt
- `GET/POST /api/admin/temperature` — View/update LLM temperature
- `GET /api/admin/flagged-responses` — List flagged responses
- `POST /api/admin/flagged-responses/{id}/approve` — Approve a flagged response
- `POST /api/admin/flagged-responses/{id}/reject` — Reject a flagged response
- `GET/POST /api/admin/corrections` — List/create corrections
- `GET/POST/DELETE /api/admin/blocked-words` — Manage blocked words
- `GET /api/admin/uploads` — List uploaded documents
- `DELETE /api/admin/uploads/{id}` — Delete an uploaded document
- `GET /api/admin/audit-logs` — View audit trail

### Upload
- `POST /api/upload` — Upload a document (multipart form with `file` and optional `title`)

### Status
- `GET /api/status` — System status
- `GET /health` — Health check

## Architecture

```
white_label_chatbot/
├── backend/
│   ├── main.py              # FastAPI app + RAG service + all API routes
│   ├── config.py            # Environment configuration loader
│   ├── pgvector_store.py    # Supabase pgvector wrapper
│   ├── workflow_db.py       # SQLAlchemy ORM + workflow functions
│   ├── ingestion.py         # Document parsing + chunking
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # Your configuration (not committed)
│   └── .env.example         # Template configuration
├── frontend/                # React admin dashboard (build with npm run build)
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## No Connection to Ask GLA

This is a **completely independent** chatbot. It has:
- ❌ No GLA-specific data, prompts, or branding
- ❌ No connection to the Ask GLA backend or database
- ❌ No analytics, intent scoring, or Sarvam TTS integration
- ✅ Its own separate database, vector store, and configuration
- ✅ Full customization of prompts, data, and branding

## License

Proprietary — for authorized use only.
