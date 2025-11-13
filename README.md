# 📚 Archivist Magika MVP v2.0

**Semantic Search RAG Pipeline for Technical Books**

Transform PDF books into searchable knowledge bases with advanced metadata extraction, OCR support, and hybrid search capabilities.

---

## ✨ Features

### Core Pipeline
- **🔍 Robust PDF Extraction** - Multi-extractor chain with retry/fallback (pdfminer → pdfplumber → PyPDF2 → OCR)
- **📊 Table Extraction** - Structured table extraction with markdown export
- **👁️ OCR Support** - Tesseract OCR for scanned pages with confidence scoring
- **📖 Structure Detection** - Automatic chapter/section detection and TOC generation
- **📝 Summarization** - Extractive summaries (L1/L2)
- **🤖 LM-Enhanced Metadata** - Extended fields via Ollama (topics, entities, complexity, etc.)
- **🔄 Deduplication** - Exact + fuzzy duplicate detection
- **✂️ Smart Chunking** - Context-aware chunking with structure preservation
- **🎯 Vector Embeddings** - BGE-M3 embeddings with FAISS indexing

### Search Capabilities
- **🔎 Semantic Search** - Dense retrieval via FAISS
- **📋 Keyword Search** - BM25-based sparse retrieval
- **🔀 Hybrid Search** - Combined semantic + keyword (weighted)
- **🎨 Query Expansion** - Synonym-based query augmentation
- **🔧 Comprehensive Filters** - Filter by chapters, topics, complexity, tools, companies, etc.
- **📍 Context Expansion** - Retrieve surrounding chunks for extended context

### Quality & Robustness
- **✅ Quality Tracking** - Metrics tracking across all pipeline stages
- **🔁 Retry Logic** - Exponential backoff for transient failures
- **🛡️ Graceful Degradation** - Partial results better than nothing
- **📊 Threshold Checking** - Automated quality validation

---

## 🚀 Quick Start

### Prerequisites

**System Requirements:**
- Python 3.8+
- Tesseract OCR (for scanned PDFs)
- Poppler utils (for PDF to image conversion)
- Ollama (for LM-enhanced metadata)

**Install System Dependencies:**

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils

# macOS
brew install tesseract poppler

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/archivist-magika.git
cd archivist-magika

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements_v2.0.txt

# Verify installation
python -c "import faiss; import sentence_transformers; print('✓ All dependencies installed')"
```

### Basic Usage

**1. Process a single PDF:**

```bash
python run_mvp.py -i data/sources/pdf/accelerate.pdf
```

This will:
- Extract text/tables with OCR fallback
- Detect chapters and sections
- Generate summaries
- Add LM-enhanced metadata
- Create chunks with embeddings
- Build FAISS index

**2. Search the index:**

```bash
python rag/search.py -i accelerate -q "deployment frequency metrics"
```

**3. Search with filters:**

```bash
python rag/search.py -i accelerate -q "architecture patterns" \
  --chapter "Chapter 5" \
  --complexity intermediate \
  --has-diagram
```

---

## 📖 Usage Examples

### Pipeline Operations

**Process a directory of PDFs:**

```bash
python run_mvp.py -i data/sources/pdf/ --batch
```

**Resume from specific stage:**

```bash
# If you already have structural datasets, start from structure detection
python run_mvp.py -i data/datasets/structural/book.dataset.jsonl \
  --start structure_detect
```

**Run partial pipeline:**

```bash
# Only extract structure, don't embed
python run_mvp.py -i book.pdf --start structural --end finalize
```

**Dry run (plan only):**

```bash
python run_mvp.py -i book.pdf --dry-run
```

### Search Operations

**Semantic search:**

```bash
python rag/search.py -i accelerate -q "continuous delivery practices" -k 10
```

**Hybrid search (semantic + keyword):**

```bash
python rag/search.py -i accelerate -q "DevOps metrics" --hybrid
```

**Search with context expansion:**

```bash
python rag/search.py -i accelerate -q "deployment pipeline" \
  --expand-context 2
```

**Advanced filtering:**

```bash
python rag/search.py -i accelerate \
  -q "microservices architecture" \
  --domain devops \
  --content-type case_study \
  --has-code \
  --topic "architecture" --topic "scalability"
```

### Quality Tracking

**Generate quality report:**

```bash
python run_mvp.py --quality-report
```

**Check specific metrics:**

```bash
python tools/quality_tracker.py report -s structural
```

**Compare sources:**

```bash
python tools/quality_tracker.py compare -s extended \
  --sources book1 book2 book3
