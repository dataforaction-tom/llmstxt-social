"""Document text extractors for the strategy / idea chat creator.

Accepts PDF, DOCX, and plain-text uploads. Other formats raise
:class:`UnsupportedFormatError` so the route can return a 415 cleanly.

Hard 10 MB cap on the input — large uploads tie up the worker and there's no
realistic charity strategy that comes close. Tune via :data:`MAX_UPLOAD_BYTES`
if a real one shows up.
"""

from __future__ import annotations

import io
from pathlib import PurePosixPath

from pypdf import PdfReader


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


class ExtractError(RuntimeError):
    """Raised when the file's content can't be turned into text."""


class UnsupportedFormatError(ExtractError):
    """Raised when the file extension is something we don't handle."""


def extract_text(filename: str, content: bytes) -> str:
    """Return the text of ``content`` based on the file's extension.

    Raises :class:`ExtractError` (or its subclasses) for empty input,
    oversize uploads, unsupported formats, and underlying-library failures.
    """
    if not content:
        raise ExtractError("upload is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ExtractError(
            f"upload is too large ({len(content)} bytes, max {MAX_UPLOAD_BYTES})"
        )

    extension = PurePosixPath(filename).suffix.lower()
    if extension == ".pdf":
        return _extract_pdf(content)
    if extension == ".docx":
        return _extract_docx(content)
    if extension in {".txt", ".md", ""}:
        return _extract_plain(content)
    raise UnsupportedFormatError(
        f"unsupported upload format: {extension!r}; expected .pdf, .docx, .txt, or .md"
    )


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise ExtractError(f"could not parse PDF: {exc}") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def _extract_docx(content: bytes) -> str:
    # Late import: python-docx is a runtime dep but loading it on every import
    # of this module would slow the Celery boot. It's only needed in the
    # upload path.
    from docx import Document  # type: ignore[import-not-found]

    try:
        document = Document(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise ExtractError(f"could not parse DOCX: {exc}") from exc

    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_plain(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        # Older sector docs are often Latin-1; fall back rather than fail.
        return content.decode("latin-1", errors="replace")


__all__ = [
    "MAX_UPLOAD_BYTES",
    "ExtractError",
    "UnsupportedFormatError",
    "extract_text",
]
