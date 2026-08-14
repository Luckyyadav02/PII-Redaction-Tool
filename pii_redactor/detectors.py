"""
detectors.py
============
One function per PII type. Every detector has the same signature:

    detect_X(text: str, nlp=None) -> list[Span]

and returns a list of `Span(start, end, label, text)` -- character
offsets into `text`, half-open like Python slicing (text[start:end]).

To add a new PII type:
    1. Write a `detect_<type>(text, nlp=None) -> list[Span]` function.
    2. Add it to the `DETECTORS` dict at the bottom of this file with
       a unique label string.
That's it -- redactor.py and the CLI pick it up automatically.
"""

from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str
    text: str


# ---------------------------------------------------------------------
# Regex-based detectors (structured PII -- high precision/recall by design)
# ---------------------------------------------------------------------

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Indian mobile/landline formats seen in filings: "+91 98765 43210",
# "+ 91 20 4505 3237", "022-68052182". Requires an explicit country
# code or STD-code-with-dash so we don't swallow CINs, financial years
# ("2024-2025"), or ticket/reference numbers.
PHONE_RE = re.compile(
    r"\+\s?91[-\s]?(?:\d[\s-]?){9}\d"      # +91 followed by 10 digits
    r"|\b0\d{2,4}-\d{6,8}\b"               # STD code - local number
)

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

IP_ADDRESS_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)

# 13-19 digits, optionally grouped by spaces/dashes in blocks of 4.
_CC_CANDIDATE_RE = re.compile(
    r"\b(?:\d[ -]?){13,19}\b"
)

DOB_CONTEXT_RE = re.compile(
    r"(?:date of birth|dob|born)\s*(?:is|was|on)?\s*[:\-]?\s*"
    r"(\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}|"        # YYYY-MM-DD
    r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|"        # DD/MM/YYYY or similar
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_email(text: str, nlp=None) -> list[Span]:
    return [Span(m.start(), m.end(), "EMAIL", m.group()) for m in EMAIL_RE.finditer(text)]


def detect_phone(text: str, nlp=None) -> list[Span]:
    return [Span(m.start(), m.end(), "PHONE", m.group()) for m in PHONE_RE.finditer(text)]


def detect_ssn(text: str, nlp=None) -> list[Span]:
    return [Span(m.start(), m.end(), "SSN", m.group()) for m in SSN_RE.finditer(text)]


def detect_ip_address(text: str, nlp=None) -> list[Span]:
    return [Span(m.start(), m.end(), "IP_ADDRESS", m.group()) for m in IP_ADDRESS_RE.finditer(text)]


def detect_credit_card(text: str, nlp=None) -> list[Span]:
    """Digit runs of 13-19, Luhn-validated to cut false positives on
    reference numbers, PIN codes glued together, CINs, etc."""
    spans = []
    for m in _CC_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            spans.append(Span(m.start(), m.end(), "CREDIT_CARD", m.group()))
    return spans


def detect_date_of_birth(text: str, nlp=None) -> list[Span]:
    spans = []
    for m in DOB_CONTEXT_RE.finditer(text):
        spans.append(Span(m.start(1), m.end(1), "DATE_OF_BIRTH", m.group(1)))
    return spans


# ---------------------------------------------------------------------
# Regex-based address detector
# ---------------------------------------------------------------------
# This document keeps each address in its own table cell / paragraph
# (see README), so instead of trying to parse street-grammar, we anchor
# on an Indian PIN code following a dash, then treat the *whole*
# paragraph as the ADDRESS span if it also contains an address-ish
# keyword. That trades some precision for much better recall/robustness
# on a document this structurally messy.

_PIN_ANCHOR_RE = re.compile(r"[–-]\s*\d{3}\s?\d{3}\b")
_ADDRESS_KEYWORDS_RE = re.compile(
    r"\b(?:Maharashtra|Road|Rd\.|Street|Nagar|Village|Taluka|Tower|Floor|"
    r"Building|Society|Colony|Estate|Industrial Area|Compound|Lane|"
    r"Marg|Chowk|District|Pune|Mumbai|Delhi|Bengaluru|Chennai|Kolkata|"
    r"Hyderabad|Ahmedabad)\b",
    re.IGNORECASE,
)


def detect_address(text: str, nlp=None) -> list[Span]:
    if _PIN_ANCHOR_RE.search(text) and _ADDRESS_KEYWORDS_RE.search(text):
        stripped = text.strip()
        if stripped:
            start = text.index(stripped)
            return [Span(start, start + len(stripped), "ADDRESS", stripped)]
    return []


# ---------------------------------------------------------------------
# NER-based detectors (PERSON, COMPANY) -- need a loaded spaCy pipeline
# ---------------------------------------------------------------------

# Legal defined-terms / generic nouns spaCy's small model regularly
# mis-tags as PERSON or ORG in prospectus boilerplate. Extend this list
# as you spot new false positives -- it is the single biggest precision
# lever for the NER detectors.
PERSON_STOPLIST = {
    "the company", "our company", "the board", "the promoters",
    "the promoter", "the issuer", "the offer", "the equity shares",
    "the selling shareholders", "the audit committee", "compliance officer",
    "bid", "bidder", "bidders", "allotment", "bid amount",
}

COMPANY_STOPLIST = {
    "sebi", "rbi", "bse", "nse", "roc", "cdsl", "nsdl", "mca", "gst",
    "sebi icdr regulations", "companies act", "sebi listing regulations",
    "the stock exchanges", "sme exchange", "registrar", "offer", "syndicate",
    "cin", "fig", "allotted equity shares", "anchor investors",
    "registered brokers", "asba bidders", "g block", "1st floor",
    "registered office", "corporate office", "board of directors",
    "maharashtra, india", "embassy",
}

# Legal/IPO boilerplate that spaCy's small model (trained on general news
# text) regularly mis-tags as PERSON/ORG because it's Title-Cased as a
# "defined term" in Indian prospectuses. Extend this as new false
# positives are spotted -- it's the main precision lever for NER output,
# used *in addition* to the structural filters below (which catch the
# bulk of the problem: anything containing a digit, starting with an
# article, or built mostly from short all-caps acronyms).
NER_JARGON_STOPLIST = {
    "bid cum application form", "the bid cum application form",
    "anchor investor application form", "the anchor investor application form",
    "the upi mechanism", "upi bidders", "first bidder", "dp id", "client id",
    "designated intermediary", "designated intermediaries",
}

COMPANY_SUFFIX_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z&.]*\s){1,6}"
    r"(?:Private\s+Limited|Pvt\.?\s*Ltd\.?|Limited|Ltd\.?|LLP|"
    r"Inc\.?|Corp(?:oration)?\.?)\b"
)

