# 📊 Archivist Magika MVP v2.0 - Dataset Examples

Complete pipeline transformation from PDF to RAG search with all v2.0 features.

---

## 📖 Source: PDF Book "Accelerate" (DevOps Research)

**Page 42:**
```
Chapter 5: Architecture

High performers use a loosely coupled architecture. This allows teams 
to test and deploy their applications on demand, without requiring 
orchestration with other services.

Figure 5.1 shows the impact of architecture on deployment frequency.
Organizations with well-designed architecture can deploy 200x more 
frequently than those with tightly coupled systems.

Table 5.1: Deployment Metrics
╔═══════════════╦═══════════════╗
║ Performer     ║ Deploys/day   ║
╠═══════════════╬═══════════════╣
║ High          ║ 200+          ║
║ Medium        ║ 1-7/week      ║
║ Low           ║ 1/month       ║
╚═══════════════╩═══════════════╝
```

---

## ⚙️ STAGE 1: STRUCTURAL (am_structural_robust.py)

**Output:** `data/datasets/structural/accelerate.dataset.jsonl`

### Header:
```jsonl
{
  "segment_id": "__header__",
  "source": {
    "title": "Accelerate",
    "author": "Nicole Forsgren, Jez Humble, Gene Kim",
    "file_name": "accelerate.pdf",
    "file_size": 5242880,
    "pages": 257
  },
  "book": "accelerate",
  "total_cards": 257,
  "segment_ids": ["00001", "00002", ..., "00257"],
  "dataset_created_at": "2025-01-28T10:30:00Z",
  "pdf_sha256": "a1b2c3d4e5f6...",
  "version": "2.0.0",
  "product": "archivist magika 2.0.0"
}
```

### Page Card (with table):
```jsonl
{
  "segment_id": "00042",
  "page_num": 42,
  "segment": "Chapter 5: Architecture\n\nHigh performers use a loosely coupled architecture. This allows teams to test and deploy their applications on demand, without requiring orchestration with other services.\n\nFigure 5.1 shows the impact of architecture on deployment frequency. Organizations with well-designed architecture can deploy 200x more frequently than those with tightly coupled systems.\n\nTable 5.1: Deployment Metrics\n- High performers: 200+ deploys/day\n- Medium: 1-7 deploys/week\n- Low: 1 deploy/month",
  "source_file": "accelerate.pdf",
  "extraction_method": "pdfminer",
  "ocr_used": false,
  "has_table": true,
  "tables": [
    {
      "table_id": "table_1",
      "rows": 4,
      "cols": 2,
      "data": [
        ["Performer", "Deploys/day"],
        ["High", "200+"],
        ["Medium", "1-7/week"],
        ["Low", "1/month"]
      ],
      "markdown": "| Performer | Deploys/day |\n|---|---|\n| High | 200+ |\n| Medium | 1-7/week |\n| Low | 1/month |"
    }
  ],
  "table_count": 1
}
```

### Page Card (OCR example - scanned page):
```jsonl
{
  "segment_id": "00015",
  "page_num": 15,
  "segment": "Introduction to Continuous Delivery\n\nContinuous delivery is the ability to get changes of all types—including new features, configuration changes, bug fixes, and experiments—into production safely and quickly in a sustainable way.",
  "source_file": "accelerate.pdf",
  "extraction_method": "ocr",
  "ocr_used": true,
  "ocr_confidence": 0.87,
  "has_table": false
}
```

### Audit:
```jsonl
{
  "segment_id": "__audit__",
  "total_cards": 257,
  "success_pages": 255,
  "failed_pages": 2,
  "empty_pages": 5,
  "error_pages": 2,
  "extraction_methods": {
    "pdfminer": 240,
    "pdfplumber": 10,
    "ocr": 5
  },
  "ocr_used_count": 5,
  "ocr_avg_confidence": 0.85,
  "tables_extracted": 23,
  "stage": "structural",
  "version": "2.0.0",
  "created_at": "2025-01-28T10:30:05Z"
}
```

**Key Features:**
- ✅ `extraction_method` - which extractor succeeded (pdfminer/pdfplumber/pypdf2/ocr)
- ✅ `ocr_used` + `ocr_confidence` - OCR tracking
- ✅ `tables` - structured table data with markdown
- ✅ Extraction statistics in audit

