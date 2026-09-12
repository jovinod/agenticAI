from pathlib import Path

_SKILL_FILE = Path(__file__).parent / "SKILL.md"


def load_instructions() -> str:
    """Returns guidance -- it does not assess sentiment itself. The
    model-facing name describes why an agent may choose this capability;
    this function's name describes what the code actually does."""
    content = _SKILL_FILE.read_text()
    _, _, body = content.split("---", 2)
    return body.strip()
