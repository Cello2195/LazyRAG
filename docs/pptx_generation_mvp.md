# LazyRAG PPTX Generation MVP

This patch adds the first PPTX artifact toolchain for Agentic LazyRAG. It follows a schema-driven workflow inspired by public PPTX generation skills and projects, but keeps the first renderer in Python to match the existing backend stack.

## Added workflow

```text
RAG evidence / user content
  -> deck_schema
  -> pptx_create_from_schema
  -> pptx_parse
  -> pptx_qa
  -> artifact_save
  -> optional pptx_render_thumbnails
```

## New tools

- `pptx_create_from_schema(deck_schema, filename)`: renders an editable `.pptx` from a normalized schema using `python-pptx`.
- `pptx_parse(file_path)`: extracts slide count, text, table/image counts, and lightweight shape metadata.
- `pptx_qa(file_path, deck_schema)`: checks empty slides, missing expected text, placeholder residue, excessive text, and simple bounds issues.
- `pptx_render_thumbnails(file_path, dpi)`: converts PPTX to PDF via `LAZYRAG_OFFICE_CONVERT_URL` or local LibreOffice, then renders PNG thumbnails with PyMuPDF.
- `artifact_save(file_path, kind, filename)`: copies generated files into LazyRAG's upload root and returns signed `/static-files/...` URLs.

## Supported slide types

The first Python renderer supports:

- `cover`
- `toc`
- `section_divider`
- `content_bullets`
- `two_column`
- `comparison`
- `table`
- `summary`

The schema normalizer is permissive and accepts common aliases such as `content`, `bullets`, `items`, `points`, `left_bullets`, `right_bullets`, `citations`, and `sources`.

## Important environment variables

- `LAZYRAG_UPLOAD_ROOT` or `LAZYRAG_SHARED_UPLOAD_DIR`: root for generated artifacts, default `/var/lib/lazyrag/uploads`.
- `LAZYRAG_FILE_URL_SIGN_SECRET`: secret used to sign static file URLs, default matches the backend default.
- `LAZYRAG_FILE_URL_EXPIRE_SECONDS`: signed URL expiry seconds, default `3600`.
- `LAZYRAG_OFFICE_CONVERT_URL`: optional Office-to-PDF service URL, e.g. `http://office-convert-service:8080/v1/office/to-pdf`.

## Next steps

1. Add richer templates and chart rendering.
2. Add OOXML/template editing for existing PPTX files.
3. Add optional Node/PptxGenJS or HTML2PPTX renderer behind the same `deck_schema` interface.
4. Add stronger visual QA from thumbnails, including low-contrast and overlap detection.
5. Extend frontend chat responses with a first-class `artifacts` field instead of relying only on text links.