---

## 📖 STAGE 2: STRUCTURE DETECTION (am_structure_detect.py)

**Output:** `data/datasets/structured/accelerate.dataset.jsonl`

### Header (with TOC):
```jsonl
{
  "segment_id": "__header__",
  "source": {...},
  "book": "accelerate",
  "total_cards": 257,
  "toc": [
    {
      "level": 1,
      "title": "Chapter 1: Introduction",
      "page": 1,
      "segment_id": "00001"
    },
    {
      "level": 1,
      "title": "Chapter 5: Architecture",
      "page": 42,
      "segment_id": "00042"
    },
    {
      "level": 2,
      "title": "5.1 Loosely Coupled Systems",
      "page": 42,
      "segment_id": "00042"
    },
    {
      "level": 2,
      "title": "5.2 Team Autonomy",
      "page": 45,
      "segment_id": "00045"
    }
  ],
  "chapters_detected": 8,
  "sections_detected": 34,
  "version": "2.0.0"
}
```

### Page Card (with chapter/section):
```jsonl
{
  "segment_id": "00042",
  "page_num": 42,
  "segment": "Chapter 5: Architecture\n\nHigh performers use a loosely coupled architecture...",
  "source_file": "accelerate.pdf",
  "extraction_method": "pdfminer",
  "ocr_used": false,
  "chapter_num": 5,
  "chapter_title": "Chapter 5: Architecture",
  "section_num": "5.1",
  "section_title": "Loosely Coupled Systems",
  "section_path": "chapter/5/section/5.1",
  "has_table": true,
  "tables": [{...}]
}
```

**Key Features:**
- ✅ TOC in header
- ✅ `chapter_title`, `section_title` detected
- ✅ `section_path` - hierarchical path

---

## 📝 STAGE 3: SUMMARIZATION (am_summarize.py)

**Output:** `data/datasets/summarized/accelerate.dataset.jsonl`

### Page Card (with summaries):
```jsonl
{
  "segment_id": "00042",
  "page_num": 42,
  "segment": "Chapter 5: Architecture\n\nHigh performers use a loosely coupled architecture...",
  "chapter_title": "Chapter 5: Architecture",
  "section_title": "Loosely Coupled Systems",
  "summary": {
    "l1": "High performers use loosely coupled architecture enabling independent deployment. Organizations with good architecture deploy 200x more frequently.",
    "l1_length": 150
  },
  "has_table": true,
  "tables": [{...}]
}
```

**Key Features:**
- ✅ `summary.l1` - 300 char extractive summary
- ✅ Optional `summary.l2` - 900 char summary (if enabled)

---

## 🤖 STAGE 4: EXTENDED (am_extended.py) ⭐ **KEY STAGE**

**Output:** `data/datasets/extended/accelerate.dataset.jsonl`

### Page Card (with extended_fields - LM extracted):
```jsonl
{
  "segment_id": "00042",
  "page_num": 42,
  "segment": "Chapter 5: Architecture\n\nHigh performers use a loosely coupled architecture...",
  "chapter_title": "Chapter 5: Architecture",
  "section_title": "Loosely Coupled Systems",
  "summary": {
    "l1": "High performers use loosely coupled architecture..."
  },
  "has_table": true,
  "tables": [{...}],
  "extended_fields": {
    "content_type": "research",
    "domain": "devops",
    "complexity": "intermediate",
    "entities": {
      "companies": [],
      "people": [],
      "products": [],
      "technologies": ["microservices", "containerization"],
      "frameworks": ["DevOps", "Continuous Delivery"],
      "methodologies": ["CI/CD", "Agile"]
    },
    "technical": {
      "has_code": false,
      "has_formulas": false,
      "has_diagram": true,
      "programming_languages": []
    },
    "actionable": {
      "has_best_practices": true,
      "has_antipatterns": false,
      "has_instructions": true
    },
    "business": {
      "has_metrics": true,
      "metrics": ["deployment frequency", "lead time"],
      "has_case_study": false,
      "case_study_company": null
    },
    "content_analysis": {
      "topics": ["architecture", "deployment", "team autonomy", "scalability"],
      "key_concepts": ["loosely coupled", "autonomous teams", "deployment frequency"],
      "problem_statement": "Tightly coupled systems limit deployment frequency and team autonomy",
      "solution_approach": "Loosely coupled architecture enables independent deployment and faster delivery"
    },
    "tools_mentioned": []
  },
  "dedup_info": {
    "is_duplicate": false,
    "duplicate_of": null,
    "similarity_score": null
  }
}
```

