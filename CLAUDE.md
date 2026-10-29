# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local RAG knowledge base that retrieves Korean **law articles** (형법, 국민건강증진법, 개인정보 보호법) and **police investigation procedures** for unmanned-store CCTV incident reports. It sits between an upstream VLM (which emits one JSON per video segment) and a downstream report-generation LLM. Fully local: ChromaDB + HuggingFace embeddings (`BAAI/bge-m3`), no API keys. Code comments, docs, and data are in Korean.

## Commands

Windows/PowerShell, run from the repo root (scripts import `config` and `src.*` relative to it):

```powershell
.venv\Scripts\activate
pip install -r requirements.txt     # versions are pinned on purpose (same results across the team)

python pdf_to_json.py               # law PDFs -> data/laws/laws_draft.json (only when adding/amending laws)
python build_kb.py --dry-run        # load + chunk only, prints every chunk label; no model download
python build_kb.py                  # rebuild chroma_db/ (drops and recreates the collection)
python test_retrieval.py            # Hit@K / Recall@K over tests/retrieval_cases.json
python test_retrieval.py -k 3       # different K
python test_retrieval.py -q "무인 매장에서 물건을 훔치면?"   # single ad-hoc query
python test_segments.py             # golden tests for retrieve_for_segment (exit 1 on failure)
python run_segment.py examples/sample_input.json                  # RAG output JSON
python run_segment.py examples/sample_input.json --format context # [참고 법령] block only
python run_segment.py examples/sample_input.json --format prompt  # full report prompt
```

There is no pytest/linter. Both test scripts need a built `chroma_db/`. `test_retrieval.py` scores raw vector search: `expect` strings must equal a `label()` exactly. `test_segments.py` checks per-event rules (rank-1 article, procedure order, warnings, no duplicate articles) and also runs every `EVENT_CONFIG` entry to catch `core_articles`/`procedures` names missing from the index.

**Re-run `build_kb.py` whenever `data/` or `config.py` (embedding model / chunk sizes) changes** — `chroma_db/` is gitignored and not auto-updated. `build_kb.py` stores `src/kb.build_fingerprint()` in the collection metadata and `get_vectorstore()` warns when it no longer matches. Per README, changes to embedding model or chunking should report `test_retrieval.py` results in the PR.

## Architecture

**Law data** is `data/laws/laws.json` (one object per article: `law_name`, `article_no`, `article_title`, `chapter`, `enforcement`, `text`, `amendments`, `keywords`, `source_pdf`). It is hand-reviewed and is the source of truth; the PDFs are kept only as evidence. `pdf_to_json.py` writes a *draft* (`laws_draft.json`): it strips 법제처 footers/contact lines, splits on `ARTICLE_RE`, moves `<개정…>`/`[제목개정…]` into `amendments`, and joins PDF-wrapped lines without a space — the printed `[검수]` join points must be checked by hand before copying into `laws.json`. Never overwrite `laws.json` with a raw draft.

**Indexing** (`build_kb.py`): `src/loaders.load_all()` → `src/chunking.chunk()` → Chroma.
- `load_law_json`: one Document per article with header `[법령명 제N조(제목)]`; keywords go to metadata as a comma string.
- `load_manual_md`: splits Markdown on `#`/`##`; only `##` sections become Documents (header `[title | section]`).
- Metadata `doc_type` is `"law"` or `"manual"`; retrieval filters on it.
- `chunk()` keeps each article/section whole unless it exceeds `CHUNK_MAX_LEN`; split pieces get the `[...]` header re-prepended, and every piece gets the `(관련 키워드: ...)` line.
- `chunking.label()` is the canonical identifier (`"형법 제329조"` or the full manual section name) used by test matching, dedup, and `EVENT_CONFIG` references.

**Retrieval for the pipeline** (`src/rag_service.retrieve_for_segment(segment)`) — the single entry point other team members call:
1. `src/query_builder.EVENT_CONFIG` maps `event_type` → `search` (whether to search at all), `covered` (whether the KB has relevant law), `core_articles` (always included as `match: "rule"`, fetched by metadata via `store.get`), `legal_queries` (+ the segment's `summary`), `procedures` (exact manual section names, returned in that order — procedures are not vector-searched), and an optional `note` warning.
2. `_search` runs every legal query, drops hits with distance > `config.LAW_MAX_DISTANCE`, dedups by `label()`, and fills the slots left after the core articles (`match: "search"`).
3. `_clean_text` strips the `[...]` header and the keyword line so output `text` is statute text only (keywords are team-added search aids, not law text).
4. Unknown or `search: False` event types return `status: "skipped"`; `covered: False`, `confidence: "low"`, a config `note`, or an empty law list each add a warning.

The output JSON contract is documented in `docs/rag_output_schema.md` (`SCHEMA_VERSION` in `rag_service.py`, currently 1.1). The `event_type` set must stay in sync with what the VLM side emits; renaming/removing fields means bumping the version and updating the schema doc. `get_embeddings()` and the default store are `lru_cache`d, so bge-m3 loads once per process.

**Prompt formatting** (`src/prompt_formatter.py`): turns a RAG result into `[참고 법령] / [경찰 수사 절차] / [주의]` text blocks (`format_rag_context`) or a full default report prompt (`build_report_prompt`). Output must not assert guilt — see `DISCLAIMER` and `REPORT_INSTRUCTIONS`.

## Adding data

1. Law PDF from 국가법령정보센터 → `data/laws/` (English filename), run `pdf_to_json.py`, review the draft, copy the new article into `laws.json` (a PDF with no matched articles prints `[경고] 조문을 찾지 못했습니다`).
2. Optional everyday-language keywords → that article's `keywords` list.
3. Manuals → `data/manuals/*.md`, one topic per `## ` section. Renaming a section breaks `EVENT_CONFIG[...]["procedures"]`; `test_segments.py` catches this.
4. Add cases to `tests/retrieval_cases.json` / `tests/segment_cases.json`, then `build_kb.py` → `test_retrieval.py` → `test_segments.py`.
