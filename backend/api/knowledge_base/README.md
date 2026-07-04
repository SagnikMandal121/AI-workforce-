# Knowledge Base

Reusable knowledge engine for organization-scoped retrieval augmented generation.

## Pipeline

1. Upload or submit source text.
2. Parse and clean content with a source-specific parser.
3. Chunk the content with the recursive chunker.
4. Generate embeddings through the configured provider abstraction.
5. Persist versions, chunks, embeddings, and retrieval logs.
6. Search with organization scoping and cached retrieval.

## Supported Sources

PDF, DOCX, TXT, Markdown, CSV, website URLs, and future-ready placeholders for Notion, Google Drive, and Confluence.
