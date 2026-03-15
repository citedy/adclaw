import os
import tempfile
import pytest
from adclaw.agents.tools.shared_memory import make_read_shared_file, make_write_shared_file, make_list_shared_files


class TestSharedMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.shared_root = os.path.join(self.tmpdir, "shared")
        os.makedirs(os.path.join(self.shared_root, "researcher"), exist_ok=True)
        os.makedirs(os.path.join(self.shared_root, "content"), exist_ok=True)

    def test_write_shared_file(self):
        write_fn = make_write_shared_file(self.shared_root, "researcher")
        result = write_fn(filename="report.md", content="# Daily Report\nTrending: AI agents")
        assert "success" in result.lower()
        assert os.path.exists(os.path.join(self.shared_root, "researcher", "report.md"))

    def test_write_rejects_path_traversal(self):
        write_fn = make_write_shared_file(self.shared_root, "researcher")
        result = write_fn(filename="../../../etc/passwd", content="hack")
        assert "error" in result.lower()

    def test_read_shared_file(self):
        with open(os.path.join(self.shared_root, "researcher", "report.md"), "w") as f:
            f.write("# Report\nContent here")
        read_fn = make_read_shared_file(self.shared_root)
        result = read_fn(agent_id="researcher", filename="report.md")
        assert "Content here" in result

    def test_read_nonexistent(self):
        read_fn = make_read_shared_file(self.shared_root)
        result = read_fn(agent_id="researcher", filename="nope.md")
        assert "not found" in result.lower()

    def test_read_rejects_path_traversal(self):
        read_fn = make_read_shared_file(self.shared_root)
        result = read_fn(agent_id="researcher", filename="../../etc/passwd")
        assert "error" in result.lower()

    def test_list_shared_files(self):
        with open(os.path.join(self.shared_root, "researcher", "a.md"), "w") as f:
            f.write("a")
        with open(os.path.join(self.shared_root, "researcher", "b.md"), "w") as f:
            f.write("b")
        list_fn = make_list_shared_files(self.shared_root)
        result = list_fn(agent_id="researcher")
        assert "a.md" in result
        assert "b.md" in result

    def test_list_all_agents_shared(self):
        list_fn = make_list_shared_files(self.shared_root)
        result = list_fn()
        assert "researcher" in result
        assert "content" in result

    def test_write_only_own_dir(self):
        write_fn = make_write_shared_file(self.shared_root, "researcher")
        result = write_fn(filename="../content/hack.md", content="hacked")
        assert "error" in result.lower()

    def test_cross_agent_read(self):
        write_r = make_write_shared_file(self.shared_root, "researcher")
        write_r(filename="intel.md", content="Breaking: new model")
        read_c = make_read_shared_file(self.shared_root)
        result = read_c(agent_id="researcher", filename="intel.md")
        assert "Breaking" in result