```

---

## 🏗️ Architecture

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────┐
│  PDF Input                                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: Structural Extraction (am_structural_robust.py)       │
│  ─────────────────────────────────────────────────────────────  │
│  • Multi-extractor chain: pdfminer → pdfplumber → PyPDF2 → OCR │
│  • Table extraction (pdfplumber)                                │
│  • Smart blank page detection                                   │
│  • Retry logic with exponential backoff                         │
│  Output: structural/*.dataset.jsonl                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: Structure Detection (am_structure_detect.py)          │
│  ─────────────────────────────────────────────────────────────  │
│  • Chapter detection (regex + heuristics)                       │
│  • Section detection (numbered, Title Case)                     │
│  • TOC generation                                               │
│  • Section path updates                                         │
│  Output: structured/*.dataset.jsonl                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 3: Summarization (am_summarize.py)                       │
│  ─────────────────────────────────────────────────────────────  │
│  • L1 summary (300 chars)                                       │
│  • L2 summary (900 chars) - optional                            │
│  • Extractive summarization                                     │
│  Output: summarized/*.dataset.jsonl                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4: Extended Fields (am_extended.py)                      │
│  ─────────────────────────────────────────────────────────────  │
│  • Deduplication (exact + fuzzy)                                │
│  • LM-enhanced metadata via Ollama:                             │
│    - content_type, domain, complexity                           │
│    - entities (companies, people, technologies, etc)            │
│    - actionable (best practices, antipatterns)                  │
│    - topics, key concepts, tools                                │
│  Output: extended/*.dataset.jsonl                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 5: Finalization (am_finalize.py)                         │
│  ─────────────────────────────────────────────────────────────  │
│  • Schema validation                                            │
│  • Extended fields validation                                   │
│  • Policy checks                                                │
│  • Manifest SHA256 recalculation                                │
│  Output: final/*.dataset.jsonl                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 6: Chunking (am_chunk.py)                                │
│  ─────────────────────────────────────────────────────────────  │
│  • Smart chunking with overlap                                  │
│  • Structure context: [BOOK | CHAPTER | SECTION]               │
│  • Metadata preservation                                        │
│  • Table preservation                                           │
│  Output: chunks/*.jsonl                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 7: Embedding (am_embed.py)                               │
│  ─────────────────────────────────────────────────────────────  │
│  • BGE-M3 embeddings (1024 dim)                                 │
│  • FAISS index creation                                         │
│  • Metadata storage                                             │
│  Output: indexes/faiss/*.index + metadata/*.pkl                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Search (rag/search.py)                                         │
│  ─────────────────────────────────────────────────────────────  │
│  • Semantic search (FAISS)                                      │
│  • Keyword search (BM25)                                        │
│  • Hybrid search                                                │
│  • Comprehensive filtering                                      │
│  • Context expansion                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Extended Fields Schema

```json
{
  "extended_fields": {
    "content_type": "case_study",
    "domain": "devops",
    "complexity": "intermediate",
    
    "entities": {
      "companies": ["Netflix", "Amazon"],
      "people": ["Gene Kim"],
      "products": ["Jenkins", "Docker"],
      "technologies": ["Kubernetes", "Terraform"],
      "frameworks": ["DevOps", "Agile"],
      "methodologies": ["CI/CD", "Infrastructure as Code"]
    },
    
    "technical": {
      "has_code": true,
      "has_formulas": false,
      "has_diagram": true,
      "programming_languages": ["Python", "Go"]
    },
    
    "actionable": {
      "has_best_practices": true,
      "has_antipatterns": true,
      "has_instructions": true
    },
    
    "business": {
      "has_metrics": true,
      "metrics": ["deployment frequency", "lead time"],
      "has_case_study": true,
      "case_study_company": "Netflix"
    },
    
    "content_analysis": {
      "topics": ["architecture", "deployment", "monitoring"],
      "key_concepts": ["continuous delivery", "microservices"],
      "problem_statement": "...",
      "solution_approach": "..."
    },
    
    "tools_mentioned": ["Jenkins", "Kubernetes", "Terraform"]
  }
}
```

---

## 📊 Quality Metrics

### Per-Stage Thresholds

**Structural:**
- Min success ratio: 95%
- Max empty pages: 10%
- Min avg page length: 500 chars

**Extended:**
- Max duplicates: 5%
- Min extended fields coverage: 70%
- Min topics per page: 1

**Chunking:**
- Min chunk length: 100 chars
- Max chunk length: 2000 chars

**Embedding:**
- Min embedding success: 99%

---

## 🔧 Configuration

Edit `config/am_config_v2.0.yaml`:

```yaml
pipeline:
  structural:
    ocr:
      enabled: true
      languages: ['eng']
      dpi: 300
    tables:
      enabled: true
      min_rows: 2
  
  extended:
    ollama:
      base_url: "http://localhost:11434"
      model: "llama3.2:3b"
      timeout: 60
  
  chunk:
    chunk_size: 512
    overlap: 50
  
  embed:
    model: "BAAI/bge-m3"
    batch_size: 32
