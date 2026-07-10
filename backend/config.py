from pathlib import Path

# --- Ollama ---
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "gemma4"                 # preferred chat model
OLLAMA_FALLBACK_MODEL = "qwen2.5:7b-instruct"
OLLAMA_EMBED_MODEL = "nomic-embed-text"  # local embedding model for RAG

# --- Data storage (gitignored) ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
METADATA_DIR = DATA_DIR / "metadata"
INDEX_FILE = DATA_DIR / "index.json"

# --- Vector store (ChromaDB) ---
CHROMA_DIR = DATA_DIR / "chroma"
CHROMA_COLLECTION = "osdr_studies"
RAG_TOP_K = 10                          # chunks retrieved per query

# --- OSDR API ---
OSDR_API_BASE = "https://osdr.nasa.gov/osdr/data"
OSDR_FILES_URL = f"{OSDR_API_BASE}/osd/files"
OSDR_SEARCH_URL = f"{OSDR_API_BASE}/search"
OSDR_STUDY_TYPE = "cgene"               # search `type` that filters to the OSD study index

# --- Curated eye/SANS studies (used by --curated fetch mode & optional relevance boost) ---
EYE_SANS_STUDY_IDS = [
    "OSD-679",   # Head-Down Tilt - Intracranial/Intraocular Pressures + Retina (RNA-seq)
    "OSD-680",   # Head-Down Tilt - Intracranial/Intraocular Pressures + Retina (proteomics)
    "OSD-681",   # Head-Down Tilt - Intracranial/Intraocular Pressures + Retina (metabolomics)
    "OSD-583",   # Mouse ocular responses / intraocular pressure - RR-9 spaceflight
    "OSD-758",   # Artificial Gravity - Retina transcriptomics (spaceflight)
    "OSD-759",   # Artificial Gravity - Retina transcriptomics (ground)
    "OSD-87",    # Spaceflight effects on mouse retina: histology, gene expression, epigenomics
    "OSD-397",   # RNA-seq + RRBS on spaceflight mouse retina
    "OSD-194",   # RR-3-CASIS: Mouse retina transcriptomics
    "OSD-255",   # Spaceflight - photoreceptor integrity + oxidative stress (retina)
    "OSD-557",   # Spaceflight - photoreceptor integrity + oxidative stress (retina, replicate)
    "OSD-100",   # RR-1: Mouse eye transcriptomics + epigenomics
    "OSD-162",   # RR-3-CASIS: Mouse eye transcriptomics + proteomics
    "OSD-363",   # Idiopathic intracranial hypertension - gene expression
    "OSD-364",   # Idiopathic intracranial hypertension - gene expression (replicate)
]

# Search keywords for --search discovery
EYE_SANS_KEYWORDS = [
    "eye", "retina", "optic", "intraocular", "intracranial",
    "SANS", "neuro-ocular", "vision", "photoreceptor", "choroidal",
    "ocular", "vitreous", "papilledema", "astronaut vision",
]
