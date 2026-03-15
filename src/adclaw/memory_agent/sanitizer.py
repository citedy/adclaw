# -*- coding: utf-8 -*-
"""Memory injection sanitizer — detects and blocks prompt injection in AOM content."""

from __future__ import annotations

import base64
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# --- Threat patterns ---

# Direct prompt injection attempts
_INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, threat_id, description)
    (
        r"(?i)ignore\s+(all\s+)?previous\s+(instructions|prompts|context)",
        "PROMPT_OVERRIDE",
        "Attempt to override previous instructions",
    ),
    (
        r"(?i)forget\s+(all\s+)?(your\s+)?(previous\s+)?(instructions|rules|context)",
        "PROMPT_OVERRIDE",
        "Attempt to erase previous instructions",
    ),
    (
        r"(?i)you\s+are\s+now\s+(a|an|the)\s+",
        "ROLE_HIJACK",
        "Attempt to reassign agent role",
    ),
    (
        r"(?i)new\s+system\s+prompt",
        "PROMPT_OVERRIDE",
        "Attempt to inject new system prompt",
    ),
    (
        r"(?i)act\s+as\s+(if\s+)?(you\s+)?(are|were)\s+",
        "ROLE_HIJACK",
        "Attempt to reassign agent role",
    ),
    (
        r"(?i)disregard\s+(all\s+)?(prior|previous|above)",
        "PROMPT_OVERRIDE",
        "Attempt to disregard prior context",
    ),
    (
        r"(?i)override\s+(system|safety|security)\s+(prompt|rules|guardrails)",
        "PROMPT_OVERRIDE",
        "Attempt to override safety rules",
    ),
    (
        r"(?i)jailbreak|DAN\s+mode|developer\s+mode|unrestricted\s+mode",
        "JAILBREAK",
        "Known jailbreak pattern",
    ),
    (
        r"(?i)pretend\s+(that\s+)?(you|there)\s+(are|is)\s+no\s+(rules|restrictions|limits)",
        "JAILBREAK",
        "Attempt to remove restrictions",
    ),
]

# Exfiltration via tool/command instructions
_EXFIL_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"(?i)curl\s+-X\s*POST\s",
        "EXFILTRATION",
        "curl POST exfiltration attempt",
    ),
    (
        r"(?i)curl\s+[^\n]*--data|curl\s+[^\n]*-d\s",
        "EXFILTRATION",
        "curl data exfiltration attempt",
    ),
    (
        r"(?i)wget\s+--post",
        "EXFILTRATION",
        "wget POST exfiltration attempt",
    ),
    (
        r"(?i)\bscp\s+",
        "EXFILTRATION",
        "scp file transfer attempt",
    ),
    (
        r"(?i)ssh-keygen|authorized_keys|id_rsa",
        "SSH_BACKDOOR",
        "SSH key/backdoor manipulation",
    ),
    (
        r"(?i)reverse\s*shell|bind\s*shell|nc\s+-[el]",
        "EXFILTRATION",
        "Reverse/bind shell attempt",
    ),
]

# SQL injection patterns
_SQL_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"(?i)(DROP|DELETE|TRUNCATE|ALTER)\s+(TABLE|DATABASE|INDEX)",
        "SQL_INJECTION",
        "Destructive SQL statement",
    ),
    (
        r"(?i)UNION\s+(ALL\s+)?SELECT",
        "SQL_INJECTION",
        "SQL UNION injection",
    ),
    (
        r"(?i);\s*(DROP|DELETE|INSERT|UPDATE|EXEC)\s",
        "SQL_INJECTION",
        "SQL injection chain",
    ),
]

# Path traversal
_TRAVERSAL_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"\.\./\.\./",
        "PATH_TRAVERSAL",
        "Directory traversal attempt",
    ),
    (
        r"(?i)/etc/(passwd|shadow|hosts)",
        "PATH_TRAVERSAL",
        "Access to sensitive system files",
    ),
    (
        r"(?i)~/.ssh/|~/.aws/|~/.kube/",
        "PATH_TRAVERSAL",
        "Access to sensitive user config",
    ),
]

# Context/memory exfiltration
_CONTEXT_EXFIL_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"(?i)reveal\s+(your|the)\s+(system\s+prompt|instructions|context|internal)",
        "CONTEXT_EXFIL",
        "Attempt to extract system prompt/context",
    ),
    (
        r"(?i)output\s+(your|the)\s+(entire|full|complete)\s+(prompt|instructions|memory)",
        "CONTEXT_EXFIL",
        "Attempt to dump full prompt/memory",
    ),
    (
        r"(?i)what\s+(are|is)\s+your\s+(system|initial|original)\s+(prompt|instructions)",
        "CONTEXT_EXFIL",
        "Attempt to read system prompt",
    ),
]

