"""Prompts as versioned files, not strings buried in code.

Each prompt lives in ``prompts/<name>.v<N>.md`` with a small front-matter header:

    ---
    version: 2
    owner: finops-platform
    changelog: Added few-shot examples and an explicit output schema section.
    ---
    You are ...  {question} ...

Code asks for a prompt by name (latest version) or by name and version.
Changing a prompt is a reviewed change with an eval run attached, like code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"
_FILE = re.compile(r"^(?P<name>[a-z0-9_]+)\.v(?P<version>\d+)\.md$")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    metadata: dict[str, str]
    template: str

    def render(self, **values: str) -> str:
        # {name} is a placeholder; {{ and }} are literal braces (e.g. in JSON examples).
        missing = set(re.findall(r"(?<!{){(\w+)}(?!})", self.template)) - values.keys()
        if missing:
            raise KeyError(f"Prompt {self.name}.v{self.version} needs values for: {sorted(missing)}")
        return self.template.format(**values)

    @property
    def id(self) -> str:
        return f"{self.name}.v{self.version}"


def _parse(path: Path) -> Prompt:
    match = _FILE.match(path.name)
    if not match:
        raise ValueError(f"Bad prompt file name {path.name}; expected <name>.v<N>.md")
    text = path.read_text()
    metadata: dict[str, str] = {}
    if text.startswith("---\n"):
        header, text = text[4:].split("\n---\n", 1)
        for line in header.splitlines():
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
    version = int(match["version"])
    if metadata.get("version") and int(metadata["version"]) != version:
        raise ValueError(f"{path.name}: header version {metadata['version']} != file version {version}")
    return Prompt(match["name"], version, metadata, text.strip() + "\n")


def available(name: str, prompt_dir: Path = PROMPT_DIR) -> list[int]:
    return sorted(int(m["version"]) for p in prompt_dir.glob(f"{name}.v*.md") if (m := _FILE.match(p.name)))


def load_prompt(name: str, version: int | None = None, prompt_dir: Path = PROMPT_DIR) -> Prompt:
    versions = available(name, prompt_dir)
    if not versions:
        raise FileNotFoundError(f"No prompt named {name!r} in {prompt_dir}")
    chosen = versions[-1] if version is None else version
    if chosen not in versions:
        raise FileNotFoundError(f"{name}.v{chosen} not found; available: {versions}")
    return _parse(prompt_dir / f"{name}.v{chosen}.md")
