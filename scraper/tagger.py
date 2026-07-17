from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from scraper.normalizer import normalize_for_match
from scraper.schemas import SpeakerProfile


@dataclass(frozen=True)
class TagEvidence:
    tag_id: str
    label: str
    source_field: str
    evidence: str
    confidence: float = 1.0


class RuleTagger:
    def __init__(self, rules_path: Path = Path("config/tag_rules.yaml")) -> None:
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def tag_profile(self, profile: SpeakerProfile) -> list[TagEvidence]:
        fields: list[tuple[str, str]] = []
        if profile.biography:
            fields.append(("biography", profile.biography))
        for position in profile.positions:
            fields.append(("position_title", position.title))
            if position.organization_name:
                fields.append(("organization_name", position.organization_name))
        for event in profile.events:
            fields.append(("event_name", event.name))

        evidence: list[TagEvidence] = []
        seen: set[tuple[str, str, str]] = set()
        for tag_id, rule in self.rules.items():
            label = str(rule.get("label", tag_id))
            keywords = [normalize_for_match(item) for item in rule.get("keywords", [])]
            for field_name, value in fields:
                normalized_value = normalize_for_match(value)
                if any(keyword and keyword in normalized_value for keyword in keywords):
                    key = (tag_id, field_name, value)
                    if key not in seen:
                        evidence.append(TagEvidence(tag_id, label, field_name, value))
                        seen.add(key)
        return evidence

    def _load_rules(self) -> dict:
        if not self.rules_path.exists():
            return {}
        with self.rules_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return data if isinstance(data, dict) else {}

