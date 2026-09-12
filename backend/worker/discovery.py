import importlib
from pathlib import Path
from typing import Callable

SKILLS_DIR = Path(__file__).parent / "skills"


def _parse_frontmatter(skill_md: Path) -> dict[str, str]:
    """Deliberately minimal: current frontmatter is flat `name: value`
    pairs. A real YAML parser should replace this if it ever needs to
    hold nested or multiline fields."""
    content = skill_md.read_text()
    _, frontmatter, _ = content.split("---", 2)
    fields = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def discover_skills(skills_dir: Path = SKILLS_DIR) -> tuple[list[dict], dict[str, Callable]]:
    """Scans a trusted directory for reviewed skill folders and builds
    both a model-facing schema list and an application-owned registry.

    Sorted traversal makes discovery deterministic. A folder without
    SKILL.md is ignored -- presence of arbitrary code does not by
    itself advertise a skill.
    """
    tool_schemas: list[dict] = []
    tool_registry: dict[str, Callable] = {}

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue

        fields = _parse_frontmatter(skill_md)
        module = importlib.import_module(f"skills.{skill_dir.name}.skill")
        tool_registry[fields["name"]] = module.load_instructions
        tool_schemas.append(
            {
                "type": "function",
                "function": {
                    "name": fields["name"],
                    "description": fields.get("description", ""),
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        )

    return tool_schemas, tool_registry
