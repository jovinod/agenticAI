"""
Loader for this skill's instructions. Unlike flag_risk_factors (Phase 3), this
skill has no logic of its own -- calling it doesn't compute anything. It reads
the accompanying SKILL.md and hands its body back as plain text, which the
agent feeds to the model as a tool result. The model is then the one that
applies those instructions, using its own judgment, to whatever news content
it already has -- exactly the way tutor/SKILL.md's own instructions get
followed by judgment rather than executed as code.
"""
import pathlib

_SKILL_FILE = pathlib.Path(__file__).parent / "SKILL.md"


def load_instructions() -> str:
    content = _SKILL_FILE.read_text()
    _, _, body = content.split("---", 2)  # drop the YAML frontmatter, keep the instructions
    return body.strip()
