from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionRule:
    field_name: str
    pattern: str
    flags: int = re.IGNORECASE


class RuleExtractor:
    def __init__(self, rules: list[ExtractionRule]) -> None:
        self.rules = rules

    def extract(self, text: str) -> dict[str, str]:
        results: dict[str, str] = {}
        for rule in self.rules:
            match = re.search(rule.pattern, text, flags=rule.flags)
            if not match:
                continue
            value = match.group(1) if match.groups() else match.group(0)
            results[rule.field_name] = value.strip()
        return results
