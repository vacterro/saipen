"""Canonical INIT materialization (T-1553).

`saipen/phases/init.md` is prose an agent executes: copy the shipped templates,
fill the placeholders from the RUNNING install, write `IDENTITY.md`, enter
PLAN. The bytes that prose produces are canonical, so they are produced here by
exactly one implementation. A caller that hand-writes STATE/BOARD/LOG strings --
as a fixture used to -- proves only that the file it invented parses; this
proves the real INIT effect, which is what the mid-session response contract
must survive.

Authorities, all read from the running install and never from a caller:

* the shapes -- `extensions/templates/{STATE,BOARD,LOG}.md`;
* `saipen_version` / `schema_version` / `style_contract` -- the same
  `state.running_*` accessors validation uses, so a fresh project cannot be
  born against a version this install does not speak;
* `project_lineage` -- `paths.new_project_lineage`.

The seat is the one value the caller must supply, because a seat is a fact
about who is running, and INIT is run by a real seat (`agent:` is never
`none`).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .paths import identity_file_content, new_project_lineage
from .state import (
    running_home,
    running_protocol_major,
    running_schema_version,
    running_style_token,
)

TEMPLATE_NAMES = ("STATE.md", "BOARD.md", "LOG.md")

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class InitRefused(RuntimeError):
    """INIT was asked to run where the protocol says it must not."""


def _template(name: str) -> str:
    path = running_home() / "extensions" / "templates" / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InitRefused(f"canonical template unavailable: {path}: {exc}") from None


def _fill_state(text: str, values: dict[str, str]) -> str:
    """Replace declared placeholders inside the template frontmatter only.

    Line-wise and key-by-key: the template owns field order and every key it
    does not name is left exactly as shipped.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        raise InitRefused("STATE.md template has no frontmatter fence")
    body = match.group(1)
    seen: set[str] = set()
    lines = []
    for line in body.split("\n"):
        key, sep, _old = line.partition(":")
        if sep and key in values:
            lines.append(f"{key}: {values[key]}")
            seen.add(key)
        else:
            lines.append(line)
    missing = set(values) - seen
    if missing:
        raise InitRefused(
            "STATE.md template is missing placeholder(s): " + ", ".join(sorted(missing))
        )
    return text[: match.start(1)] + "\n".join(lines) + text[match.end(1) :]


def bootstrap_project(
    root: Path | str,
    *,
    agent: str,
    mode: str = "full",
    execution_intent: str = "normal",
    now: dt.datetime | None = None,
) -> dict[str, str]:
    """Materialize the canonical INIT project at `root`. Returns what it wrote.

    Refuses a root that already carries `.saipen/`: INIT runs only when the
    bound project root genuinely lacks it, and an overwrite here would destroy
    live Work rather than bootstrap a project.
    """
    root = Path(root).resolve()
    seat = str(agent or "").strip()
    if not seat:
        raise InitRefused("INIT needs a real seat; `agent:` is never none")
    target = root / ".saipen"
    if target.exists():
        raise InitRefused(f"{target} already exists; INIT does not overwrite a project")

    version = running_protocol_major()
    schema = running_schema_version()
    token = running_style_token()
    if version is None or schema is None or token is None:
        raise InitRefused("running install does not expose its own version/schema/style authority")

    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = _fill_state(
        _template("STATE.md"),
        {
            "agent": seat,
            "saipen_version": str(version),
            "schema_version": str(schema),
            "style_contract": token,
            "saipen_home": f'"{running_home().as_posix()}"',
            "mode": mode,
            "execution_intent": execution_intent,
            "updated": stamp,
        },
    )

    target.mkdir(parents=True)
    (target / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (target / "STATE.md").write_text(state, encoding="utf-8")
    for name in ("BOARD.md", "LOG.md"):
        (target / name).write_text(_template(name), encoding="utf-8")
    return {
        "project_root": str(root),
        "identity": str(target / "IDENTITY.md"),
        "state": str(target / "STATE.md"),
        "board": str(target / "BOARD.md"),
        "log": str(target / "LOG.md"),
        "saipen_home": str(running_home()),
    }