### Page Card (case study example):
```jsonl
{
  "segment_id": "00044",
  "page_num": 44,
  "segment": "Case Study: ING Bank\n\nING Netherlands restructured their organization around small, autonomous squads. Each squad owns their services end-to-end...",
  "chapter_title": "Chapter 5: Architecture",
  "section_title": "5.2 Team Autonomy",
  "summary": {
    "l1": "ING Bank restructured into autonomous squads owning services end-to-end, increasing deployment frequency from once per 4 weeks to multiple times daily."
  },
  "extended_fields": {
    "content_type": "case_study",
    "domain": "devops",
    "complexity": "intermediate",
    "entities": {
      "companies": ["ING Bank", "ING Netherlands"],
      "people": [],
      "products": [],
      "technologies": [],
      "frameworks": ["DevOps", "Agile"],
      "methodologies": ["squad model", "end-to-end ownership"]
    },
    "technical": {
      "has_code": false,
      "has_formulas": false,
      "has_diagram": false,
      "programming_languages": []
    },
    "actionable": {
      "has_best_practices": true,
      "has_antipatterns": false,
      "has_instructions": false
    },
    "business": {
      "has_metrics": true,
      "metrics": ["deployment frequency"],
      "has_case_study": true,
      "case_study_company": "ING Bank"
    },
    "content_analysis": {
      "topics": ["organizational structure", "autonomous teams", "squad model"],
      "key_concepts": ["autonomous squads", "end-to-end ownership", "deployment frequency"],
      "problem_statement": "Slow deployment frequency (once per 4 weeks)",
      "solution_approach": "Restructure into autonomous squads with end-to-end ownership"
    },
    "tools_mentioned": []
  },
  "dedup_info": {
    "is_duplicate": false
  }
}
```

### Page Card (programming book example):
```jsonl
{
  "segment_id": "00123",
  "page_num": 123,
  "segment": "# Python Async Programming\n\nimport asyncio\n\nasync def fetch_data(url):\n    async with aiohttp.ClientSession() as session:\n        async with session.get(url) as response:\n            return await response.json()\n\nThe async/await syntax enables concurrent I/O operations...",
  "chapter_title": "Chapter 8: Asynchronous Programming",
  "extended_fields": {
    "content_type": "tutorial",
    "domain": "programming",
    "complexity": "intermediate",
    "entities": {
      "companies": [],
      "people": [],
      "products": ["aiohttp"],
      "technologies": ["Python", "asyncio"],
      "frameworks": [],
      "methodologies": ["asynchronous programming"]
    },
    "technical": {
      "has_code": true,
      "has_formulas": false,
      "has_diagram": false,
      "programming_languages": ["Python"]
    },
    "actionable": {
      "has_best_practices": true,
      "has_antipatterns": false,
      "has_instructions": true
    },
    "business": {
      "has_metrics": false,
      "metrics": [],
      "has_case_study": false,
      "case_study_company": null
    },
    "content_analysis": {
      "topics": ["async programming", "concurrency", "I/O operations"],
      "key_concepts": ["async/await", "event loop", "coroutines"],
      "problem_statement": "Blocking I/O limits application performance",
      "solution_approach": "Use async/await for concurrent I/O operations"
    },
    "tools_mentioned": ["asyncio", "aiohttp"]
  }
}
```

### Audit (with dedup stats):
```jsonl
{
  "segment_id": "__audit__",
  "total_cards": 257,
  "dedup_stats": {
    "exact_duplicates": 3,
    "fuzzy_duplicates": 5,
    "total_duplicates": 8,
    "duplicate_ratio": 0.031
  },
  "continuity_stats": {
    "gaps_detected": 2,
    "gap_pages": [43, 156]
  },
  "extended_extraction": {
    "pages_with_extended_fields": 245,
    "coverage_ratio": 0.953,
    "lm_model": "qwen2.5:7b",
    "extraction_time_sec": 1250
  },
  "stage": "extended",
  "version": "2.0.0"
}
```

