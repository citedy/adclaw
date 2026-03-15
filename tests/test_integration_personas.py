import os
import pytest
import tempfile
from adclaw.config.config import Config, AgentsConfig, PersonaConfig, PersonaCronConfig
from adclaw.agents.persona_manager import PersonaManager
from adclaw.agents.persona_templates import TEMPLATES, get_template
from adclaw.agents.tools.shared_memory import (
    make_read_shared_file, make_write_shared_file, make_list_shared_files,
)
from adclaw.agents.tools.delegation import make_delegate_tool, DelegationContext
from adclaw.app.crons.persona_sync import build_persona_cron_jobs, get_persona_cron_job_ids


class TestFullOrchestration:
    """Integration tests for multi-agent persona system."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.personas = [
            PersonaConfig(
                id="coordinator",
                name="Coordinator",
                soul_md="## Coordinator\nYou orchestrate the team.",
                is_coordinator=True,
            ),
            PersonaConfig(
                id="researcher",
                name="Researcher",
                soul_md="## Researcher\nYou find facts.",
                model_provider="aliyun-intl",
                model_name="qwen3.5-plus",
                mcp_clients=["brave_search"],
                cron=PersonaCronConfig(
                    enabled=True,
                    schedule="0 8,14,20 * * *",
                    prompt="Scan for AI trends",
                    output="both",
                ),
            ),
            PersonaConfig(
                id="content",
                name="Content Writer",
                soul_md="## Content\nYou write posts.",
                skills=["content_writing"],
                mcp_clients=["citedy"],
            ),
        ]
        self.mgr = PersonaManager(working_dir=self.tmpdir, personas=self.personas)
        self.mgr.ensure_dirs()

    # --- Routing (10 tests) ---

    def test_tag_routing_researcher(self):
        assert self.mgr.resolve_tag("@researcher find AI trends") == "researcher"

    def test_tag_routing_content(self):
        assert self.mgr.resolve_tag("@content write a blog post") == "content"

    def test_tag_routing_coordinator(self):
        assert self.mgr.resolve_tag("@coordinator status update") == "coordinator"

    def test_no_tag_returns_none(self):
        assert self.mgr.resolve_tag("just a regular message") is None

    def test_coordinator_fallback(self):
        coord = self.mgr.get_coordinator()
        assert coord.id == "coordinator"

    def test_strip_tag(self):
        assert self.mgr.strip_tag("@researcher find trends") == "find trends"

    def test_strip_no_tag(self):
        assert self.mgr.strip_tag("no tag here") == "no tag here"

    def test_unknown_tag_returns_none(self):
        assert self.mgr.resolve_tag("@unknown hello") is None

    def test_tag_case_insensitive(self):
        assert self.mgr.resolve_tag("@Researcher find trends") == "researcher"  # case-insensitive

    def test_tag_at_middle_ignored(self):
        assert self.mgr.resolve_tag("hello @researcher") is None  # not at start

    # --- Working dirs (5 tests) ---

    def test_agent_working_dirs_created(self):
        for pid in ["coordinator", "researcher", "content"]:
            assert os.path.isdir(os.path.join(self.tmpdir, "agents", pid))

    def test_memory_dirs_created(self):
        for pid in ["coordinator", "researcher", "content"]:
            assert os.path.isdir(os.path.join(self.tmpdir, "agents", pid, "memory"))

    def test_shared_dirs_created(self):
        for pid in ["coordinator", "researcher", "content"]:
            assert os.path.isdir(os.path.join(self.tmpdir, "shared", pid))

    def test_working_dir_path(self):
        d = self.mgr.get_working_dir("researcher")
        assert "agents/researcher" in d

    def test_shared_dir_path(self):
        d = self.mgr.get_shared_dir("researcher")
        assert "shared/researcher" in d

    # --- Shared memory (8 tests) ---

    def test_shared_write_read_cycle(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        write = make_write_shared_file(shared_root, "researcher")
        read = make_read_shared_file(shared_root)
        result = write(filename="trends.md", content="# AI Trends\n1. Agents\n2. MCP")
        assert "success" in result.lower()
        content = read(agent_id="researcher", filename="trends.md")
        assert "AI Trends" in content

    def test_shared_cross_agent_read(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        write_r = make_write_shared_file(shared_root, "researcher")
        write_r(filename="intel.md", content="Breaking: new model released")
        read_c = make_read_shared_file(shared_root)
        result = read_c(agent_id="researcher", filename="intel.md")
        assert "Breaking" in result

    def test_shared_path_traversal_write_blocked(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        write = make_write_shared_file(shared_root, "researcher")
        result = write(filename="../../../etc/passwd", content="hack")
        assert "error" in result.lower()

    def test_shared_path_traversal_read_blocked(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        read = make_read_shared_file(shared_root)
        result = read(agent_id="researcher", filename="../../etc/passwd")
        assert "error" in result.lower()

    def test_shared_write_cross_dir_blocked(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        write = make_write_shared_file(shared_root, "researcher")
        result = write(filename="../content/hack.md", content="hacked")
        assert "error" in result.lower()

    def test_shared_read_nonexistent(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        read = make_read_shared_file(shared_root)
        result = read(agent_id="researcher", filename="nope.md")
        assert "not found" in result.lower()

    def test_shared_list_files(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        write = make_write_shared_file(shared_root, "researcher")
        write(filename="a.md", content="a")
        write(filename="b.md", content="b")
        list_fn = make_list_shared_files(shared_root)
        result = list_fn(agent_id="researcher")
        assert "a.md" in result
        assert "b.md" in result

    def test_shared_read_agent_id_traversal(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        read = make_read_shared_file(shared_root)
        result = read(agent_id="../../etc", filename="passwd")
        assert "error" in result.lower()

    def test_shared_list_agent_id_traversal(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        list_fn = make_list_shared_files(shared_root)
        result = list_fn(agent_id="../../../etc")
        assert "error" in result.lower()

    def test_shared_list_all_agents(self):
        shared_root = os.path.join(self.tmpdir, "shared")
        list_fn = make_list_shared_files(shared_root)
        result = list_fn()
        assert "researcher" in result
        assert "content" in result
        assert "coordinator" in result

    # --- Team summary (3 tests) ---

    def test_team_summary_includes_all(self):
        summary = self.mgr.get_team_summary()
        assert "@coordinator" in summary
        assert "@researcher" in summary
        assert "@content" in summary

    def test_team_summary_shows_coordinator(self):
        summary = self.mgr.get_team_summary()
        assert "coordinator" in summary.lower()

    def test_team_summary_shows_roles(self):
        summary = self.mgr.get_team_summary()
        assert "Researcher" in summary
        assert "Content Writer" in summary

    # --- Config (5 tests) ---

    def test_persona_model_override(self):
        p = self.mgr.get_persona("researcher")
        assert p.model_provider == "aliyun-intl"
        assert p.model_name == "qwen3.5-plus"

    def test_persona_skill_filter(self):
        p = self.mgr.get_persona("content")
        assert p.skills == ["content_writing"]

    def test_persona_mcp_filter(self):
        p = self.mgr.get_persona("researcher")
        assert p.mcp_clients == ["brave_search"]

    def test_config_round_trip(self):
        cfg = Config(agents=AgentsConfig(personas=self.personas))
        data = cfg.model_dump()
        cfg2 = Config(**data)
        assert len(cfg2.agents.personas) == 3

    def test_config_empty_personas_default(self):
        cfg = Config()
        assert cfg.agents.personas == []

    # --- Cron (4 tests) ---

    def test_cron_build_jobs(self):
        jobs = build_persona_cron_jobs(self.personas)
        assert len(jobs) == 1
        assert jobs[0]["id"] == "persona_researcher"
        assert jobs[0]["output_mode"] == "both"

    def test_cron_job_ids(self):
        ids = get_persona_cron_job_ids(self.personas)
        assert ids == {"persona_researcher"}

    def test_cron_disabled_not_included(self):
        personas = [PersonaConfig(id="x", name="X", cron=PersonaCronConfig(enabled=False, schedule="0 8 * * *", prompt="x"))]
        assert build_persona_cron_jobs(personas) == []

    def test_cron_no_cron_not_included(self):
        personas = [PersonaConfig(id="x", name="X")]
        assert build_persona_cron_jobs(personas) == []

    # --- Delegation (4 tests) ---

    def test_delegation_tool_created(self):
        tool = make_delegate_tool(self.mgr)
        assert callable(tool)

    def test_delegation_unknown_agent(self):
        tool = make_delegate_tool(self.mgr)
        result = tool(agent_id="nonexistent", task="do something")
        assert "not found" in result.lower()

    def test_delegation_depth_limit(self):
        ctx = DelegationContext(max_depth=2)
        assert ctx.can_delegate()
        ctx.depth = 2
        assert not ctx.can_delegate()

    def test_delegation_lists_available(self):
        tool = make_delegate_tool(self.mgr)
        result = tool(agent_id="nope", task="test")
        assert "coordinator" in result
        assert "researcher" in result

    # --- Templates (3 tests) ---

    def test_all_templates_valid(self):
        for t in TEMPLATES:
            p = PersonaConfig(**t)
            assert p.id
            assert p.name

    def test_template_creates_persona(self):
        tmpl = get_template("researcher")
        persona = PersonaConfig(**tmpl)
        assert persona.id == "researcher"
        assert len(persona.soul_md) > 50

    def test_template_returns_copy(self):
        t1 = get_template("researcher")
        t2 = get_template("researcher")
        t1["name"] = "Modified"
        assert t2["name"] == "Researcher"
        # Verify deep copy — nested mutable lists are independent
        t1["mcp_clients"].append("test_mcp")
        assert "test_mcp" not in t2["mcp_clients"]
        t1["skills"].append("test_skill")
        assert "test_skill" not in t2["skills"]
        # Verify suggested_mcp_clients (mutable list) is also independent
        t1["suggested_mcp_clients"].append("extra")
        assert "extra" not in t2["suggested_mcp_clients"]

    # --- Backward compat (3 tests) ---

    def test_empty_personas_no_crash(self):
        mgr = PersonaManager(working_dir=self.tmpdir, personas=[])
        assert mgr.get_coordinator() is None
        assert mgr.resolve_tag("@test hi") is None
        assert mgr.all_personas == []

    def test_config_without_personas_works(self):
        config = Config()
        assert config.agents.personas == []
        mgr = PersonaManager(working_dir=self.tmpdir, personas=config.agents.personas)
        assert mgr.all_personas == []

    def test_team_summary_empty_personas(self):
        mgr = PersonaManager(working_dir=self.tmpdir, personas=[])
        summary = mgr.get_team_summary()
        assert "Team" in summary
