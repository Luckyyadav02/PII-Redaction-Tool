#!/usr/bin/env python3
"""
CLI for the PII redaction tool.

Usage:
    python redact.py INPUT.docx OUTPUT.docx [--log events.csv] [--seed 42]

Reads a .docx file, detects PII (names, emails, phones, company names,
addresses, SSNs, credit cards, dates of birth, IP addresses), replaces
each instance with a consistent fake value, and writes a redacted copy.
See README.md for the detection approach and known limitations.
"""

import argparse
import sys

import spacy

from pii_redactor.redactor import Redactor
from pii_redactor.docx_io import redact_docx


def main():
    parser = argparse.ArgumentParser(description="Redact PII from a .docx file.")
    parser.add_argument("input", help="Path to the source .docx file")
    parser.add_argument("output", help="Path to write the redacted .docx file")
    parser.add_argument("--log", default=None, help="Optional path to write a CSV audit log")
    parser.add_argument("--seed", type=int, default=42, help="Faker random seed (for reproducible fake values)")
    args = parser.parse_args()

    print(f"Loading spaCy model...", file=sys.stderr)
    nlp = spacy.load("en_core_web_sm")

    redactor = Redactor(nlp=nlp, seed=args.seed)

    print(f"Redacting {args.input} -> {args.output}", file=sys.stderr)
    events, counts = redact_docx(args.input, args.output, redactor, log_path=args.log)

    print(f"\nDone. {len(events)} redactions applied:", file=sys.stderr)
    for label, count in sorted(counts.items()):
        print(f"  {label:15s} {count}", file=sys.stderr)
    if args.log:
        print(f"\nAudit log written to {args.log}", file=sys.stderr)


if __name__ == "__main__":
    main()
