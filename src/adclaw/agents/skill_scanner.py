# -*- coding: utf-8 -*-
"""Skill security scanner — static analysis of skill scripts before installation."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Finding:
    """A security finding in a skill file."""

    severity: str  # "critical", "high", "medium", "low"
    category: str = ""
    file: str = ""
    line: int = 0
    description: str = ""
    code_snippet: str = ""

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.file}:{self.line} — {self.description}"


@dataclass
class ScanResult:
    """Result of a skill security scan."""

    safe: bool
    skill_name: str
    findings: List[Finding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "skill_name": self.skill_name,
            "files_scanned": self.files_scanned,
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "file": f.file,
                    "line": f.line,
                    "description": f.description,
                    "code_snippet": f.code_snippet,
                }
                for f in self.findings
            ],
            "summary": {
                "critical": self.critical_count,
                "high": self.high_count,
                "total": len(self.findings),
            },
        }


# ============================================================================
# Category 1: Code Execution (eval/exec/compile)
# ============================================================================

_DANGEROUS_CALLS = {
    "eval": "critical",
    "exec": "critical",
    "compile": "high",
    "__import__": "high",
    "breakpoint": "medium",
    "globals": "medium",
    "locals": "medium",
    "vars": "low",
    "getattr": "low",
    "setattr": "medium",
    "delattr": "medium",
}

# ============================================================================
# Category 2: Dangerous module.function patterns
# ============================================================================

_DANGEROUS_ATTRS = {
    # OS command execution
    ("os", "system"): ("critical", "os.system() — arbitrary command execution"),
    ("os", "popen"): ("critical", "os.popen() — arbitrary command execution"),
    ("os", "exec"): ("critical", "os.exec*() — process replacement"),
    ("os", "execvp"): ("critical", "os.execvp() — process replacement"),
    ("os", "execve"): ("critical", "os.execve() — process replacement"),
    ("os", "execl"): ("critical", "os.execl() — process replacement"),
    ("os", "execlp"): ("critical", "os.execlp() — process replacement"),
    ("os", "spawn"): ("high", "os.spawn*() — process spawning"),
    ("os", "spawnl"): ("high", "os.spawnl() — process spawning"),
    ("os", "spawnle"): ("high", "os.spawnle() — process spawning"),
    ("os", "spawnlp"): ("high", "os.spawnlp() — process spawning"),
    ("os", "fork"): ("critical", "os.fork() — process forking"),
    ("os", "kill"): ("high", "os.kill() — process termination"),
    ("os", "killpg"): ("high", "os.killpg() — process group termination"),
    # File system destructive ops
    ("os", "remove"): ("medium", "os.remove() — file deletion"),
    ("os", "unlink"): ("medium", "os.unlink() — file deletion"),
    ("os", "rmdir"): ("medium", "os.rmdir() — directory deletion"),
    ("os", "rename"): ("low", "os.rename() — file rename"),
    ("os", "chmod"): ("medium", "os.chmod() — permission change"),
    ("os", "chown"): ("high", "os.chown() — ownership change"),
    ("os", "setuid"): ("critical", "os.setuid() — privilege escalation"),
    ("os", "setgid"): ("critical", "os.setgid() — privilege escalation"),
    ("os", "seteuid"): ("critical", "os.seteuid() — privilege escalation"),
    ("os", "setegid"): ("critical", "os.setegid() — privilege escalation"),
    # shutil
    ("shutil", "rmtree"): ("high", "shutil.rmtree() — recursive directory deletion"),
    ("shutil", "move"): ("low", "shutil.move() — file move"),
    ("shutil", "chown"): ("high", "shutil.chown() — ownership change"),
    # subprocess
    ("subprocess", "call"): ("high", "subprocess.call() — command execution"),
    ("subprocess", "Popen"): ("high", "subprocess.Popen() — command execution"),
    ("subprocess", "run"): ("medium", "subprocess.run() — command execution"),
    ("subprocess", "check_call"): ("high", "subprocess.check_call() — command execution"),
    ("subprocess", "check_output"): ("high", "subprocess.check_output() — command execution"),
    ("subprocess", "getoutput"): ("high", "subprocess.getoutput() — command execution"),
    ("subprocess", "getstatusoutput"): ("high", "subprocess.getstatusoutput() — command execution"),
    # Dynamic imports
    ("importlib", "import_module"): ("high", "Dynamic module import"),
    ("importlib", "__import__"): ("high", "Dynamic module import"),
    # Native code / FFI
    ("ctypes", "cdll"): ("critical", "ctypes — native code execution"),
    ("ctypes", "CDLL"): ("critical", "ctypes — native code execution"),
    ("ctypes", "windll"): ("critical", "ctypes — native code execution"),
    ("ctypes", "WinDLL"): ("critical", "ctypes — native code execution"),
    ("ctypes", "oledll"): ("critical", "ctypes — native code execution"),
    ("ctypes", "pythonapi"): ("critical", "ctypes — Python C API access"),
    ("cffi", "FFI"): ("high", "cffi — foreign function interface"),
    # Deserialization
    ("pickle", "loads"): ("high", "pickle.loads() — deserialization attack vector"),
    ("pickle", "load"): ("high", "pickle.load() — deserialization attack vector"),
    ("pickle", "Unpickler"): ("high", "pickle.Unpickler() — deserialization attack vector"),
    ("marshal", "loads"): ("high", "marshal.loads() — code object deserialization"),
    ("marshal", "load"): ("high", "marshal.load() — code object deserialization"),
    ("yaml", "load"): ("high", "yaml.load() — unsafe YAML deserialization (use safe_load)"),
    ("yaml", "unsafe_load"): ("critical", "yaml.unsafe_load() — arbitrary code execution"),
    ("shelve", "open"): ("medium", "shelve.open() — uses pickle internally"),
    ("dill", "loads"): ("high", "dill.loads() — deserialization attack vector"),
    ("dill", "load"): ("high", "dill.load() — deserialization attack vector"),
    ("jsonpickle", "decode"): ("high", "jsonpickle.decode() — deserialization attack vector"),
    # Networking
    ("socket", "socket"): ("medium", "Raw socket creation"),
    ("socket", "create_connection"): ("medium", "Socket connection"),
    ("http", "server"): ("medium", "HTTP server creation"),
    ("smtplib", "SMTP"): ("medium", "SMTP email sending"),
    ("ftplib", "FTP"): ("medium", "FTP connection"),
    ("telnetlib", "Telnet"): ("high", "Telnet connection"),
    ("paramiko", "SSHClient"): ("high", "SSH client connection"),
    ("paramiko", "Transport"): ("high", "SSH transport connection"),
    # Code generation / templating
    ("jinja2", "Template"): ("low", "Jinja2 template — check for SSTI"),
    ("mako", "template"): ("medium", "Mako template — potential SSTI"),
    # Crypto mining indicators
    ("hashlib", "sha256"): ("low", "SHA-256 — check context for mining"),
    # System info gathering
    ("platform", "system"): ("low", "System info gathering"),
    ("platform", "node"): ("low", "Hostname gathering"),
    # Signals
    ("signal", "signal"): ("medium", "Signal handler modification"),
    ("signal", "alarm"): ("medium", "Alarm signal"),
    # Weak crypto
    ("hashlib", "md5"): ("low", "MD5 — weak hash, check if used for security"),
    ("hashlib", "sha1"): ("low", "SHA-1 — weak hash, check if used for security"),
}

# ============================================================================
# Category 3: Dangerous imports
# ============================================================================

_CRITICAL_MODULES = {"ctypes"}
_DANGEROUS_MODULES = {
    "ctypes", "pickle", "marshal", "shelve", "dill", "jsonpickle",
    "pty", "commands",  # deprecated but dangerous
}

# ============================================================================
# Category 4: Sensitive file paths
# ============================================================================

_SENSITIVE_PATHS = [
    r"/etc/passwd",
    r"/etc/shadow",
    r"/etc/sudoers",
    r"/etc/crontab",
    r"~/.ssh",
    r"\.env",
    r"\.secret",
    r"\.aws/credentials",
    r"\.aws/config",
    r"\.kube/config",
    r"id_rsa",
    r"id_ed25519",
    r"\.git/config",
    r"\.netrc",
    r"\.pgpass",
    r"\.mysql_history",
    r"\.bash_history",
    r"\.zsh_history",
    r"/proc/self",
    r"\.docker/config\.json",
    r"\.npmrc",
    r"\.pypirc",
    r"authorized_keys",
    r"known_hosts",
    r"/var/log/",
    r"\.gnupg/",
]
_SENSITIVE_PATH_RE = re.compile("|".join(_SENSITIVE_PATHS), re.IGNORECASE)

# ============================================================================
# Category 5: Network exfiltration patterns in string literals
# ============================================================================

_EXFIL_PATTERNS = [
    (
        r"(?i)https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[^\s\"']+",
        "medium",
        "External URL in string literal",
    ),
]

# Safe domains that are commonly used and not suspicious
_SAFE_DOMAINS = (
    "github.com", "pypi.org", "npmjs.com", "npmjs.org",
    "googleapis.com", "microsoft.com", "python.org",
    "readthedocs.io", "example.com", "mozilla.org",
    "cloudflare.com", "fastly.net", "unpkg.com",
    "cdnjs.cloudflare.com", "cdn.jsdelivr.net",
    "registry.npmjs.org", "files.pythonhosted.org",
)

# ============================================================================
# Category 6: Shell injection patterns
# ============================================================================

_SHELL_PATTERNS: list[tuple[str, str, str, str]] = [
    # (pattern, severity, description, category)
    # Remote code execution
    (
        r"(?i)curl\s+[^\n]*\|\s*(sh|bash|zsh|python|python3|perl|ruby|node)",
        "critical", "curl piped to shell — remote code execution", "rce",
    ),
    (
        r"(?i)wget\s+[^\n]*\|\s*(sh|bash|zsh|python|python3|perl|ruby|node)",
        "critical", "wget piped to shell — remote code execution", "rce",
    ),
    (
        r"(?i)curl\s+[^\n]*>\s*/tmp/[^\s]+\s*&&\s*(sh|bash|chmod|python)",
        "high", "Download and execute pattern", "rce",
    ),
    (
        r"(?i)(curl|wget)\s+[^\n]*(--output|-o|-O)\s+[^\s]+\s*&&\s*(chmod|sh|bash)",
        "high", "Download, chmod, execute pattern", "rce",
    ),
    # Destructive commands
    (
        r"(?i)rm\s+-rf\s+/(?!\w)",
        "critical", "Destructive rm -rf / command", "destructive",
    ),
    (
        r"(?i)rm\s+-rf\s+~",
        "critical", "Destructive rm -rf ~ (home directory)", "destructive",
    ),
    (
        r"(?i)rm\s+-rf\s+\$HOME",
        "critical", "Destructive rm -rf $HOME", "destructive",
    ),
    (
        r"(?i)rm\s+-rf\s+/var|/usr|/etc|/opt|/boot",
        "critical", "Destructive rm -rf on system directory", "destructive",
    ),
    (
        r":\(\)\{[^\}]*:\|:&[^\}]*\};:",
        "critical", "Fork bomb", "destructive",
    ),
    (
        r"(?i)mkfs\.|dd\s+if=.*of=/dev/",
        "critical", "Disk destruction command", "destructive",
    ),
    (
        r"(?i)>\s*/dev/sd[a-z]|>\s*/dev/nvme|>\s*/dev/vd[a-z]",
        "critical", "Write to raw block device", "destructive",
    ),
    # Reverse shells
    (
        r"(?i)bash\s+-i\s+>&\s*/dev/tcp/",
        "critical", "Bash reverse shell", "reverse_shell",
    ),
    (
        r"(?i)nc\s+(-e|-c)\s+",
        "critical", "Netcat reverse/bind shell", "reverse_shell",
    ),
    (
        r"(?i)ncat\s+(-e|-c)\s+",
        "critical", "Ncat reverse/bind shell", "reverse_shell",
    ),
    (
        r"(?i)socat\s+.*exec:",
        "critical", "Socat exec — potential reverse shell", "reverse_shell",
    ),
    (
        r"(?i)/dev/tcp/[0-9]",
        "critical", "/dev/tcp redirection — reverse shell indicator", "reverse_shell",
    ),
    (
        r"(?i)python3?\s+-c\s+['\"]import\s+socket",
        "critical", "Python reverse shell", "reverse_shell",
    ),
    (
        r"(?i)perl\s+-e\s+.*socket",
        "critical", "Perl reverse shell", "reverse_shell",
    ),
    (
        r"(?i)ruby\s+-rsocket\s+-e",
        "critical", "Ruby reverse shell", "reverse_shell",
    ),
    (
        r"(?i)php\s+-r\s+.*fsockopen",
        "critical", "PHP reverse shell", "reverse_shell",
    ),
    (
        r"(?i)mkfifo\s+/tmp/.*\s*&&\s*(nc|ncat|cat)",
        "critical", "Named pipe reverse shell", "reverse_shell",
    ),
    # Crypto mining
    (
        r"(?i)xmrig|minerd|cpuminer|cgminer|ethminer|bfgminer|nicehash",
        "critical", "Cryptocurrency miner detected", "crypto_mining",
    ),
    (
        r"(?i)stratum(\+tcp)?://",
        "critical", "Mining pool connection (stratum protocol)", "crypto_mining",
    ),
    (
        r"(?i)--donate-level|--coin\s+(XMR|ETH|BTC|MONERO)",
        "critical", "Mining configuration flag", "crypto_mining",
    ),
    # Persistence mechanisms
    (
        r"(?i)crontab\s+-[elr]",
        "high", "Crontab modification", "persistence",
    ),
    (
        r"(?i)/etc/cron\.(d|daily|hourly|weekly|monthly)/",
        "high", "System cron directory access", "persistence",
    ),
    (
        r"(?i)systemctl\s+(enable|start|daemon-reload)",
        "high", "Systemd service manipulation", "persistence",
    ),
    (
        r"(?i)/etc/systemd/system/.*\.service",
        "high", "Systemd service file creation", "persistence",
    ),
    (
        r"(?i)/etc/init\.d/",
        "high", "Init.d service manipulation", "persistence",
    ),
    (
        r"(?i)launchctl\s+(load|submit)",
        "high", "macOS LaunchAgent/Daemon loading", "persistence",
    ),
    (
        r"(?i)~/Library/LaunchAgents/",
        "high", "macOS LaunchAgent directory access", "persistence",
    ),
    (
        r"(?i)@reboot\s+",
        "high", "Cron @reboot persistence", "persistence",
    ),
    (
        r"(?i)\.bashrc|\.bash_profile|\.zshrc|\.profile",
        "medium", "Shell profile modification", "persistence",
    ),
    # Privilege escalation
    (
        r"(?i)sudo\s+",
        "medium", "sudo usage — potential privilege escalation", "privesc",
    ),
    (
        r"(?i)chmod\s+[0-7]*[4-7][0-7]{2}\s+|chmod\s+[ug]\+s\s+",
        "high", "Set SUID/SGID bit — privilege escalation", "privesc",
    ),
    (
        r"(?i)chown\s+root",
        "high", "Change file owner to root", "privesc",
    ),
    (
        r"(?i)/etc/sudoers",
        "critical", "Sudoers file access", "privesc",
    ),
    (
        r"(?i)visudo|NOPASSWD",
        "critical", "Sudoers modification — passwordless sudo", "privesc",
    ),
    (
        r"(?i)passwd\s+(root|--stdin)",
        "critical", "Password change for root", "privesc",
    ),
    (
        r"(?i)useradd|adduser|usermod",
        "high", "User account manipulation", "privesc",
    ),
    # SSH backdoors
    (
        r"(?i)ssh-keygen\s+",
        "high", "SSH key generation", "ssh_backdoor",
    ),
    (
        r"(?i)>>.*authorized_keys",
        "critical", "SSH authorized_keys append — backdoor", "ssh_backdoor",
    ),
    (
        r"(?i)ssh\s+-R\s+",
        "high", "SSH remote port forwarding", "ssh_backdoor",
    ),
    (
        r"(?i)ssh\s+-D\s+",
        "high", "SSH SOCKS proxy", "ssh_backdoor",
    ),
    (
        r"(?i)sshpass\s+",
        "high", "sshpass — non-interactive SSH auth", "ssh_backdoor",
    ),
    # Data exfiltration via CLI
    (
        r"(?i)curl\s+-X\s*POST\s",
        "high", "curl POST — potential data exfiltration", "exfiltration",
    ),
    (
        r"(?i)curl\s+[^\n]*(--data|-d)\s",
        "high", "curl with data — potential exfiltration", "exfiltration",
    ),
    (
        r"(?i)wget\s+--post",
        "high", "wget POST — potential data exfiltration", "exfiltration",
    ),
    (
        r"(?i)\bscp\s+",
        "high", "scp file transfer", "exfiltration",
    ),
    (
        r"(?i)\brsync\s+.*@",
        "high", "rsync to remote host", "exfiltration",
    ),
    (
        r"(?i)base64\s.*\|\s*(curl|wget|nc)",
        "critical", "Base64 encode and exfiltrate", "exfiltration",
    ),
    (
        r"(?i)tar\s+.*\|\s*(curl|wget|nc|ssh)",
        "critical", "Archive and exfiltrate", "exfiltration",
    ),
    # Network reconnaissance
    (
        r"(?i)\bnmap\s+",
        "high", "nmap port scanning", "recon",
    ),
    (
        r"(?i)\bnetstat\s+",
        "medium", "Network statistics gathering", "recon",
    ),
    (
        r"(?i)\bifconfig\s|ip\s+addr",
        "low", "Network interface information", "recon",
    ),
    (
        r"(?i)\barp\s+-a",
        "medium", "ARP table enumeration", "recon",
    ),
    # Supply chain attacks
    (
        r"(?i)pip\s+install\s+[^\s]+\s+--index-url\s+(?!https://pypi\.org)",
        "critical", "pip install from non-standard index — supply chain risk", "supply_chain",
    ),
    (
        r"(?i)pip\s+install\s+--extra-index-url",
        "high", "pip extra-index-url — dependency confusion risk", "supply_chain",
    ),
    (
        r"(?i)npm\s+install\s+--registry\s+(?!https://registry\.npmjs\.org)",
        "critical", "npm install from non-standard registry", "supply_chain",
    ),
    (
        r"(?i)setup\.py\s+install|python\s+setup\.py",
        "medium", "setup.py execution — check for malicious hooks", "supply_chain",
    ),
    # Obfuscation
    (
        r"(?i)\\x[0-9a-f]{2}(\\x[0-9a-f]{2}){10,}",
        "high", "Hex-encoded payload — possible obfuscation", "obfuscation",
    ),
    (
        r"(?i)base64\s+-d|base64\s+--decode",
        "medium", "Base64 decoding — check for hidden commands", "obfuscation",
    ),
    (
        r"(?i)python3?\s+-c\s+['\"]exec\(|python3?\s+-c\s+['\"]eval\(",
        "critical", "Python exec/eval in one-liner — obfuscated execution", "obfuscation",
    ),
    (
        r"(?i)echo\s+[A-Za-z0-9+/]{50,}={0,2}\s*\|\s*base64\s+-d\s*\|\s*(sh|bash)",
        "critical", "Base64-obfuscated shell command", "obfuscation",
    ),
    # Environment/secrets access
    (
        r"(?i)printenv|env\s*$|set\s*$",
        "medium", "Environment variable dump", "env_access",
    ),
    (
        r"(?i)\$\{?[A-Z_]*(SECRET|TOKEN|KEY|PASSWORD|PASS|CREDENTIAL|AUTH)[A-Z_]*\}?",
        "medium", "Access to secret environment variable", "env_access",
    ),
    # Container escape
    (
        r"(?i)docker\s+run\s+.*--privileged",
        "critical", "Privileged Docker container — escape risk", "container_escape",
    ),
    (
        r"(?i)docker\s+run\s+.*-v\s+/:/",
        "critical", "Docker host root mount — container escape", "container_escape",
    ),
    (
        r"(?i)nsenter\s+",
        "critical", "nsenter — namespace escape", "container_escape",
    ),
    (
        r"(?i)mount\s+.*cgroup|/sys/fs/cgroup",
        "high", "Cgroup access — potential container escape", "container_escape",
    ),
    (
        r"(?i)/var/run/docker\.sock",
        "critical", "Docker socket access — container escape", "container_escape",
    ),
    # Kernel / low-level
    (
        r"(?i)insmod\s+|modprobe\s+|rmmod\s+",
        "critical", "Kernel module manipulation", "kernel",
    ),
    (
        r"(?i)/proc/sys/|sysctl\s+-w",
        "high", "Kernel parameter modification", "kernel",
    ),
    (
        r"(?i)iptables\s+|nftables\s+|firewall-cmd",
        "high", "Firewall rule modification", "kernel",
    ),
]

# ============================================================================
# Category 7: Python AST — additional dangerous patterns
# ============================================================================

# Code object manipulation
_CODE_OBJECT_ATTRS = {
    "co_code", "co_consts", "co_names", "co_varnames",
    "co_freevars", "co_cellvars", "co_filename",
}

# Metaclass / descriptor abuse
_META_PATTERNS = {
    "__subclasses__": ("high", "Access to subclasses — sandbox escape"),
    "__bases__": ("high", "Base class manipulation"),
    "__mro__": ("medium", "MRO inspection — potential sandbox escape"),
    "__class__": ("low", "Class access — check context"),
    "__globals__": ("critical", "Access to global variables — sandbox escape"),
    "__builtins__": ("critical", "Access to builtins — sandbox escape"),
    "__code__": ("high", "Code object access — bytecode manipulation"),
    "__reduce__": ("high", "Custom pickle reduce — deserialization attack"),
    "__reduce_ex__": ("high", "Custom pickle reduce — deserialization attack"),
    "__getstate__": ("medium", "Custom serialization"),
    "__setstate__": ("medium", "Custom deserialization"),
}


class _ASTScanner(ast.NodeVisitor):
    """AST visitor that collects security findings from Python code."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.findings: list[Finding] = []
        self._source_lines: list[str] = []

    def scan(self, source: str) -> list[Finding]:
        self._source_lines = source.splitlines()
        try:
            tree = ast.parse(source, filename=self.filepath)
        except SyntaxError:
            return []
        self.visit(tree)
        return self.findings

    def _snippet(self, lineno: int) -> str:
        if 0 < lineno <= len(self._source_lines):
            return self._source_lines[lineno - 1].strip()[:120]
        return ""

    def _add(self, severity: str, line: int, desc: str, category: str = "") -> None:
        self.findings.append(
            Finding(
                severity=severity,
                category=category,
                file=self.filepath,
                line=line,
                description=desc,
                code_snippet=self._snippet(line),
            )
        )

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # Direct function calls: eval(), exec(), compile()
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in _DANGEROUS_CALLS:
                severity = _DANGEROUS_CALLS[name]
                self._add(severity, node.lineno, f"{name}() — dangerous built-in", "code_execution")

        # Attribute calls: os.system(), subprocess.Popen()
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                module = node.func.value.id
                key = (module, attr_name)
                if key in _DANGEROUS_ATTRS:
                    severity, desc = _DANGEROUS_ATTRS[key]
                    self._add(severity, node.lineno, desc, "dangerous_call")

            # Check for open() on sensitive paths
            if attr_name == "open":
                self._check_open_args(node)

        # Check open() as direct call too
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            self._check_open_args(node)

        self.generic_visit(node)

    def _check_open_args(self, node: ast.Call) -> None:
        """Check if open() targets sensitive files."""
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _SENSITIVE_PATH_RE.search(arg.value):
                    self._add("high", node.lineno,
                              f"Access to sensitive path: {arg.value}",
                              "sensitive_path")

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            mod_name = alias.name.split(".")[0]
            if mod_name in _DANGEROUS_MODULES:
                severity = "critical" if mod_name in _CRITICAL_MODULES else "high"
                self._add(severity, node.lineno,
                          f"Import of dangerous module: {alias.name}",
                          "dangerous_import")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module:
            mod_name = node.module.split(".")[0]
            if mod_name in _DANGEROUS_MODULES:
                severity = "critical" if mod_name in _CRITICAL_MODULES else "high"
                self._add(severity, node.lineno,
                          f"Import from dangerous module: {node.module}",
                          "dangerous_import")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        """Check string literals for sensitive paths and URLs."""
        if isinstance(node.value, str) and len(node.value) > 5:
            if _SENSITIVE_PATH_RE.search(node.value):
                self._add("medium", node.lineno,
                           f"Reference to sensitive path: {node.value[:80]}",
                           "sensitive_path")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        """Detect access to dangerous dunder attributes."""
        if node.attr in _META_PATTERNS:
            severity, desc = _META_PATTERNS[node.attr]
            self._add(severity, node.lineno, f"{node.attr} — {desc}", "meta_abuse")
        if node.attr in _CODE_OBJECT_ATTRS:
            self._add("high", node.lineno,
                       f"Code object attribute access: {node.attr}",
                       "code_manipulation")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Detect suspicious function definitions."""
        if node.name in ("__reduce__", "__reduce_ex__"):
            self._add("high", node.lineno,
                       f"Custom {node.name}() — pickle exploit vector",
                       "deserialization")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # same check

    def visit_Global(self, node: ast.Global) -> None:  # noqa: N802
        """Flag global statement usage."""
        self._add("low", node.lineno,
                   f"global {', '.join(node.names)} — global state mutation",
                   "code_quality")
        self.generic_visit(node)


class SkillSecurityScanner:
    """Static analysis scanner for skill directories.

    Scans Python scripts via AST analysis and SKILL.md / shell scripts
    via regex patterns. 80+ security patterns across 15 categories.
    """

    def scan_skill(
        self,
        skill_dir: Path | str,
        skill_name: Optional[str] = None,
    ) -> ScanResult:
        """Scan a skill directory for security issues."""
        skill_dir = Path(skill_dir)
        if not skill_name:
            skill_name = skill_dir.name

        findings: list[Finding] = []
        files_scanned = 0

        # Scan Python files in scripts/
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            for py_file in scripts_dir.rglob("*.py"):
                files_scanned += 1
                try:
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                    rel_path = str(py_file.relative_to(skill_dir))
                    scanner = _ASTScanner(rel_path)
                    findings.extend(scanner.scan(source))
                    findings.extend(
                        self._scan_strings_for_exfil(source, rel_path)
                    )
                except Exception as exc:
                    logger.warning("Failed to scan %s: %s", py_file, exc)

        # Scan shell scripts
        for sh_file in skill_dir.rglob("*.sh"):
            files_scanned += 1
            try:
                source = sh_file.read_text(encoding="utf-8", errors="replace")
                rel_path = str(sh_file.relative_to(skill_dir))
                findings.extend(self._scan_shell(source, rel_path))
            except Exception as exc:
                logger.warning("Failed to scan %s: %s", sh_file, exc)

        # Scan SKILL.md for shell commands
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            files_scanned += 1
            try:
                source = skill_md.read_text(encoding="utf-8", errors="replace")
                findings.extend(self._scan_markdown(source, "SKILL.md"))
            except Exception as exc:
                logger.warning("Failed to scan SKILL.md: %s", exc)

        has_critical = any(f.severity == "critical" for f in findings)

        result = ScanResult(
            safe=not has_critical,
            skill_name=skill_name,
            findings=findings,
            files_scanned=files_scanned,
        )

        if findings:
            logger.warning(
                "Skill '%s' scan: %d finding(s) (%d critical)",
                skill_name, len(findings), result.critical_count,
            )

        return result

    def scan_content(
        self,
        content: str,
        skill_name: str,
        filename: str = "SKILL.md",
    ) -> ScanResult:
        """Scan raw SKILL.md content (before writing to disk)."""
        findings: list[Finding] = []
        findings.extend(self._scan_markdown(content, filename))

        has_critical = any(f.severity == "critical" for f in findings)
        return ScanResult(
            safe=not has_critical,
            skill_name=skill_name,
            findings=findings,
            files_scanned=1,
        )

    def scan_scripts_content(
        self,
        scripts: dict,
        skill_name: str,
        prefix: str = "scripts",
    ) -> ScanResult:
        """Scan scripts dict content before writing to disk."""
        findings: list[Finding] = []
        files_scanned = 0

        def _walk(tree: dict, path: str) -> None:
            nonlocal files_scanned
            for key, value in tree.items():
                full_path = f"{path}/{key}"
                if isinstance(value, dict):
                    _walk(value, full_path)
                elif isinstance(value, str):
                    files_scanned += 1
                    if key.endswith(".py"):
                        scanner = _ASTScanner(full_path)
                        findings.extend(scanner.scan(value))
                        findings.extend(
                            self._scan_strings_for_exfil(value, full_path)
                        )
                    elif key.endswith(".sh"):
                        findings.extend(self._scan_shell(value, full_path))

        _walk(scripts, prefix)
        has_critical = any(f.severity == "critical" for f in findings)
        return ScanResult(
            safe=not has_critical,
            skill_name=skill_name,
            findings=findings,
            files_scanned=files_scanned,
        )

    def _scan_strings_for_exfil(
        self, source: str, filepath: str
    ) -> list[Finding]:
        """Scan source for potential data exfiltration URLs."""
        findings: list[Finding] = []
        for pattern, severity, desc in _EXFIL_PATTERNS:
            for m in re.finditer(pattern, source):
                url = m.group()
                if any(d in url for d in _SAFE_DOMAINS):
                    continue
                line = source[:m.start()].count("\n") + 1
                findings.append(
                    Finding(
                        severity=severity,
                        category="exfiltration",
                        file=filepath,
                        line=line,
                        description=f"{desc}: {url[:80]}",
                    )
                )
        return findings

    def _scan_shell(self, source: str, filepath: str) -> list[Finding]:
        """Scan shell script content for dangerous patterns."""
        findings: list[Finding] = []
        for pattern, severity, desc, category in _SHELL_PATTERNS:
            for m in re.finditer(pattern, source):
                line = source[:m.start()].count("\n") + 1
                findings.append(
                    Finding(
                        severity=severity,
                        category=category,
                        file=filepath,
                        line=line,
                        description=desc,
                        code_snippet=m.group()[:120],
                    )
                )
        return findings

    async def llm_audit_skill(
        self,
        skill_dir: Path | str,
        llm_caller: object = None,
        skill_name: Optional[str] = None,
    ) -> ScanResult:
        """Secondary LLM-based security audit of a skill.

        Sends skill content to the current LLM for analysis.
        Best-effort — if LLM is unavailable, returns static scan only.

        Args:
            skill_dir: Path to the skill directory.
            llm_caller: Async callable(prompt) -> str. If None, falls back to static scan.
            skill_name: Override skill name.

        Returns:
            ScanResult combining static + LLM findings.
        """
        import json as _json

        # First run static scan
        static_result = self.scan_skill(skill_dir, skill_name)
        if llm_caller is None:
            return static_result

        skill_dir = Path(skill_dir)
        if not skill_name:
            skill_name = skill_dir.name

        # Collect skill content for LLM
        content_parts: list[str] = []
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            text = skill_md.read_text(encoding="utf-8", errors="replace")[:5000]
            content_parts.append(f"=== SKILL.md ===\n{text}")

        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            for py_file in list(scripts_dir.rglob("*.py"))[:10]:
                text = py_file.read_text(encoding="utf-8", errors="replace")[:3000]
                rel = py_file.relative_to(skill_dir)
                content_parts.append(f"=== {rel} ===\n{text}")
            for sh_file in list(scripts_dir.rglob("*.sh"))[:5]:
                text = sh_file.read_text(encoding="utf-8", errors="replace")[:3000]
                rel = sh_file.relative_to(skill_dir)
                content_parts.append(f"=== {rel} ===\n{text}")

        if not content_parts:
            return static_result

        prompt = (
            "You are a security auditor reviewing an AI agent skill/plugin. "
            "Analyze the following skill files for security issues. "
            "Look for: data exfiltration, command injection, privilege escalation, "
            "backdoors, obfuscated code, supply chain risks, sandbox escapes.\n\n"
            "Respond ONLY with a JSON array of findings. Each finding:\n"
            '{"severity":"critical|high|medium|low","description":"...","file":"...","line":0}\n\n'
            "If no issues found, respond with: []\n\n"
            + "\n\n".join(content_parts)
        )

        try:
            response = await llm_caller(prompt)
            # Parse LLM response — extract JSON array
            response = response.strip()
            # Try to find JSON array in response
            start = response.find("[")
            end = response.rfind("]")
            if start >= 0 and end > start:
                llm_findings_raw = _json.loads(response[start:end + 1])
                for item in llm_findings_raw:
                    if isinstance(item, dict) and "description" in item:
                        severity = item.get("severity", "medium")
                        if severity not in ("critical", "high", "medium", "low"):
                            severity = "medium"
                        static_result.findings.append(
                            Finding(
                                severity=severity,
                                category="llm_audit",
                                file=item.get("file", ""),
                                line=item.get("line", 0),
                                description=f"[LLM] {item['description']}",
                            )
                        )
                # Re-evaluate safety
                if any(f.severity == "critical" for f in static_result.findings):
                    static_result.safe = False
        except Exception as exc:
            logger.warning("LLM audit failed for '%s': %s", skill_name, exc)

        return static_result

    def _scan_markdown(self, source: str, filepath: str) -> list[Finding]:
        """Scan markdown for shell injection patterns in code blocks."""
        findings: list[Finding] = []
        for block_match in re.finditer(
            r"```(?:sh|bash|shell|zsh)?\n(.*?)```",
            source,
            re.DOTALL,
        ):
            block = block_match.group(1)
            block_start = source[:block_match.start()].count("\n") + 1
            for pattern, severity, desc, category in _SHELL_PATTERNS:
                for m in re.finditer(pattern, block):
                    line = block_start + block[:m.start()].count("\n")
                    findings.append(
                        Finding(
                            severity=severity,
                            category=category,
                            file=filepath,
                            line=line,
                            description=desc,
                            code_snippet=m.group()[:120],
                        )
                    )
        return findings
