"""Markdown ↔ Open Org JSON converter.

Markdown with YAML frontmatter is the source of truth for organisations
editing their profiles, strategies, and ideas. The converter is bidirectional
so the editor can load existing JSON, the user edits markdown, and we
re-derive JSON on save.

Round-trip identity is the load-bearing invariant — see
``tests/open_org/test_converter_round_trip.py``.
"""

from __future__ import annotations

import re
from typing import Any

import frontmatter
import yaml


class ConverterError(Exception):
    """Raised when markdown cannot be converted to a valid Open Org payload.

    The ``errors`` attribute carries the structured error list (same shape as
    :class:`llmstxt_core.open_org.validator.ValidationError`).
    """

    def __init__(self, errors: list[dict[str, str]] | str) -> None:
        if isinstance(errors, str):
            errors = [{"path": "", "message": errors}]
        self.errors = errors
        summary = "; ".join(f"{e['path'] or '<root>'}: {e['message']}" for e in errors[:5])
        super().__init__(f"{len(errors)} converter error(s): {summary}")


# Match HTML comments lazily so adjacent comments don't get merged.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def parse_frontmatter(md: str) -> tuple[dict, str]:
    """Split markdown into (frontmatter_dict, body_str).

    Returns ``({}, md)`` when no frontmatter block is present. Raises
    :class:`ConverterError` if the frontmatter YAML is malformed.
    """
    try:
        post = frontmatter.loads(md)
    except yaml.YAMLError as e:
        raise ConverterError(f"invalid YAML frontmatter: {e}") from e
    return dict(post.metadata), post.content


def strip_comments(body: str) -> str:
    """Remove HTML comments (``<!-- ... -->``) from a markdown body, preserving
    any comment-like text inside fenced code blocks (``` ... ```)."""
    placeholders: list[str] = []

    def _stash(match: re.Match) -> str:
        placeholders.append(match.group(0))
        return f"\x00CODEBLOCK{len(placeholders) - 1}\x00"

    stashed = _FENCED_CODE_RE.sub(_stash, body)
    stripped = _HTML_COMMENT_RE.sub("", stashed)

    def _restore(match: re.Match) -> str:
        idx = int(match.group(1))
        return placeholders[idx]

    return re.sub(r"\x00CODEBLOCK(\d+)\x00", _restore, stripped)


