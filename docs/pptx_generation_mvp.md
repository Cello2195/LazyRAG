# LazyRAG PPTX Generation (Phase 2)

This document describes the second-phase PPTX capability in LazyRAG. The pipeline keeps the Python stack (`python-pptx`) and extends phase 1 with stronger schema normalization, rule-based QA, and one-round auto-repair.

## End-to-end flow

```text
user requirement / RAG evidence
  -> deck_schema
  -> pptx_validate_schema
  -> pptx_create_from_schema (or pptx_generate_with_qa_loop)
  -> pptx_parse
  -> pptx_qa
  -> (optional) pptx_repair_schema + regenerate once
  -> artifact_save
  -> (optional) pptx_render_thumbnails
```

## Core tools

- `pptx_validate_schema(deck_schema)`
- `pptx_create_from_schema(deck_schema, filename)`
- `pptx_parse(file_path)`
- `pptx_qa(file_path, deck_schema, thumbnail_result)`
- `pptx_repair_schema(deck_schema, qa_result)`
- `pptx_generate_with_qa_loop(deck_schema, filename, max_repair_rounds)`
- `artifact_save(file_path, kind, filename, related_artifacts)`
- `pptx_render_thumbnails(file_path, dpi)`

## Phase-2 enhancements

1. **Schema robustness**
- Normalization and validation for loose LLM outputs.
- Auto-fallback for missing title/slides/type.
- Type inference for `table`, `two_column`, `comparison`, `content_bullets`.
- Theme fallback to `minimal`.

2. **Theme system**
- Built-in themes: `academic`, `business`, `minimal`.
- Unified color/spacing/font tokens across slide renderers.
- Chinese-friendly font fallback strategy.

3. **Rendering quality controls**
- Bullet count and length control.
- Table row/column clipping to reduce overflow.
- Notes and evidence/source propagation.
- Optional references slide.

4. **Rule-based QA and repair**
- File-level, slide-level, and shape-level checks.
- Placeholder residue, empty slide, dense content, tiny fonts, out-of-bounds checks.
- Optional thumbnail consistency checks.
- Deterministic one-round auto-repair loop.

5. **Artifact metadata**
- `size_bytes`, `sha256`, `created_at` in saved artifact response.
- Optional related artifact metadata (`pdf_path`, `thumbnail_paths`).

## Environment variables

- `LAZYRAG_UPLOAD_ROOT` / `LAZYRAG_SHARED_UPLOAD_DIR`
- `LAZYRAG_FILE_URL_SIGN_SECRET`
- `LAZYRAG_FILE_URL_EXPIRE_SECONDS`
- `LAZYRAG_OFFICE_CONVERT_URL` (optional)
- Local LibreOffice (`libreoffice` or `soffice`) is used when service URL is unavailable.

## Current constraints

- Node/PptxGenJS is not required in phase 2.
- Thumbnail rendering depends on PDF conversion + PyMuPDF availability.
- If thumbnail conversion fails, PPTX generation remains valid and returns the saved PPTX artifact.
