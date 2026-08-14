"""
redactor.py
===========
Orchestrates the detectors in detectors.py:
  1. run every registered detector over a paragraph of text
  2. resolve overlapping spans
  3. replace each span with a *consistent* fake value (same original
     value -> same fake value everywhere in the document)

This module has no docx-specific code, so it's independently testable
and reusable for other formats (plain text, PDF-extracted text, ...).
"""

from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from faker import Faker

from .detectors import DETECTORS, Span

# Lower number = higher priority when spans overlap. Structured,
# high-precision detectors win over the fuzzier NER-based ones; ADDRESS
# (which typically spans a whole paragraph) is resolved before the
# entity-level detectors so it doesn't get chopped up by a PERSON/COMPANY
# match inside it.
PRIORITY = {
    "EMAIL": 0, "PHONE": 0, "SSN": 0, "CREDIT_CARD": 0, "IP_ADDRESS": 0,
    "DATE_OF_BIRTH": 0,
    "ADDRESS": 1,
    "COMPANY": 2,
    "PERSON": 3,
}


@dataclass
class RedactionEvent:
    label: str
    original: str
    fake: str


def resolve_overlaps(spans: list[Span]) -> list[Span]:
    """Greedy interval selection: highest priority (then longest) spans
    win; anything overlapping an already-accepted span is dropped."""
    ordered = sorted(spans, key=lambda s: (PRIORITY.get(s.label, 9), -(s.end - s.start)))
    accepted: list[Span] = []
    for span in ordered:
        if any(not (span.end <= a.start or span.start >= a.end) for a in accepted):
            continue
        accepted.append(span)
    return sorted(accepted, key=lambda s: s.start)


class Redactor:
    def __init__(self, nlp=None, seed: int = 42):
        self.nlp = nlp
        self.faker = Faker()
        self.faker.seed_instance(seed)
        self._cache: dict[tuple[str, str], str] = {}
        self.counts: dict[str, int] = defaultdict(int)

    # -- fake value generation, with per-original-value caching --------

    def _generate_fake(self, label: str, original: str) -> str:
        if label == "EMAIL":
            return self.faker.email()
        if label == "PHONE":
            digits = self.faker.numerify("##########")
            return f"+91 {digits[:5]} {digits[5:]}"
        if label == "SSN":
            return self.faker.ssn()
        if label == "CREDIT_CARD":
            return self.faker.credit_card_number()
        if label == "IP_ADDRESS":
            return self.faker.ipv4_public()
        if label == "DATE_OF_BIRTH":
            return self.faker.date_of_birth(minimum_age=25, maximum_age=70).strftime("%d/%m/%Y")
        if label == "PERSON":
            return self.faker.name()
        if label == "COMPANY":
            return self.faker.company()
        if label == "ADDRESS":
            return self.faker.address().replace("\n", ", ")
        return "[REDACTED]"

    def get_fake(self, label: str, original: str) -> str:
        key = (label, original.strip().lower())
        if key not in self._cache:
            self._cache[key] = self._generate_fake(label, original)
        return self._cache[key]

    # -- main entry point -----------------------------------------------

    def detect(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for detector in DETECTORS.values():
            spans.extend(detector(text, self.nlp))
        return resolve_overlaps(spans)

    def redact_text(self, text: str) -> tuple[str, list[RedactionEvent]]:
        """Returns (redacted_text, events). Replacement is done
        right-to-left so earlier character offsets stay valid."""
        spans = self.detect(text)
        events: list[RedactionEvent] = []
        result = text
        for span in sorted(spans, key=lambda s: s.start, reverse=True):
            fake = self.get_fake(span.label, span.text)
            result = result[: span.start] + fake + result[span.end :]
            events.append(RedactionEvent(span.label, span.text, fake))
            self.counts[span.label] += 1
        events.reverse()
        return result, events