def _set_path(target: dict, path: tuple[str, ...], value: Any) -> None:
    """Assign ``value`` at ``path`` in ``target``, creating dicts as needed."""
    cursor = target
    for key in path[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[path[-1]] = value


# --- section parsers / renderers ---------------------------------------------

_BOLD_ITEM_SPLIT_RE = re.compile(r"(?m)^- \*\*")
_PLAIN_ITEM_SPLIT_RE = re.compile(r"(?m)^- ")
_SOURCE_TAG_RE = re.compile(r"\*Source:\s*([^\s*]+)\s*\*")
_WHITESPACE_RE = re.compile(r"\s+")


def parse_text(body: str) -> str:
    """Strip leading/trailing whitespace; preserve internal structure."""
    return body.strip()


def render_text(text: str) -> str:
    """Inverse of :func:`parse_text` — passthrough."""
    return text


def parse_bullet_list(body: str) -> list[str]:
    """Parse ``- item`` lines into a list of strings, ignoring blank lines."""
    out: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(stripped[2:].strip())
    return out


def render_bullet_list(items: list[str]) -> str:
    """Inverse of :func:`parse_bullet_list`."""
    return "\n".join(f"- {item}" for item in items)


def parse_bold_items(body: str, *, body_field: str = "rationale") -> list[dict[str, str]]:
    """Parse ``- **title.** description`` items into ``[{title, body_field}, ...]``.

    The bold title may span multiple lines; whitespace in the title is collapsed
    to single spaces. The body field name defaults to ``rationale`` (used by
    ``not_doing``); pass ``body_field="narrative"`` for tensions.

    Items without a bold prefix (``- plain text``) are also accepted — the
    whole line becomes the ``title`` and the body field is left empty. This
    keeps the parser forgiving for human-edited markdown.
    """
    # Split on any bullet item start, then classify each chunk as bold or plain.
    chunks = _PLAIN_ITEM_SPLIT_RE.split(body)
    out: list[dict[str, str]] = []
    # chunks[0] is anything before the first item; ignore.
    for chunk in chunks[1:]:
        text = chunk.strip()
        if not text:
            continue
        if text.startswith("**"):
            end = text.find("**", 2)
            if end == -1:
                # Malformed — no closing **. Treat the whole chunk as the title.
                title = _WHITESPACE_RE.sub(" ", text)
                rest = ""
            else:
                title = _WHITESPACE_RE.sub(" ", text[2:end].strip())
                rest = _WHITESPACE_RE.sub(" ", text[end + 2:].strip())
        else:
            # Plain item — no bold prefix. Whole text is the title.
            title = _WHITESPACE_RE.sub(" ", text)
            rest = ""
        out.append({"title": title, body_field: rest})
    return out


def render_bold_items(items: list[dict[str, str]], *, body_field: str = "rationale") -> str:
    """Inverse of :func:`parse_bold_items`."""
    lines = []
    for item in items:
        title = item.get("title", "")
        body = item.get(body_field, "")
        lines.append(f"- **{title}** {body}".rstrip())
    return "\n".join(lines)


def parse_bold_items_with_source(body: str) -> list[dict[str, str]]:
    """Parse learning items into ``[{lesson, source?}, ...]``.

    Accepts both bold-prefixed (``- **title.** lesson``) and plain (``- lesson``)
    input — the bold prefix, if present, is treated as a headline and dropped
    in favour of the lesson body. This is the forgiving parse direction; the
    canonical render uses plain bullets.

    A trailing ``*Source: x*`` tag, if present, is extracted into ``source``.
    """
    chunks = _PLAIN_ITEM_SPLIT_RE.split(body)
    out: list[dict[str, str]] = []
    for chunk in chunks[1:]:
        text = chunk.strip()
        # If item starts with a bold prefix, drop it.
        if text.startswith("**"):
            close = text.find("**", 2)
            if close != -1:
                text = text[close + 2:].strip()
        # Extract source tag if present.
        item: dict[str, str] = {}
        match = _SOURCE_TAG_RE.search(text)
        if match:
            item["source"] = match.group(1)
            text = _SOURCE_TAG_RE.sub("", text).strip()
        item["lesson"] = _WHITESPACE_RE.sub(" ", text).strip()
        # Conventional key order: lesson first, source second
        ordered = {"lesson": item["lesson"]}
        if "source" in item:
            ordered["source"] = item["source"]
        out.append(ordered)
    return out


def render_bold_items_with_source(items: list[dict[str, str]]) -> str:
    """Inverse of :func:`parse_bold_items_with_source` (plain bullet form)."""
    lines = []
    for item in items:
        lesson = item.get("lesson", "")
        if "source" in item:
            lines.append(f"- {lesson}\n  *Source: {item['source']}*")
        else:
            lines.append(f"- {lesson}")
    return "\n".join(lines)


# --- per-kind section maps ---------------------------------------------------
# Each entry: (heading, json_path, parser, renderer)
#
# Anything not listed here stays in the YAML frontmatter. Round-trip identity
# depends on parsers and renderers being inverse — see
# tests/open_org/test_converter_round_trip.py.

# Strategy priorities are rendered as `## Priority N: Title` sections whose
# body is the narrative. They don't have a fixed heading — we use a regex to
# detect them during parse and a dedicated renderer for the markdown side.
_PRIORITY_HEADING_RE = re.compile(r"^Priority\s+\d+\s*:\s*(.+)$", re.IGNORECASE)


def parse_priorities(body_sections: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Extract priority objects from body sections matching ``## Priority N: Title``.

    The section body becomes the ``narrative`` field. Heading order is preserved
    so ``Priority 1`` maps to ``priorities[0]``, etc.
    """
    out: list[dict[str, str]] = []
    for heading, content in body_sections:
        match = _PRIORITY_HEADING_RE.match(heading)
        if not match:
            continue
        title = match.group(1).strip()
        item: dict[str, str] = {"title": title}
        narrative = content.strip()
        if narrative:
            item["narrative"] = narrative
        out.append(item)
    return out


def render_priorities(items: list[dict[str, str]]) -> str:
    """Render priorities as ``## Priority N: Title`` sections with narrative body."""
    chunks: list[str] = []
    for i, item in enumerate(items, start=1):
        title = item.get("title", "")
        narrative = item.get("narrative", "")
        if narrative:
            chunks.append(f"## Priority {i}: {title}\n\n{narrative}")
        else:
            chunks.append(f"## Priority {i}: {title}")
    return "\n\n".join(chunks)


def _bold_items_rationale(body: str):
    return parse_bold_items(body, body_field="rationale")


def _render_bold_items_rationale(value):
    return render_bold_items(value, body_field="rationale")


def _bold_items_narrative(body: str):
    return parse_bold_items(body, body_field="narrative")


def _render_bold_items_narrative(value):
    return render_bold_items(value, body_field="narrative")


_BODY_SECTIONS: dict[str, list[tuple[str, tuple[str, ...], Any, Any]]] = {
    "profile": [
        ("Mission", ("mission", "summary"), parse_text, render_text),
        ("Theory of change", ("mission", "theory_of_change"), parse_text, render_text),
        ("Culture", ("culture", "narrative"), parse_text, render_text),
        ("Values", ("values",), parse_bullet_list, render_bullet_list),
    ],
    "strategy": [
        ("Summary", ("summary",), parse_text, render_text),
        ("Not doing", ("not_doing",), _bold_items_rationale, _render_bold_items_rationale),
        ("Tensions", ("tensions",), _bold_items_narrative, _render_bold_items_narrative),
        (
            "Learning",
            ("learning", "what_changed"),
            parse_bold_items_with_source,
            render_bold_items_with_source,
        ),
    ],
    "idea": [
        ("Summary", ("summary",), parse_text, render_text),
        ("The detail", ("detail",), parse_text, render_text),
    ],
}


_HEADING_SPLIT_RE = re.compile(r"(?m)^## (.+?)$")


def _pop_path(d: dict, path: tuple[str, ...]) -> Any:
    """Pop value at ``path`` from ``d``. Cleans up emptied intermediate dicts."""
    if not path:
        return None
    cursor = d
    parents: list[tuple[dict, str]] = []
    for key in path[:-1]:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        parents.append((cursor, key))
        cursor = cursor[key]
    if not isinstance(cursor, dict):
        return None
    value = cursor.pop(path[-1], None)
    # Walk back up, removing keys whose dict value is now empty.
    for parent, key in reversed(parents):
        if isinstance(parent[key], dict) and not parent[key]:
            parent.pop(key)
        else:
            break
    return value


def _split_body_sections(body: str) -> list[tuple[str, str]]:
    """Split a markdown body on ``## `` headings into ``[(heading, content), ...]``.

    Fenced code blocks (``` ... ```) are masked before splitting so that
    ``##`` headings *inside* code blocks are not mistaken for section headings.
    """
    # Mask fenced code blocks with same-length blank lines so column offsets
    # are preserved and headings inside code blocks are invisible to the split.
    masked = _FENCED_CODE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), body)
    parts = _HEADING_SPLIT_RE.split(masked)
    # parts[0] is anything before the first heading.
    # After that, parts alternates [heading, content, heading, content, ...].
    # But the content slices refer to the masked body — we need the original
    # body's content. So re-split using indices from the masked body.
    # Strategy: find heading positions in masked body, then slice original body.
    sections: list[tuple[str, str]] = []
    for match in _HEADING_SPLIT_RE.finditer(masked):
        heading = match.group(1).strip()
        start = match.end()
        # Find the next heading start in the masked body, or end of body.
        next_match = _HEADING_SPLIT_RE.search(masked, pos=start)
        end = next_match.start() if next_match else len(masked)
        content = body[start:end].strip()
        sections.append((heading, content))
    return sections