**Key Features:**
- ✅ `extended_fields` - rich LM-extracted metadata
- ✅ `content_type` - theory/practice/case_study/tutorial/reference
- ✅ `domain` - devops/architecture/programming/security/etc.
- ✅ `complexity` - beginner/intermediate/advanced
- ✅ `entities` - companies, people, technologies, frameworks
- ✅ `technical` - code detection, programming languages
- ✅ `actionable` - best practices, antipatterns, instructions
- ✅ `business` - metrics, case studies
- ✅ `content_analysis` - topics, key concepts, problem/solution
- ✅ `tools_mentioned` - specific tools referenced
- ✅ `dedup_info` - duplicate detection results

---

## ✅ STAGE 5: FINALIZE (am_finalize.py)

**Output:** `data/datasets/final/accelerate.dataset.jsonl`

### Audit (validated):
```jsonl
{
  "segment_id": "__audit__",
  "total_cards": 257,
  "validation": {
    "passed": true,
    "errors": [],
    "warnings": [
      "Page 15: low OCR confidence (0.65)"
    ]
  },
  "dedup_stats": {...},
  "extended_extraction": {...},
  "finalized_at": "2025-01-28T10:45:00Z",
  "stage": "finalize",
  "version": "2.0.0"
}
```

### Footer (with manifest):
```jsonl
{
  "segment_id": "__footer__",
  "manifest_sha256": "x9y8z7...",
  "created_at": "2025-01-28T10:45:00Z",
  "version": "2.0.0",
  "product": "archivist magika 2.0.0"
}
```

**Key Features:**
- ✅ Schema validation
- ✅ Extended fields validation
- ✅ Policy checks
- ✅ Manifest SHA256 recalculated

---

## 🧩 STAGE 6: CHUNKING (am_chunk.py)

**Output:** `data/datasets/chunks/accelerate.chunks.jsonl`

### Chunk (research content):
```jsonl
{
  "chunk_id": "accelerate_00042_chunk_001",
  "book": "accelerate",
  "source_segments": ["00042"],
  "text": "[BOOK: Accelerate | CHAPTER: Chapter 5: Architecture | SECTION: 5.1 Loosely Coupled Systems]\n\nHigh performers use a loosely coupled architecture. This allows teams to test and deploy their applications on demand, without requiring orchestration with other services.\n\nFigure 5.1 shows the impact of architecture on deployment frequency. Organizations with well-designed architecture can deploy 200x more frequently than those with tightly coupled systems.\n\nTable 5.1: Deployment Metrics\n- High performers: 200+ deploys/day\n- Medium: 1-7 deploys/week\n- Low: 1 deploy/month",
  "char_count": 512,
  "metadata": {
    "book": "accelerate",
    "chapter_num": 5,
    "chapter_title": "Chapter 5: Architecture",
    "section_num": "5.1",
    "section_title": "Loosely Coupled Systems",
    "page_num": 42,
    "has_table": true,
    "has_code": false,
    "has_diagram": true,
    "extended_fields": {
      "content_type": "research",
      "domain": "devops",
      "complexity": "intermediate",
      "topics": ["architecture", "deployment", "team autonomy"],
      "key_concepts": ["loosely coupled", "deployment frequency"],
      "entities": {
        "technologies": ["microservices"],
        "frameworks": ["DevOps"]
      },
      "business": {
        "has_metrics": true,
        "metrics": ["deployment frequency"]
      }
    }
  },
  "context": {
    "prev_chunk_id": "accelerate_00041_chunk_002",
    "next_chunk_id": "accelerate_00042_chunk_002"
  }
}
```

