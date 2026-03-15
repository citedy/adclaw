import pytest
from unittest.mock import AsyncMock
from pathlib import Path


@pytest.fixture
def broken_skill_dir(tmp_path):
    skill_dir = tmp_path / "broken-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        '---\nname: broken\nmetadata: {"emoji":"\\ud83d\\udc26"}\n---\n# Broken'
    )
    return skill_dir


@pytest.fixture
def no_frontmatter_skill_dir(tmp_path):
    skill_dir = tmp_path / "no-fm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Just a heading\n\nSome content.")
    return skill_dir


@pytest.mark.asyncio
async def test_heal_broken_yaml(broken_skill_dir):
    from adclaw.agents.skill_healer import heal_skill

    fixed_content = '---\nname: broken\ndescription: A broken skill fixed.\nmetadata: {"emoji":"bird"}\n---\n# Broken'
    mock_llm = AsyncMock(return_value=fixed_content)

    result = await heal_skill(
        skill_dir=broken_skill_dir,
        error_message='found invalid Unicode character escape code',
        llm_caller=mock_llm,
    )

    assert result.healed is True
    assert result.original != result.fixed
    actual = (broken_skill_dir / "SKILL.md").read_text()
    assert "\\ud83d" not in actual


@pytest.mark.asyncio
async def test_heal_missing_frontmatter(no_frontmatter_skill_dir):
    from adclaw.agents.skill_healer import heal_skill

    fixed_content = '---\nname: no-fm-skill\ndescription: A skill without frontmatter.\n---\n# Just a heading\n\nSome content.'
    mock_llm = AsyncMock(return_value=fixed_content)

    result = await heal_skill(
        skill_dir=no_frontmatter_skill_dir,
        error_message="must have a YAML Front Matter including `name` and `description`",
        llm_caller=mock_llm,
    )

    assert result.healed is True
    actual = (no_frontmatter_skill_dir / "SKILL.md").read_text()
    assert "name: no-fm-skill" in actual


@pytest.mark.asyncio
async def test_heal_llm_fails_gracefully(tmp_path):
    from adclaw.agents.skill_healer import heal_skill

    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# No frontmatter")
    original = (skill_dir / "SKILL.md").read_text()

    mock_llm = AsyncMock(side_effect=Exception("LLM unavailable"))

    result = await heal_skill(
        skill_dir=skill_dir,
        error_message="missing frontmatter",
        llm_caller=mock_llm,
    )

    assert result.healed is False
    assert (skill_dir / "SKILL.md").read_text() == original


@pytest.mark.asyncio
async def test_heal_preserves_backup(broken_skill_dir):
    from adclaw.agents.skill_healer import heal_skill

    fixed = '---\nname: broken\ndescription: Fixed.\n---\n# Broken'
    mock_llm = AsyncMock(return_value=fixed)

    await heal_skill(broken_skill_dir, "error", mock_llm)

    backup = broken_skill_dir / "SKILL.md.bak"
    assert backup.exists()
    assert "\\ud83d" in backup.read_text()


@pytest.mark.asyncio
async def test_register_with_healing(tmp_path):
    from adclaw.agents.skill_healer import heal_skill

    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# No frontmatter at all\nJust text.")

    fixed = '---\nname: test-skill\ndescription: Test skill.\n---\n# No frontmatter at all\nJust text.'
    mock_llm = AsyncMock(return_value=fixed)

    result = await heal_skill(skill_dir, "must have YAML Front Matter", mock_llm)
    assert result.healed is True

    import frontmatter
    post = frontmatter.load(str(skill_dir / "SKILL.md"))
    assert post["name"] == "test-skill"
    assert post["description"] == "Test skill."


@pytest.mark.asyncio
async def test_heal_strips_code_fences(tmp_path):
    from adclaw.agents.skill_healer import heal_skill

    skill_dir = tmp_path / "fenced-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# No frontmatter")

    # LLM wraps response in code fences
    fenced = '```markdown\n---\nname: fenced-skill\ndescription: Fixed.\n---\n# No frontmatter\n```'
    mock_llm = AsyncMock(return_value=fenced)

    result = await heal_skill(skill_dir, "missing frontmatter", mock_llm)
    assert result.healed is True
    actual = (skill_dir / "SKILL.md").read_text()
    assert actual.startswith("---")
    assert "```" not in actual