def _import_validator():
    # Late import to avoid a hard import cycle if validator wants converter helpers later.
    from llmstxt_core.open_org.validator import (
        ValidationError,
        validate_for_kind,
    )
    return ValidationError, validate_for_kind


def _coerce_scalar_types(payload: Any, *, schema: dict, kind: str) -> dict:
    """Coerce numeric/bool scalars to strings where the schema requires ``type: string``.

    YAML parsers (pyyaml, js-yaml) read an unquoted ``1234567`` as an integer.
    If the schema field is ``type: string``, validation fails. Rather than
    forcing every user to quote their values, we coerce int/float/bool values
    to strings in-place for paths the schema declares as strings.

    This is a pragmatic, schema-driven coercion — it only touches leaf scalars
    whose schema type is ``string`` and whose current Python type is not str.
    """
    if not isinstance(schema, dict):
        return payload

    def _walk(node: Any, node_schema: dict) -> Any:
        if not isinstance(node_schema, dict):
            return node
        node_type = node_schema.get("type")
        if node_type == "string" and not isinstance(node, str) and node is not None:
            # Coerce int/float/bool to string. Bool → "true"/"false" to match
            # YAML 1.1 conventions (not Python's "True"/"False").
            if isinstance(node, bool):
                return "true" if node else "false"
            return str(node)
        if node_type == "object" and isinstance(node, dict):
            props = node_schema.get("properties", {})
            for key, val in node.items():
                if key in props:
                    node[key] = _walk(val, props[key])
            return node
        if node_type == "array" and isinstance(node, list):
            item_schema = node_schema.get("items", {})
            if isinstance(item_schema, dict):
                return [_walk(item, item_schema) for item in node]
            return node
        # Handle anyOf (used by registration in the profile schema)
        if "anyOf" in node_schema and isinstance(node, dict):
            props = node_schema.get("properties", {})
            for key, val in node.items():
                if key in props:
                    node[key] = _walk(val, props[key])
            return node
        return node

    return _walk(payload, schema)