### Chunk (case study):
```jsonl
{
  "chunk_id": "accelerate_00044_chunk_001",
  "book": "accelerate",
  "source_segments": ["00044"],
  "text": "[BOOK: Accelerate | CHAPTER: Chapter 5: Architecture | SECTION: 5.2 Team Autonomy]\n\nCase Study: ING Bank\n\nING Netherlands restructured their organization around small, autonomous squads. Each squad owns their services end-to-end, from development to production. This enabled them to increase deployment frequency from once every 4 weeks to multiple times per day.\n\nKey Results:\n- Deployment frequency: 4 weeks → multiple/day\n- Team autonomy: increased\n- Time to market: reduced by 70%",
  "char_count": 485,
  "metadata": {
    "book": "accelerate",
    "chapter_num": 5,
    "chapter_title": "Chapter 5: Architecture",
    "section_num": "5.2",
    "section_title": "Team Autonomy",
    "page_num": 44,
    "has_table": false,
    "has_code": false,
    "extended_fields": {
      "content_type": "case_study",
      "domain": "devops",
      "complexity": "intermediate",
      "topics": ["organizational structure", "autonomous teams"],
      "key_concepts": ["autonomous squads", "end-to-end ownership"],
      "entities": {
        "companies": ["ING Bank"],
        "methodologies": ["squad model"]
      },
      "business": {
        "has_metrics": true,
        "metrics": ["deployment frequency", "time to market"],
        "has_case_study": true,
        "case_study_company": "ING Bank"
      }
    }
  }
}
```

### Chunk (code example):
```jsonl
{
  "chunk_id": "python_book_00123_chunk_001",
  "book": "python_async",
  "source_segments": ["00123"],
  "text": "[BOOK: Python Async Programming | CHAPTER: Chapter 8: Asynchronous Programming]\n\n# Python Async Programming\n\nimport asyncio\nimport aiohttp\n\nasync def fetch_data(url):\n    async with aiohttp.ClientSession() as session:\n        async with session.get(url) as response:\n            return await response.json()\n\nThe async/await syntax enables concurrent I/O operations without blocking the main thread. This is essential for high-performance web applications.",
  "char_count": 398,
  "metadata": {
    "book": "python_async",
    "chapter_num": 8,
    "chapter_title": "Chapter 8: Asynchronous Programming",
    "page_num": 123,
    "has_table": false,
    "has_code": true,
    "extended_fields": {
      "content_type": "tutorial",
      "domain": "programming",
      "complexity": "intermediate",
      "topics": ["async programming", "concurrency"],
      "key_concepts": ["async/await", "coroutines"],
      "entities": {
        "technologies": ["Python", "asyncio"],
        "products": ["aiohttp"]
      },
      "technical": {
        "has_code": true,
        "programming_languages": ["Python"]
      },
      "tools_mentioned": ["asyncio", "aiohttp"]
    }
  }
}
```

**Key Features:**
- ✅ Structure context: `[BOOK | CHAPTER | SECTION]`
- ✅ `metadata.extended_fields` - full LM metadata preserved
- ✅ `metadata.chapter_title`, `section_title` - structure info
- ✅ `context` - links to prev/next chunks
- ✅ Chunk size ~512 chars (configurable)

---

## 🔢 STAGE 7: EMBEDDING (am_embed.py)

**Output 1:** `data/indexes/faiss/accelerate.faiss` (binary FAISS index)

**Output 2:** `data/indexes/metadata/accelerate.pkl` (metadata pickle)

### Metadata structure:
```python
[
  {
    "chunk_id": "accelerate_00042_chunk_001",
    "text": "[BOOK: Accelerate | CHAPTER: Chapter 5...]...",
    "metadata": {
      "book": "accelerate",
      "chapter_title": "Chapter 5: Architecture",
      "section_title": "5.1 Loosely Coupled Systems",
      "page_num": 42,
      "has_table": True,
      "has_code": False,
      "extended_fields": {
        "content_type": "research",
        "domain": "devops",
        "complexity": "intermediate",
        "topics": ["architecture", "deployment"],
        "entities": {
          "technologies": ["microservices"]
        },
        "business": {
          "has_metrics": True,
          "metrics": ["deployment frequency"]
        }
      }
    },
    "context": {
      "prev_chunk_id": "...",
      "next_chunk_id": "..."
    }
  },
  # ... 486 more chunks
]
```

**Key Features:**
- ✅ FAISS index: 1024-dim vectors (bge-m3)
- ✅ Metadata: full structure + extended_fields
- ✅ Fast lookup: vector_id → metadata

---

## 🔍 STAGE 8: SEARCH (rag/search.py)

### Example 1: Simple search
```bash
python rag/search.py -i accelerate -q "How to measure deployment frequency?"
```

