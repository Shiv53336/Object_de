"""Turn Claude Code's stream-json output into readable workflow logs, a result report and annotations.

  claude -p ... --output-format stream-json --verbose | python3 agentlog.py progress
  python3 agentlog.py summary transcript.jsonl > result.md
  some-command | python3 agentlog.py notice "Title" [--quiet]

Annotations can be read through the GitHub REST API, so dispatch.sh (and Claude in chat) can fetch a
run's result without downloading logs. Runs on the system python3 too, so it uses only the stdlib.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Iterator

NOTICE_LIMIT = 3900


def events(lines: Iterable[str]) -> Iterator[dict]:
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def _blocks(event: dict) -> list[dict]:
    content = (event.get("message") or {}).get("content")
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _one_line(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe_tool(block: dict) -> str:
    name = block.get("name", "tool")
    args = block.get("input") or {}
    keys = ("command", "file_path", "pattern", "description")
    detail = next((str(args[k]) for k in keys if args.get(k)), "")
    return f"[{name}] {_one_line(detail, 200)}".rstrip()


def progress_lines(evts: Iterable[dict]) -> Iterator[str]:
    for e in evts:
        kind = e.get("type")
        if kind == "system" and e.get("subtype") == "init":
            yield f"session started · model {e.get('model', '?')}"
        elif kind == "assistant":
            for b in _blocks(e):
                if b.get("type") == "text" and b.get("text", "").strip():
                    yield "» " + _one_line(b["text"], 400)
                elif b.get("type") == "tool_use":
                    yield describe_tool(b)
        elif kind == "user":
            for b in _blocks(e):
                if b.get("type") == "tool_result" and b.get("is_error"):
                    content = b.get("content")
                    if isinstance(content, list):
                        content = " ".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
                    yield "  ! " + _one_line(content or "error", 300)
        elif kind == "result":
            yield f"finished · {e.get('subtype', '?')} · turns {e.get('num_turns', '?')}"


def summary(evts: Iterable[dict]) -> str:
    model, last_text, result = "?", "", None
    for e in evts:
        if e.get("type") == "system" and e.get("subtype") == "init":
            model = e.get("model", model)
        elif e.get("type") == "assistant":
            texts = [b.get("text", "") for b in _blocks(e) if b.get("type") == "text"]
            if any(t.strip() for t in texts):
                last_text = "\n".join(texts).strip()
        elif e.get("type") == "result":
            result = e
    if result is None:
        body = last_text or "(no output)"
        return f"{body}\n\n---\nClaude Code stopped without a final result · model {model}\n"
    body = (result.get("result") or last_text or "(no final message)").strip()
    cost = result.get("total_cost_usd")
    seconds = int((result.get("duration_ms") or 0) / 1000)
    parts = [
        f"model {model}",
        f"status {result.get('subtype', '?')}",
        f"turns {result.get('num_turns', '?')}",
        f"cost ~${cost:.2f}" if isinstance(cost, (int, float)) else "cost ?",
        f"time {seconds // 60}m {seconds % 60:02d}s",
    ]
    return f"{body}\n\n---\n{' · '.join(parts)}\n"


def escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def notice(title: str, text: str) -> str:
    text = text.strip() or "(empty)"
    if len(text) > NOTICE_LIMIT:
        text = text[:NOTICE_LIMIT] + "\n… (truncated; full text in the run log)"
    safe_title = title.replace("%", "%25").replace(":", "%3A").replace(",", "%2C")
    return f"::notice title={safe_title}::{escape(text)}"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "progress":
        for line in progress_lines(events(sys.stdin)):
            print(line, flush=True)
    elif cmd == "summary":
        with open(rest[0], encoding="utf-8") as fh:
            sys.stdout.write(summary(events(fh)))
    elif cmd == "notice":
        text = sys.stdin.read()
        if "--quiet" not in rest:
            sys.stdout.write(text)
        print(notice(rest[0] if rest else "Agent", text))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
