#!/usr/bin/env python3
"""
Evaluation harness.

Runs the actual detection pipeline (same code path as redact.py) over
two ground-truth corpora and reports precision / recall / F1 per PII
type:

  1. ground_truth/general_information_sample.py
     -- 80 real lines from the uploaded prospectus's "General
        Information" chapter (hand-annotated), covering PERSON,
        COMPANY, EMAIL, PHONE, ADDRESS "in the wild."

  2. ground_truth/synthetic_sample.py
     -- synthetic sentences for SSN, CREDIT_CARD, IP_ADDRESS, and
        DATE_OF_BIRTH (types absent from the real prospectus), plus
        negative-control sentences (order numbers, financial years,
        registration numbers) that must NOT be flagged, to measure
        precision on the kind of numeric strings a naive regex would
        false-positive on.

Matching is per-line, per-label, case-insensitive substring matching
(so minor span-boundary differences don't count as a miss) -- see
`matches()` below.

Usage: python evaluate.py
"""

import spacy
from pii_redactor.redactor import Redactor

from ground_truth.general_information_sample import GROUND_TRUTH
from ground_truth.synthetic_sample import (
    SYNTHETIC_LINES, SYNTHETIC_GROUND_TRUTH, NEGATIVE_CONTROL_LINES,
)


def matches(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or a in b or b in a


def score(lines: list[str], ground_truth: list[tuple[int, str, str]], redactor: Redactor):
    """Returns per-label {tp, fp, fn} counts plus the raw event log."""
    counts = {}
    all_events = []

    gt_by_line = {}
    for line_no, label, text in ground_truth:
        gt_by_line.setdefault(line_no, []).append({"label": label, "text": text, "matched": False})

    for line_no, line in enumerate(lines, start=1):
        events = redactor.redact_text(line)[1]
        all_events.append((line_no, line, events))
        gt_items = gt_by_line.get(line_no, [])

        for ev in events:
            counts.setdefault(ev.label, {"tp": 0, "fp": 0, "fn": 0})
            hit = next((g for g in gt_items if not g["matched"] and g["label"] == ev.label
                        and matches(g["text"], ev.original)), None)
            if hit:
                hit["matched"] = True
                counts[ev.label]["tp"] += 1
            else:
                counts[ev.label]["fp"] += 1

        for g in gt_items:
            if not g["matched"]:
                counts.setdefault(g["label"], {"tp": 0, "fp": 0, "fn": 0})
                counts[g["label"]]["fn"] += 1

    return counts, all_events


def print_table(title, counts):
    print(f"\n{title}")
    print(f"{'Type':<15}{'TP':>5}{'FP':>5}{'FN':>5}{'Precision':>12}{'Recall':>10}{'F1':>8}")
    tot_tp = tot_fp = tot_fn = 0
    for label in sorted(counts):
        tp, fp, fn = counts[label]["tp"], counts[label]["fp"], counts[label]["fn"]
        tot_tp += tp; tot_fp += fp; tot_fn += fn
        p = tp / (tp + fp) if (tp + fp) else float("nan")
        r = tp / (tp + fn) if (tp + fn) else float("nan")
        f1 = 2 * p * r / (p + r) if (p + r) and p == p and r == r and (p + r) > 0 else float("nan")
        print(f"{label:<15}{tp:>5}{fp:>5}{fn:>5}{p*100:>11.1f}%{r*100:>9.1f}%{f1*100:>7.1f}%" if p == p and r == r else
              f"{label:<15}{tp:>5}{fp:>5}{fn:>5}{'--':>12}{'--':>10}{'--':>8}")
    p = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else float("nan")
    r = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else float("nan")
    f1 = 2 * p * r / (p + r) if (p + r) else float("nan")
    print("-" * 65)
    print(f"{'TOTAL':<15}{tot_tp:>5}{tot_fp:>5}{tot_fn:>5}{p*100:>11.1f}%{r*100:>9.1f}%{f1*100:>7.1f}%")
    return tot_tp, tot_fp, tot_fn


def main():
    nlp = spacy.load("en_core_web_sm")
    redactor = Redactor(nlp=nlp, seed=42)

    # --- 1. Real-document sample ---
    with open("eval_sample.txt", encoding="utf-8") as f:
        real_lines = f.read().splitlines()
    real_counts, real_events = score(real_lines, GROUND_TRUTH, redactor)
    r_tp, r_fp, r_fn = print_table("=== Real-document sample (General Information chapter) ===", real_counts)

    # False positives in detail (for the README / report discussion)
    print("\nFalse positives on the real-document sample:")
    for line_no, line, events in real_events:
        gt_labels_texts = [(g[1], g[2]) for g in GROUND_TRUTH if g[0] == line_no]
        for ev in events:
            if not any(ev.label == lbl and matches(txt, ev.original) for lbl, txt in gt_labels_texts):
                print(f"  line {line_no:3d} [{ev.label:10s}] {ev.original!r}")

    print("\nMissed ground-truth instances (false negatives) on the real-document sample:")
    for line_no, line, events in real_events:
        gt_items = [g for g in GROUND_TRUTH if g[0] == line_no]
        for _, label, gtext in gt_items:
            if not any(ev.label == label and matches(gtext, ev.original) for ev in events):
                print(f"  line {line_no:3d} [{label:10s}] {gtext!r}")

    # --- 2. Synthetic structured-PII sample + negative controls ---
    synth_lines = SYNTHETIC_LINES + NEGATIVE_CONTROL_LINES
    synth_counts, synth_events = score(synth_lines, SYNTHETIC_GROUND_TRUTH, redactor)
    s_tp, s_fp, s_fn = print_table(
        "\n=== Synthetic sample (SSN / credit card / IP / DOB) + negative controls ===",
        synth_counts,
    )
    print("\nAny detections on the 5 negative-control lines (should be none):")
    none_found = True
    for line_no, line, events in synth_events:
        if line_no > len(SYNTHETIC_LINES) and events:
            none_found = False
            for ev in events:
                print(f"  line {line_no:3d} [{ev.label:10s}] {ev.original!r}  <- FALSE POSITIVE")
    if none_found:
        print("  (none -- all 5 negative-control lines passed through clean)")

    # --- Combined summary ---
    tot_tp, tot_fp, tot_fn = r_tp + s_tp, r_fp + s_fp, r_fn + s_fn
    precision = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else float("nan")
    recall = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else float("nan")
    accuracy = tot_tp / (tot_tp + tot_fp + tot_fn) if (tot_tp + tot_fp + tot_fn) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else float("nan")
    print("\n=== Combined across both corpora ===")
    print(f"TP={tot_tp}  FP={tot_fp}  FN={tot_fn}")
    print(f"Precision: {precision*100:.1f}%")
    print(f"Recall:    {recall*100:.1f}%")
    print(f"F1:        {f1*100:.1f}%")
    print(f"'Accuracy' (TP / (TP+FP+FN), span-level -- see report note): {accuracy*100:.1f}%")


if __name__ == "__main__":
    main()