**Result:**
```json
{
  "query": "How to measure deployment frequency?",
  "total_results": 3,
  "search_method": "semantic",
  "results": [
    {
      "chunk_id": "accelerate_00042_chunk_001",
      "score": 0.89,
      "text": "[BOOK: Accelerate | CHAPTER: Chapter 5: Architecture]\n\nHigh performers use a loosely coupled architecture...",
      "metadata": {
        "chapter_title": "Chapter 5: Architecture",
        "page_num": 42,
        "has_table": true,
        "extended_fields": {
          "content_type": "research",
          "domain": "devops",
          "topics": ["architecture", "deployment"],
          "business": {
            "has_metrics": true,
            "metrics": ["deployment frequency"]
          }
        }
      }
    },
    {
      "chunk_id": "accelerate_00028_chunk_001",
      "score": 0.82,
      "text": "[BOOK: Accelerate | CHAPTER: Chapter 3: Measuring Performance]\n\nDeployment frequency is measured...",
      "metadata": {
        "chapter_title": "Chapter 3: Measuring Performance",
        "page_num": 28,
        "extended_fields": {
          "content_type": "theory",
          "domain": "devops",
          "topics": ["metrics", "measurement"]
        }
      }
    }
  ]
}
```

---

### Example 2: Search with filters
```bash
python rag/search.py -i accelerate \
  -q "architecture patterns" \
  --content-type case_study \
  --domain devops \
  --complexity intermediate \
  --has-metrics
```

**Result:**
```json
{
  "query": "architecture patterns",
  "filters_applied": true,
  "filters": {
    "content_type": "case_study",
    "domain": "devops",
    "complexity": "intermediate",
    "has_metrics": true
  },
  "total_results": 2,
  "results": [
    {
      "chunk_id": "accelerate_00044_chunk_001",
      "score": 0.85,
      "text": "[BOOK: Accelerate | ...] Case Study: ING Bank...",
      "metadata": {
        "chapter_title": "Chapter 5: Architecture",
        "page_num": 44,
        "extended_fields": {
          "content_type": "case_study",
          "domain": "devops",
          "complexity": "intermediate",
          "topics": ["organizational structure", "autonomous teams"],
          "entities": {
            "companies": ["ING Bank"]
          },
          "business": {
            "has_metrics": true,
            "metrics": ["deployment frequency"],
            "has_case_study": true,
            "case_study_company": "ING Bank"
          }
        }
      }
    }
  ]
}
```

---

### Example 3: Programming book search
```bash
python rag/search.py -i python_async \
  -q "async await example" \
  --has-code \
  --topic "async programming"
```

**Result:**
```json
{
  "query": "async await example",
  "filters_applied": true,
  "filters": {
    "has_code": true,
    "topics": ["async programming"]
  },
  "results": [
    {
      "chunk_id": "python_book_00123_chunk_001",
      "score": 0.92,
      "text": "[BOOK: Python Async Programming] # Python Async Programming\n\nimport asyncio...",
      "metadata": {
        "chapter_title": "Chapter 8: Asynchronous Programming",
        "page_num": 123,
        "has_code": true,
        "extended_fields": {
          "content_type": "tutorial",
          "domain": "programming",
          "topics": ["async programming", "concurrency"],
          "technical": {
            "has_code": true,
            "programming_languages": ["Python"]
          },
          "tools_mentioned": ["asyncio", "aiohttp"]
        }
      }
    }
  ]
}
```

---

### Example 4: Hybrid search with context expansion
```bash
python rag/search.py -i accelerate \
  -q "ING Bank deployment" \
  --hybrid \
  --expand-context 1
```

**Result:**
```json
{
  "query": "ING Bank deployment",
  "search_method": "hybrid",
  "results": [
    {
      "chunk_id": "accelerate_00044_chunk_001",
      "score": 0.91,
      "text": "...",
      "expanded_context": {
        "before": [
          {
            "chunk_id": "accelerate_00043_chunk_002",
            "text": "...previous context..."
          }
        ],
        "after": [
          {
            "chunk_id": "accelerate_00045_chunk_001",
            "text": "...next context..."
          }
        ]
      }
    }
  ]
}
```

---

## 📊 Complete Data Flow Summary

