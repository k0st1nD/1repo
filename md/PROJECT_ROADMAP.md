# 🗺️ Archivist Magika - Complete Project Roadmap

## 📌 Project Overview

**Goal:** Production-ready RAG система для semantic search по документам

**Approach:** Итеративная разработка с фокусом на качество

**Current Status:** 🎯 Planning complete, ready to start implementation

---

## 🎯 MVP v2.0 Scope (Week 1-2) ← CURRENT FOCUS

### What's Included:
✅ **PDF Processing** with enhancements:
  - OCR support (Tesseract) для сканированных PDF
  - Table extraction (pdfplumber)
  - Structure detection (главы/секции автоматически)
  - Deduplication (удаление дублей страниц)
  - PDF metadata extraction

✅ **Quality Metrics** (lightweight):
  - Метрики на каждом этапе pipeline
  - Warnings при проблемах качества
  - Summary report в конце
  - JSON files (no dashboard)

✅ **Complete Pipeline:**
```
PDF → structural → structure_detect → summarize → extended → finalize → chunk → embed → search
         ↓             ↓                              ↓
      + OCR        + chapters                    + dedup
      + tables     + sections
```

✅ **RAG Search:**
  - FAISS vector search
  - Filters по главам/секциям
  - Filter by has_table
  - Metadata-rich results

### What's NOT Included:
❌ Multi-source support (Confluence, DOCX, etc) → Post-MVP
❌ Quality monitoring dashboard (Grafana/Prometheus) → Post-MVP
❌ Advanced NER → Post-MVP
❌ Web UI → Post-MVP
❌ API → Post-MVP

### Timeline: **10.5-13 days** (was 10-12, +0.5-1 day for metrics)

### Success Criteria:
- [ ] Normal PDFs обрабатываются корректно
- [ ] Scanned PDFs распознаются через OCR
- [ ] Tables извлекаются и сохраняются
- [ ] Chapters/sections детектятся автоматически (>85% accuracy)
- [ ] Duplicates обнаруживаются
- [ ] RAG search возвращает релевантные результаты
- [ ] Можно фильтровать по главам/секциям

### Deliverables:
- Working pipeline (все 8 этапов)
- CLI интерфейс (run_mvp.py)
- Documentation (README + examples)
- Tests (basic coverage)

---

## 🧪 Phase 1: Testing & Polish (Week 3-4)

### Focus: Stability & Quality

**Tasks:**
- [ ] Comprehensive testing на 20+ книгах
- [ ] Bug fixing
- [ ] Performance optimization
- [ ] Documentation improvement
- [ ] Edge case handling
- [ ] Error messages improvement

**Deliverables:**
- Stable MVP v2.0
- Test coverage >70%
- Complete documentation
- Known issues documented

---

## 🔌 Phase 2: Multi-Source Support (Week 5-6)

### Focus: Source Adapters Architecture

**New Sources:**
1. **Confluence Wiki** ⭐
   - REST API export → dataset
   - HTML cleaning → Markdown
   - Page hierarchy → structure
   - Labels → metadata

2. **DOCX Files** ⭐
   - python-docx для parsing
   - Styles → structure detection
   - Comments/track changes support
   - Tables extraction

3. **TXT/Markdown** ⭐
   - Plain text files
   - Markdown parsing
   - Front matter metadata
   - Auto structure detection

4. **HTML/Web Pages**
   - Beautifulsoup parsing
   - CSS cleanup
   - Link preservation
   - Navigation structure

5. **Notion** (optional)
   - Notion API integration
   - Block hierarchy
   - Database properties

**Architecture:**
```
sources/
├── base.py                   # BaseSourceAdapter (abstract)
├── pdf/                      # Refactored from pipeline/
├── confluence/               # NEW
├── docx/                     # NEW
├── txt/                      # NEW
├── html/                     # NEW
└── notion/                   # NEW (optional)
```

