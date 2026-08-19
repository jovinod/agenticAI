"""
Skill discovery -- scans skills/ for any folder with a SKILL.md (the
genuinely LLM-discoverable kind, see book/chapter-04-the-first-agent.md)
and builds tool schemas + a registry dynamically from what's actually on
disk. This is what replaces an agent hardcoding a specific skill by name:
add a new skill folder with a SKILL.md and every agent that calls
discover_skills() sees it immediately, with zero code changes anywhere.

flag_risk_factors is deliberately never discovered here -- it has no
SKILL.md, because it's a direct call (see its own module docstring), not
a model choice. Discovery only concerns itself with skills meant to be
chosen, not skills that always run.
"""
import importlib
import pathlib

SKILLS_DIR = pathlib.Path(__file__).parent


def _parse_frontmatter(skill_md_path: pathlib.Path) -> dict:
    """Minimal flat key: value parser -- SKILL.md frontmatter here is just
    `name` and `description`, not nested structure, so a real YAML library
    would be more dependency than the actual shape needs."""
    content = skill_md_path.read_text()
    _, frontmatter, _ = content.split("---", 2)
    fields = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def discover_skills() -> tuple[list[dict], dict]:
    """Returns (tool_schemas, tool_registry) for every skill folder under
    skills/ that has a SKILL.md. Built fresh from disk every call -- not a
    fixed list maintained by hand, so a new skill folder is picked up
    without touching this file or any agent that uses it."""
    tool_schemas = []
    tool_registry = {}

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue

        fields = _parse_frontmatter(skill_md)
        name = fields["name"]

        module = importlib.import_module(f"skills.{skill_dir.name}.skill")

        tool_schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": fields["description"],
                "parameters": {"type": "object", "properties": {}},
            },
        })
        tool_registry[name] = module.load_instructions

    return tool_schemas, tool_registry