```
PDF Page 42 (raw scan/digital)
    ↓
[STRUCTURAL] 
    → Extract text (pdfminer/pdfplumber/pypdf2/OCR)
    → Extract tables (structured)
    → Track extraction_method, ocr_confidence
    ↓
[STRUCTURE DETECT]
    → Detect chapters/sections
    → Build TOC
    → Add chapter_title, section_title
    ↓
[SUMMARIZE]
    → L1 summary (300 chars)
    → Optional L2 (900 chars)
    ↓
[EXTENDED] ⭐ KEY STAGE
    → Deduplicate (exact + fuzzy)
    → LM extraction (qwen2.5:7b or qwen2.5-coder:7b):
        • content_type, domain, complexity
        • entities (companies, technologies, etc.)
        • technical (has_code, languages)
        • actionable (best practices)
        • business (metrics, case studies)
        • content_analysis (topics, concepts)
        • tools_mentioned
    ↓
[FINALIZE]
    → Validate schema
    → Check policies
    → Recalculate manifest
    ↓
[CHUNK]
    → Split into 512-char chunks
    → Add structure context [BOOK | CHAPTER | SECTION]
    → Preserve extended_fields in metadata
    → Link prev/next chunks
    ↓
[EMBED]
    → Generate 1024-dim vectors (bge-m3)
    → Build FAISS index
    → Store metadata (with extended_fields)
    ↓
[SEARCH]
    → Semantic search (FAISS)
    → Optional: Hybrid (+ BM25)
    → Optional: Reranking (cross-encoder)
    → Filter by extended_fields
    → Return ranked results with full metadata
```

---

## 🎯 Key Advantages of MVP v2.0

### 1. **Rich Metadata** (extended_fields)
- Content classification (type, domain, complexity)
- Entity extraction (companies, technologies, tools)
- Technical analysis (code, languages, diagrams)
- Business insights (metrics, case studies)
- Topic analysis (concepts, problem/solution)

### 2. **Robust Extraction**
- Multi-extractor fallback chain
- OCR support with confidence tracking
- Structured table extraction
- Retry logic with exponential backoff

### 3. **Advanced Search**
- 15+ filter types via extended_fields
- Hybrid search (semantic + keyword)
- Context expansion (surrounding chunks)
- Query expansion (synonyms)
- Optional reranking

### 4. **Traceability**
- From search result → chunk → segment → PDF page
- Extraction method tracked
- Full audit trail

### 5. **Flexibility**
- Different configs for speed vs quality
- Specialized model for code (qwen2.5-coder)
- Configurable chunking strategies
- Optional features (OCR, LM, reranking)

---

## 🔧 Configuration Impact on Output

### Fast Config (`mvp_fast.yaml`)
```jsonl
// No OCR, no LM extraction
{"segment_id":"00042",
 "extraction_method":"pdfminer",
 "ocr_used":false,
 "extended_fields":null}  // ← No extended fields
```

### Default Config (`mvp.yaml`)
```jsonl
// With LM extraction (qwen2.5:7b)
{"segment_id":"00042",
 "extraction_method":"pdfminer",
 "ocr_used":false,
 "extended_fields":{
   "content_type":"research",
   "topics":["architecture"]
 }}
```

### Quality Config (`mvp_quality.yaml`)
```jsonl
// With better LM (qwen2.5:14b) + high-quality OCR
{"segment_id":"00042",
 "extraction_method":"pdfminer",
 "ocr_used":false,
 "extended_fields":{
   "content_type":"research",
   "domain":"devops",
   "complexity":"intermediate",
   "topics":["architecture","deployment","scalability"],
   "entities":{"technologies":["microservices","Docker"]},
   "business":{"metrics":["deployment frequency"]}
 }}
```

### Code Config (`mvp_code.yaml`)
```jsonl
// With qwen2.5-coder:7b for better code understanding
{"segment_id":"00123",
 "extended_fields":{
   "content_type":"tutorial",
   "domain":"programming",
   "technical":{
     "has_code":true,
     "programming_languages":["Python"]
   },
   "tools_mentioned":["asyncio","aiohttp"]
 }}
```

---

**Version:** 2.0.0  
**Last Updated:** 2025-01-28  
**Models Used:** bge-m3 (embeddings), qwen2.5:7b/14b or qwen2.5-coder:7b (extended fields)