```

---

## 🧪 Testing

**Run all tests:**

```bash
python tests/test_basic.py
```

**Run specific test class:**

```bash
python -m unittest tests.test_basic.TestDatasetIO
```

---

## 📁 Project Structure

```
archivist-magika/
├── core/
│   ├── am_common.py              # Core utilities
│   ├── am_config.yaml            # Configuration
│   └── am_logging.py             # Logging setup
│
├── pipeline/
│   ├── am_structural_robust.py   # Stage 1: Extraction
│   ├── am_structure_detect.py    # Stage 2: Structure
│   ├── am_summarize.py           # Stage 3: Summaries
│   ├── am_extended.py            # Stage 4: Extended fields
│   ├── am_finalize.py            # Stage 5: Validation
│   ├── am_chunk.py               # Stage 6: Chunking
│   └── am_embed.py               # Stage 7: Embeddings
│
├── rag/
│   ├── search.py                 # Search engine
│   └── index_manager.py          # Index management
│
├── tools/
│   ├── quality_tracker.py        # Quality metrics
│   └── validate.py               # Validation tools
│
├── tests/
│   └── test_basic.py             # Unit tests
│
├── data/
│   ├── sources/pdf/              # Input PDFs
│   ├── datasets/                 # Processed datasets
│   ├── indexes/                  # FAISS indexes
│   └── quality/                  # Quality reports
│
├── config/
│   └── am_config_v2.0.yaml       # Configuration
│
├── run_mvp.py                    # Main orchestrator
├── requirements_v2.0.txt         # Dependencies
└── README.md                     # This file
```

---

## 🐛 Troubleshooting

### Common Issues

**1. OCR not working:**

```bash
# Check Tesseract installation
tesseract --version

# Install language data
sudo apt-get install tesseract-ocr-eng
```

**2. FAISS import error:**

```bash
# Use CPU version if GPU not available
pip uninstall faiss-gpu
pip install faiss-cpu
```

**3. Ollama connection failed:**

```bash
# Start Ollama service
ollama serve

# Pull model
ollama pull llama3.2:3b
```

**4. Out of memory during embedding:**

```yaml
# Reduce batch size in config
embed:
  batch_size: 8  # Default: 32
```

**5. Poor search results:**

```bash
# Check index exists
python rag/index_manager.py list

# Rebuild index if corrupted
python run_mvp.py -i book.pdf --start chunk --end embed
```

### Performance Tips

**For large PDFs (500+ pages):**
- Disable OCR if not needed: `--no-ocr`
- Increase batch size for embedding
- Use SSD for data directory

**For many PDFs:**
- Use batch mode with `--batch`
- Enable quality checking to catch issues early
- Monitor disk space (indexes can be large)

---

## 📈 Performance Benchmarks

**Single PDF Processing (300 pages):**
- Structural: ~2 minutes
- Structure detect: ~30 seconds
- Extended fields: ~10 minutes (with LM)
- Chunking + Embedding: ~2 minutes

**Search Performance:**
- Semantic search: <100ms for 10K chunks
- Hybrid search: <150ms for 10K chunks

**Memory Usage:**
- Embedding model: ~2GB RAM
- FAISS index: ~10MB per 10K chunks
- LM (Ollama): ~4GB RAM

---

## 🗺️ Roadmap

### v2.1 (Next Release)
- [ ] Multi-format support (DOCX, HTML, Markdown)
- [ ] Advanced reranking with cross-encoders
- [ ] Query reformulation
- [ ] Result clustering

### v2.5 (Future)
- [ ] REST API
- [ ] Web UI
- [ ] Real-time updates
- [ ] Multi-modal search (text + images)

### v3.0 (Long-term)
- [ ] Graph-based RAG
- [ ] Multi-hop reasoning
- [ ] Production deployment (Docker/K8s)
- [ ] Distributed processing

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🙏 Acknowledgments

- **BGE-M3** - Embedding model by BAAI
- **FAISS** - Vector search by Meta AI
- **pdfplumber** - PDF processing library
- **Tesseract OCR** - Google's OCR engine
- **Ollama** - Local LLM platform

---

## 📧 Contact

For questions or support:
- Open an issue on GitHub
- Email: your.email@example.com

---

**Version:** 2.0.0  
**Last Updated:** 2025-01-28

Made with ❤️ for knowledge seekers