_ARTICLE_START_RE = re.compile(r"^(?:the|a|an|our|its|this|that|any|all|such)\s", re.IGNORECASE)


def _looks_like_real_entity(candidate: str, max_words: int) -> bool:
    """Structural filters shared by PERSON/COMPANY NER post-processing.
    Kills the large majority of legal-boilerplate false positives
    without hand-listing every offending phrase:
      - contains a digit (CINs, registration numbers, floor/unit numbers)
      - starts with an article/determiner ("the Bid cum Application Form")
      - more than `max_words` tokens (NER span ran on past the entity)
      - built only from short ALL-CAPS acronym tokens (PAN, UPI, ASBA...)
    """
    candidate = candidate.strip()
    if len(candidate) < 3:
        return False
    if any(ch.isdigit() for ch in candidate):
        return False
    if _ARTICLE_START_RE.match(candidate):
        return False
    lowered = candidate.lower()
    if "bidder" in lowered or "telephone" in lowered or "email" in lowered:
        return False
    words = candidate.split()
    if len(words) > max_words:
        return False
    if all(w.isupper() and len(w) <= 5 for w in words):
        return False
    if candidate.lower() in NER_JARGON_STOPLIST:
        return False
    return True


def detect_person(text: str, nlp=None) -> list[Span]:
    if nlp is None:
        return []
    spans = []
    for ent in nlp(text).ents:
        if ent.label_ != "PERSON":
            continue
        candidate = ent.text.strip()
        if candidate.lower() in PERSON_STOPLIST:
            continue
        if not _looks_like_real_entity(candidate, max_words=5):
            continue
        spans.append(Span(ent.start_char, ent.end_char, "PERSON", ent.text))
    return spans


def detect_company(text: str, nlp=None) -> list[Span]:
    spans = []
    seen_ranges = []

    for m in COMPANY_SUFFIX_RE.finditer(text):
        candidate = m.group().strip()
        if candidate.lower() in COMPANY_STOPLIST:
            continue
        start = m.start() + (len(m.group()) - len(m.group().lstrip()))
        end = m.end()
        spans.append(Span(start, end, "COMPANY", text[start:end]))
        seen_ranges.append((start, end))

    if nlp is not None:
        for ent in nlp(text).ents:
            if ent.label_ != "ORG":
                continue
            candidate = ent.text.strip()
            if candidate.lower() in COMPANY_STOPLIST:
                continue
            if not _looks_like_real_entity(candidate, max_words=8):
                continue
            # skip if it's already covered by a suffix-regex span
            if any(s <= ent.start_char and ent.end_char <= e for s, e in seen_ranges):
                continue
            spans.append(Span(ent.start_char, ent.end_char, "COMPANY", ent.text))

    return spans


# ---------------------------------------------------------------------
# Registry -- add new detectors here and nowhere else
# ---------------------------------------------------------------------

DETECTORS = {
    "EMAIL": detect_email,
    "PHONE": detect_phone,
    "SSN": detect_ssn,
    "CREDIT_CARD": detect_credit_card,
    "IP_ADDRESS": detect_ip_address,
    "DATE_OF_BIRTH": detect_date_of_birth,
    "ADDRESS": detect_address,
    "PERSON": detect_person,
    "COMPANY": detect_company,
}