def markdown_to_json(md: str, *, kind: str) -> dict:
    """Convert a markdown document with YAML frontmatter into a validated payload.

    Raises :class:`ConverterError` for malformed YAML, an unknown kind, or
    schema-validation failure (with the underlying errors attached).
    """
    if kind not in _BODY_SECTIONS:
        raise ValueError(f"unknown kind: {kind!r} (expected one of {list(_BODY_SECTIONS)})")

    frontmatter_dict, body = parse_frontmatter(md)
    body = strip_comments(body)

    payload = dict(frontmatter_dict)
    body_sections = _split_body_sections(body)
    sections_by_heading = dict(body_sections)

    for heading, path, parser, _renderer in _BODY_SECTIONS[kind]:
        if heading in sections_by_heading:
            value = parser(sections_by_heading[heading])
            _set_path(payload, path, value)

    # Strategy priorities are multi-section (## Priority N: Title) and need
    # special handling outside the fixed-heading map.
    if kind == "strategy":
        priorities = parse_priorities(body_sections)
        if priorities:
            payload["priorities"] = priorities

    ValidationError, validate_for_kind = _import_validator()
    # Coerce numeric/bool scalars to strings where the schema requires strings.
    # This handles unquoted YAML values like `charity_commission_ew: 1234567`
    # that pyyaml parses as integers.
    from llmstxt_core.open_org.validator import load_schema
    payload = _coerce_scalar_types(payload, schema=load_schema(kind), kind=kind)
    try:
        validate_for_kind(payload, kind=kind)
    except ValidationError as e:
        raise ConverterError(e.errors) from e

    return payload


# Scalars another YAML 1.1 parser (notably js-yaml, used by the guided editor)
# would coerce to a number/bool/null. pyyaml round-trips these safely unquoted,
# but js-yaml reads e.g. `01325387700` as the integer 1325387700 (leading zero
# dropped), which then fails the schema's `string` type on save. Quoting them
# keeps every parser treating the value as the string it is.
_AMBIGUOUS_SCALAR_RE = re.compile(
    r"""^(
        [-+]?\.?[0-9][0-9_]*(\.[0-9_]*)?([eE][-+]?[0-9]+)?   # int / float (incl leading zeros)
        | 0x[0-9a-fA-F_]+ | 0o?[0-7_]+ | 0b[01_]+            # hex / octal / binary
        | [-+]?\.(inf|Inf|INF) | \.(nan|NaN|NAN)             # inf / nan
        | true|True|TRUE | false|False|FALSE                 # bools
        | yes|Yes|YES | no|No|NO | on|On|ON | off|Off|OFF
        | null|Null|NULL | ~                                 # null
    )$""",
    re.VERBOSE,
)


class _QuotingDumper(yaml.SafeDumper):
    """SafeDumper that single-quotes ambiguous scalars (see above)."""


def _represent_quoting_str(dumper: yaml.Dumper, data: str):
    style = "'" if _AMBIGUOUS_SCALAR_RE.match(data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_QuotingDumper.add_representer(str, _represent_quoting_str)


def json_to_markdown(payload: dict, *, kind: str) -> str:
    """Convert an Open Org payload into markdown with YAML frontmatter.

    Inverse of :func:`markdown_to_json`. The YAML frontmatter preserves dict
    insertion order; body sections are rendered in the order declared in the
    per-kind section map.
    """
    if kind not in _BODY_SECTIONS:
        raise ValueError(f"unknown kind: {kind!r} (expected one of {list(_BODY_SECTIONS)})")

    # Deep copy via JSON round-trip so we can safely pop without mutating caller's dict.
    import json as _json
    working = _json.loads(_json.dumps(payload))

    body_chunks: list[str] = []
    for heading, path, _parser, renderer in _BODY_SECTIONS[kind]:
        value = _pop_path(working, path)
        if value is None or value == "" or value == [] or value == {}:
            continue
        body_chunks.append(f"## {heading}\n\n{renderer(value)}")

    # Strategy priorities are rendered as ## Priority N: Title sections.
    if kind == "strategy":
        priorities = _pop_path(working, ("priorities",))
        if priorities:
            body_chunks.append(render_priorities(priorities))

    yaml_str = yaml.dump(
        working,
        Dumper=_QuotingDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    body_str = "\n\n".join(body_chunks)
    if body_str:
        return f"---\n{yaml_str}---\n\n{body_str}\n"
    return f"---\n{yaml_str}---\n"
