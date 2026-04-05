"""Skills management."""

from pathlib import Path


class SkillsLoader:
    """Loads and manages agent skills."""

    def __init__(self, workspace_path: Path) -> None:
        """Initialize skills loader."""
        self.workspace_path = workspace_path
        self.workspace_skills_dir = workspace_path / "skills"

    def list_skills(self) -> list[str]:
        """List available skills."""
        skills = []
        if self.workspace_skills_dir.exists():
            for item in self.workspace_skills_dir.iterdir():
                if item.is_dir():
                    skill_file = item / "SKILL.md"
                    if skill_file.exists():
                        skills.append(item.name)
        return sorted(skills)

    def load_skill(self, name: str) -> str | None:
        """Load a skill by name."""
        skill_file = self.workspace_skills_dir / name / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")
        return None

    def get_skills_for_context(self, names: list[str]) -> str:
        """Load multiple skills for context inclusion."""
        parts = []
        for name in names:
            content = self.load_skill(name)
            if content:
                parts.append(f"## Skill: {name}\n\n{content}")
        return "\n\n---\n\n".join(parts) if parts else ""
