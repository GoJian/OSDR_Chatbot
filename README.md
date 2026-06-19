# OSDR ChatBot

A local AI chatbot for exploring NASA's [Open Science Data Repository (OSDR)](https://osdr.nasa.gov/) — focused on **eye health** and **Space Associated Neuro-ocular Syndrome (SANS)**.

The bot runs entirely on your machine using [ollama](https://ollama.com/). It fetches and caches study metadata from the OSDR API, then uses a local LLM to answer questions about spaceflight effects on the eye, retinal changes, intraocular pressure, and related neuro-ocular research.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | Uses `match` and `X \| Y` type hints |
| [ollama](https://ollama.com/) | Must be running locally (`ollama serve`) |
| `gemma4` model | `ollama pull gemma4` (9.6 GB) — see fallback note below |
| Internet access | One-time metadata fetch from OSDR API |

> **No gemma4 yet?** The chatbot automatically falls back to any other installed ollama model (e.g. `qwen3.6:latest`). You can also pass `--model` to choose explicitly.

---

## Quick Start

```bash
# 1. Clone the repo
git clone git@github.com:GoJian/OSDR_Chatbot.git
cd OSDR_Chatbot

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the LLM (skip if you already have a model in ollama)
ollama pull gemma4

# 5. Fetch OSDR metadata (downloads ~1.7 MB of study metadata)
python fetch_metadata.py

# 6. Start the chatbot
python chatbot.py
```

---

## Chatbot Usage

```
 OSDR Eye/SANS ChatBot
 Model: gemma4 | Studies loaded: 15
 Type 'quit' or Ctrl+C to exit, 'studies' to list loaded studies

You: What studies measured intraocular pressure during spaceflight?
You: Tell me about the head-down tilt studies and SANS
You: Which retina studies used RNA-seq?
You: What missions did the RR-3 studies fly on?
You: Compare OSD-758 and OSD-759
You: studies         ← list all loaded study IDs and file counts
You: quit            ← exit (or Ctrl+C)
```

### Command-line flags

```bash
# Use a specific ollama model
python chatbot.py --model gemma4
python chatbot.py --model qwen3.6:latest
python chatbot.py --model llama3.2:latest

# List all cached studies and exit
python chatbot.py --list-studies
```

Sample `--list-studies` output:
```
Cached studies (15):
  OSD-100:  251 files  [2026-06-19T18:03:42Z]
  OSD-162:  292 files  [2026-06-19T18:03:50Z]
  OSD-194:  294 files  [2026-06-19T18:04:01Z]
  OSD-255:  245 files  [2026-06-19T18:04:10Z]
  OSD-363:    3 files  [2026-06-19T18:04:18Z]
  ...
```

---

## Fetching Metadata

Metadata is downloaded once and cached locally in `data/` (not tracked by git). Re-run anytime to refresh or add studies.

```bash
# Fetch the curated eye/SANS study list (default — 15 studies)
python fetch_metadata.py

# Re-download everything, overwriting the cache
python fetch_metadata.py --force

# Fetch specific studies by ID
python fetch_metadata.py OSD-87 OSD-583 OSD-920

# Search OSDR for additional studies matching eye/SANS keywords
# and fetch any new ones found
python fetch_metadata.py --search

# Combine: re-fetch defaults AND search for more
python fetch_metadata.py --force --search
```

### What gets cached

Each study is saved as `data/metadata/OSD-NNN.json` containing:

- **Study details** — title, description, organism, tissue, assay type, mission, publication
- **File listing** — every file in the study with name, category, size, download URL, and access flags
- **Fetch timestamp**

A lightweight `data/index.json` tracks which studies are cached and their file counts.

---

## Configuration

All settings live in `config.py`:

```python
# Model preferences
OLLAMA_HOST         = "http://localhost:11434"
OLLAMA_MODEL        = "gemma4"           # preferred model
OLLAMA_FALLBACK_MODEL = "qwen3.6:latest" # used if preferred is unavailable

# Data paths (all gitignored)
DATA_DIR     = PROJECT_ROOT / "data"
METADATA_DIR = DATA_DIR / "metadata"

# Edit this list to change which studies are fetched by default
EYE_SANS_STUDY_IDS = [
    "OSD-679", "OSD-680", "OSD-681",   # Head-Down Tilt / ICP+IOP
    "OSD-583",                           # Intraocular pressure RR-9
    "OSD-758", "OSD-759",               # Artificial gravity retina
    "OSD-87",  "OSD-397",               # Mouse retina STS-135
    "OSD-194", "OSD-255", "OSD-557",    # Retina RR-3
    "OSD-100", "OSD-162",               # Mouse eye RR-1/RR-3
    "OSD-363", "OSD-364",               # Intracranial hypertension
]

# Keywords used for --search discovery and context scoring
EYE_SANS_KEYWORDS = [
    "eye", "retina", "optic", "intraocular", "intracranial",
    "SANS", "neuro-ocular", "vision", "photoreceptor", ...
]
```

---

## Curated Eye / SANS Studies

| Study ID | Title | Assay | Tissue |
|----------|-------|-------|--------|
| [OSD-679](https://osdr.nasa.gov/bio/repo/data/studies/OSD-679) | Head-Down Tilt — ICP + IOP + Retina | RNA-seq | Retina |
| [OSD-680](https://osdr.nasa.gov/bio/repo/data/studies/OSD-680) | Head-Down Tilt — ICP + IOP + Retina | Proteomics | Retina |
| [OSD-681](https://osdr.nasa.gov/bio/repo/data/studies/OSD-681) | Head-Down Tilt — ICP + IOP + Retina | Metabolomics | Retina |
| [OSD-583](https://osdr.nasa.gov/bio/repo/data/studies/OSD-583) | Ocular responses / IOP — RR-9 spaceflight | Physiological measurements | Eye |
| [OSD-758](https://osdr.nasa.gov/bio/repo/data/studies/OSD-758) | Artificial Gravity — Retina transcriptomics (spaceflight) | RNA-seq | Retina |
| [OSD-759](https://osdr.nasa.gov/bio/repo/data/studies/OSD-759) | Artificial Gravity — Retina transcriptomics (ground analog) | RNA-seq | Retina |
| [OSD-87](https://osdr.nasa.gov/bio/repo/data/studies/OSD-87)   | Spaceflight effects on mouse retina — STS-135 | Microarray | Retina |
| [OSD-397](https://osdr.nasa.gov/bio/repo/data/studies/OSD-397) | RNA-seq + RRBS on spaceflight mouse retina | RNA-seq + RRBS | Retina |
| [OSD-194](https://osdr.nasa.gov/bio/repo/data/studies/OSD-194) | RR-3-CASIS: Mouse retina transcriptomics | RNA-seq | Retina |
| [OSD-255](https://osdr.nasa.gov/bio/repo/data/studies/OSD-255) | Spaceflight — photoreceptor integrity + oxidative stress | RNA-seq | Retina |
| [OSD-557](https://osdr.nasa.gov/bio/repo/data/studies/OSD-557) | Spaceflight — photoreceptor integrity + oxidative stress (rep.) | RNA-seq | Retina |
| [OSD-100](https://osdr.nasa.gov/bio/repo/data/studies/OSD-100) | RR-1: Mouse eye transcriptomics + epigenomics | RNA-seq + RRBS | Eye |
| [OSD-162](https://osdr.nasa.gov/bio/repo/data/studies/OSD-162) | RR-3-CASIS: Mouse eye transcriptomics + proteomics | RNA-seq + MS | Eye |
| [OSD-363](https://osdr.nasa.gov/bio/repo/data/studies/OSD-363) | Idiopathic intracranial hypertension — gene expression | Microarray | CSF/Blood |
| [OSD-364](https://osdr.nasa.gov/bio/repo/data/studies/OSD-364) | Idiopathic intracranial hypertension — gene expression (rep.) | Microarray | CSF/Blood |

**Abbreviations:** ICP = intracranial pressure, IOP = intraocular pressure, RR = Rodent Research, RRBS = Reduced Representation Bisulfite Sequencing, MS = mass spectrometry

---

## How It Works

```
User question
     │
     ▼
build_context()          ← scores all cached studies by keyword + query relevance
     │                      selects top 8 most relevant studies
     ▼
Ollama API               ← system prompt + study context + conversation history
(gemma4 locally)
     │
     ▼
Streamed answer          ← tokens printed as they arrive
```

- **No external API calls at query time** — the LLM runs locally via ollama
- **Conversation memory** — last 10 turns are kept in context
- **Relevance scoring** — studies are ranked by overlap with SANS/eye keywords and the user's query words; the top 8 are injected as context
- **Graceful fallback** — if `gemma4` isn't installed, the chatbot checks for any available ollama model

### OSDR API endpoints used

| Purpose | Endpoint |
|---------|----------|
| File listing | `GET /osdr/data/osd/files/{numeric_id}/?page=1&size=500&all_files=true` |
| Study details | `GET /osdr/data/search?ffield=Accession&fvalue=OSD-87&size=1` |
| Keyword search | `GET /osdr/data/search?ffield=Study+Title&fvalue={keyword}&size=20` |

> Note: the files endpoint requires the **numeric** study ID (e.g. `87`), not the full accession string (`OSD-87`).

---

## Project Structure

```
OSDR_Chatbot/
├── chatbot.py          ← interactive chatbot (entry point)
├── fetch_metadata.py   ← download + cache OSDR study metadata
├── config.py           ← model, paths, curated study IDs, keywords
├── requirements.txt    ← requests, rich, ollama
├── README.md
├── .gitignore
└── data/               ← NOT in git (gitignored)
    ├── index.json      ← lightweight study index
    └── metadata/       ← one JSON file per OSD study
        ├── OSD-87.json
        ├── OSD-100.json
        └── ...
```

---

## Extending the Bot

**Add more studies**

Edit the `EYE_SANS_STUDY_IDS` list in `config.py`, then run:
```bash
python fetch_metadata.py
```

Or discover studies automatically:
```bash
python fetch_metadata.py --search
```

**Add more keywords**

Edit `EYE_SANS_KEYWORDS` in `config.py` to improve context scoring and `--search` discovery.

**Switch models**

Any model installed in ollama works:
```bash
ollama pull llama3.2:latest
python chatbot.py --model llama3.2:latest
```

---

## Background — What Is SANS?

**Space Associated Neuro-ocular Syndrome (SANS)** is a condition observed in a subset of astronauts after long-duration spaceflight. Symptoms include optic disc edema, globe flattening, choroidal folds, hyperopic shifts, and elevated intracranial pressure — potentially related to cephalad fluid shifts in microgravity. It is one of the top human health risks identified by NASA for long-duration missions.

This chatbot helps researchers navigate the OSDR studies most relevant to understanding the molecular, physiological, and structural changes underlying SANS.

**Further reading:**
- [NASA Human Research Program — SANS](https://www.nasa.gov/hrp/elements/sans)
- [OSDR Study Browser](https://osdr.nasa.gov/bio/repo/search)
- [NASA API Portal](https://api.nasa.gov/)

---

## License

This project is not affiliated with NASA. Data is fetched from the publicly accessible OSDR API.