**Unified Dataset Format:**
All sources → same dataset.jsonl format → reuse entire pipeline

**Deliverables:**
- Working adapters для 3+ sources
- Updated pipeline supports all sources
- Multi-source search (filter by source_type)
- Documentation per source

---

## 📊 Phase 3: Advanced Quality & Monitoring (Week 7-8)

### Focus: Production Observability & Dashboards

**Note:** Basic quality metrics уже в MVP v2.0. Эта фаза добавляет визуализацию и advanced features.

**Quality Dashboard:**
```
monitoring/
├── grafana_dashboards/       # Grafana configs
├── prometheus_exporters/     # Metrics exporters
└── alertmanager/             # Alert rules
```

**Advanced Metrics:**
- Real-time monitoring
- Temporal graphs (trends over time)
- Alerts в Slack/Email/PagerDuty
- Comparative analysis (версии датасетов)
- Performance profiling

**Validation:**
```
validation/
├── schema_validator.py       # JSON schema validation
├── quality_checker.py        # Quality thresholds
└── dataset_diff.py           # Version comparison
```

**Versioning:**
- Dataset versions (v1, v2, v3)
- A/B testing different strategies
- Rollback capability

**Deliverables:**
- Quality metrics dashboard
- Automated alerts
- Dataset versioning
- A/B testing framework

---

## 🚀 Phase 4: Advanced Features (Week 9-10)

### Focus: Enhanced Intelligence

**1. Named Entity Recognition (NER)**
```python
pipeline/am_entities.py
- Detect companies (Google, Netflix, ING)
- Detect technologies (Kubernetes, Jenkins)
- Detect people (Gene Kim, Nicole Forsgren)
- Detect metrics (deployment frequency, MTTR)
```

**2. Hierarchical Chunking**
```python
chunking/hierarchical_chunking.py
- Level 1: Section chunks (2000 tokens)
- Level 2: Paragraph chunks (512 tokens)
- Level 3: Sentence chunks (128 tokens)
- Links between levels
```

**3. Advanced Search**
```python
rag/
├── reranker.py               # Cross-encoder reranking
├── hybrid_search.py          # Keyword + semantic
└── query_expansion.py        # Query reformulation
```

**4. Code Detection**
```python
pipeline/am_code_extract.py
- Detect code blocks
- Language detection
- Syntax highlighting (optional)
- Preserve formatting
```

**Deliverables:**
- NER for domain entities
- Multi-level chunking
- Hybrid search
- Better search quality

---

## 🏭 Phase 5: Production Ready (Week 11-12)

### Focus: Deployment & Operations

**1. API Layer**
```
api/
├── rest/
│   ├── main.py               # FastAPI
│   ├── endpoints/
│   │   ├── search.py
│   │   ├── upload.py
│   │   └── status.py
│   └── auth.py               # Authentication
│
└── grpc/                     # Optional
    └── service.proto
```

**2. Web UI**
```
ui/
├── dashboard/                # React/Vue dashboard
│   ├── search-interface
│   ├── document-viewer
│   └── analytics
│
└── admin/                    # Management UI
    ├── dataset-management
    ├── pipeline-monitoring
    └── user-management
```

**3. Containerization**
```
docker/
├── Dockerfile
├── docker-compose.yml
└── k8s/
    ├── deployment.yaml
    ├── service.yaml
    └── ingress.yaml
```

**4. CI/CD**
```
.github/workflows/
├── ci.yml                    # Continuous Integration
├── tests.yml                 # Automated testing
└── deploy.yml                # Deployment
```

**Deliverables:**
- REST API (OpenAPI spec)
- Web UI для search + admin
- Docker images
- Kubernetes manifests
- CI/CD pipeline
- Deployment docs

---

## 📈 Phase 6: Optimizations (Ongoing)

### Focus: Performance & Scale

**1. Performance**
- [ ] Parallel processing (multiprocessing)
- [ ] GPU support для embeddings
- [ ] Quantized models для скорости
- [ ] Batch processing optimization
- [ ] Caching strategies