# LLM role/format markers that shouldn't appear in memory content
_ROLE_MARKER_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"<\s*system\s*>|<\s*/\s*system\s*>",
        "ROLE_MARKER",
        "System tag injection",
    ),
    (
        r"\[INST\]|\[/INST\]",
        "ROLE_MARKER",
        "Instruction tag injection (Llama format)",
    ),
    (
        r"<<\s*SYS\s*>>|<<\s*/\s*SYS\s*>>",
        "ROLE_MARKER",
        "System tag injection (Llama format)",
    ),
    (
        r"(?m)^(ASSISTANT|HUMAN|SYSTEM|USER)\s*:",
        "ROLE_MARKER",
        "Chat role marker injection",
    ),
    (
        r"<\|im_start\|>|<\|im_end\|>",
        "ROLE_MARKER",
        "ChatML tag injection",
    ),
    (
        r"<\|system\|>|<\|user\|>|<\|assistant\|>",
        "ROLE_MARKER",
        "Special token injection",
    ),
]

# Suspicious encoding / obfuscation
_OBFUSCATION_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"(?i)base64[:\s]+[A-Za-z0-9+/]{100,}={0,2}",
        "BASE64_PAYLOAD",
        "Suspicious base64-encoded payload",
    ),
    (
        r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){10,}",
        "HEX_PAYLOAD",
        "Hex-encoded payload",
    ),
    (
        r"\\u[0-9a-fA-F]{4}(\\u[0-9a-fA-F]{4}){10,}",
        "UNICODE_PAYLOAD",
        "Unicode-encoded payload",
    ),
]


@dataclass
class Threat:
    """A detected threat in content."""

    threat_id: str
    description: str
    matched_text: str = ""
    severity: str = "warning"  # "warning" or "critical"


@dataclass
class SanitizeResult:
    """Result of sanitization check."""

    safe: bool
    threats: List[Threat] = field(default_factory=list)
    cleaned_content: str = ""

    @property
    def threat_ids(self) -> list[str]:
        return [t.threat_id for t in self.threats]

    @property
    def has_critical(self) -> bool:
        return any(t.severity == "critical" for t in self.threats)


# Threat IDs that are always critical (block)
_CRITICAL_THREATS = {
    "PROMPT_OVERRIDE", "JAILBREAK", "ROLE_MARKER", "ROLE_HIJACK",
    "EXFILTRATION", "SSH_BACKDOOR", "SQL_INJECTION", "CONTEXT_EXFIL",
}


class MemorySanitizer:
    """Scans content for prompt injection before storing in AOM.

    Two modes:
    - ``mode="block"`` (default): critical threats prevent storage.
    - ``mode="warn"``: all threats are logged but content is stored
      with threat metadata.
    """

    def __init__(self, mode: str = "block") -> None:
        if mode not in ("block", "warn"):
            raise ValueError(f"mode must be 'block' or 'warn', got {mode!r}")
        self.mode = mode
        self._compiled_patterns: list[tuple[re.Pattern, str, str]] = []
        for pattern, tid, desc in (
            _INJECTION_PATTERNS + _ROLE_MARKER_PATTERNS + _OBFUSCATION_PATTERNS
            + _EXFIL_PATTERNS + _SQL_PATTERNS + _TRAVERSAL_PATTERNS
            + _CONTEXT_EXFIL_PATTERNS
        ):
            self._compiled_patterns.append((re.compile(pattern), tid, desc))

    def sanitize(self, content: str) -> SanitizeResult:
        """Check content for injection threats.

        Returns:
            SanitizeResult with ``safe=True`` if content is clean or
            only has warnings (in warn mode).
        """
        if not content:
            return SanitizeResult(safe=True, cleaned_content="")

        threats: list[Threat] = []

        # 1. Pattern matching
        for compiled, tid, desc in self._compiled_patterns:
            match = compiled.search(content)
            if match:
                severity = "critical" if tid in _CRITICAL_THREATS else "warning"
                threats.append(
                    Threat(
                        threat_id=tid,
                        description=desc,
                        matched_text=match.group()[:100],
                        severity=severity,
                    )
                )

        # 2. Unicode control character abuse
        control_count = sum(
            1
            for ch in content
            if unicodedata.category(ch).startswith("C")
            and ch not in ("\n", "\r", "\t")
        )
        if control_count > 10:
            threats.append(
                Threat(
                    threat_id="UNICODE_ABUSE",
                    description=f"Excessive Unicode control characters ({control_count})",
                    severity="warning",
                )
            )

        # 3. Hidden base64 detection (standalone, not in code blocks)
        for m in re.finditer(r"(?<!\w)[A-Za-z0-9+/]{100,}={0,2}(?!\w)", content):
            candidate = m.group()
            try:
                decoded = base64.b64decode(candidate, validate=True)
                if decoded and len(decoded) > 50:
                    threats.append(
                        Threat(
                            threat_id="HIDDEN_BASE64",
                            description="Decoded base64 payload found",
                            matched_text=candidate[:60] + "...",
                            severity="warning",
                        )
                    )
            except Exception:
                pass

        # Build result
        has_critical = any(t.severity == "critical" for t in threats)

        if self.mode == "block" and has_critical:
            safe = False
        else:
            safe = True

        if threats:
            logger.warning(
                "Memory sanitizer found %d threat(s): %s",
                len(threats),
                ", ".join(t.threat_id for t in threats),
            )

        return SanitizeResult(
            safe=safe,
            threats=threats,
            cleaned_content=content if safe else "",
        )