**2. Scalability**
- [ ] Distributed FAISS (multiple shards)
- [ ] Load balancing
- [ ] Horizontal scaling
- [ ] Database for metadata (PostgreSQL)
- [ ] Message queue (RabbitMQ/Kafka)

**3. Incremental Processing**
- [ ] Detect file changes (hash comparison)
- [ ] Process only new/changed files
- [ ] Incremental index updates
- [ ] Efficient re-indexing

**Deliverables:**
- 10x faster processing
- Handles 10,000+ documents
- Sub-second search latency
- Auto-scaling infrastructure

---

## 📊 Complete Timeline

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE              │ WEEKS  │ STATUS    │ DELIVERABLE       │
├─────────────────────────────────────────────────────────────┤
│ MVP v2.0           │ 1-2    │ 🎯 NEXT   │ PDF Pipeline      │
│ Testing & Polish   │ 3-4    │ ⏳ Future │ Stable MVP        │
│ Multi-Source       │ 5-6    │ ⏳ Future │ 3+ sources        │
│ Quality & Monitor  │ 7-8    │ ⏳ Future │ Observability     │
│ Advanced Features  │ 9-10   │ ⏳ Future │ NER, Hybrid       │
│ Production Ready   │ 11-12  │ ⏳ Future │ API, UI, Docker   │
│ Optimizations      │ 13+    │ ⏳ Future │ Scale & Speed     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Success Metrics by Phase

### MVP v2.0:
- ✅ Works with 10+ books
- ✅ OCR accuracy >80%
- ✅ Structure detection >85%
- ✅ Search returns relevant results

### Post-MVP:
- ✅ Supports 3+ source types
- ✅ Quality metrics >8.5/10
- ✅ Processes 100+ documents
- ✅ API response <500ms
- ✅ Search precision >0.8
- ✅ User satisfaction >4/5

### Production:
- ✅ 99.9% uptime
- ✅ Handles 1000+ documents
- ✅ Search latency <100ms
- ✅ API rate limit: 1000 req/min
- ✅ Auto-scaling works
- ✅ Zero data loss

---

## 📋 Key Documents Reference

1. **CONTEXT_TRANSFER_v2.0.md** - Current context, чек-листы, архитектура
2. **MVP_V2_IMPLEMENTATION_PLAN.md** - Детальный план MVP по дням
3. **am_config_v2.0.yaml** - Полная конфигурация MVP
4. **DATASET_EXAMPLES.md** - Примеры датасетов на всех этапах
5. **MULTI_SOURCE_ARCHITECTURE.md** - Post-MVP multi-source design
6. **PIPELINE_IMPROVEMENTS.md** - Обоснование улучшений

---

## 🚀 Getting Started

**Current Focus: MVP v2.0 (Week 1-2)**

### Next Steps:
1. ✅ Planning complete (this document)
2. ⏭️ Setup environment (Day 2)
3. ⏭️ Start implementation (Day 3)

### Day 2 Tasks:
- [ ] Install dependencies (requirements_v2.0.txt)
- [ ] Install Tesseract OCR
- [ ] Verify imports
- [ ] Setup project structure
- [ ] Create test PDFs

### Day 3 Tasks:
- [ ] Start am_structural.py enhancements
- [ ] Implement OCR support
- [ ] Implement table extraction
- [ ] Test on sample PDFs

---

## 💡 Key Principles

1. **Iterative Development** - Маленькие шаги, каждый шаг работает
2. **Quality First** - Лучше работающий минимум, чем сломанный максимум
3. **Test Early** - Тестируем каждый этап перед следующим
4. **Document Everything** - Документация = часть кода
5. **Refactor Later** - Сначала работает, потом красиво

---

**Version:** 1.0  
**Created:** 2025-01-28  
**Last Updated:** 2025-01-28
