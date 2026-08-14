# Evaluation Report

## Methodology

Two ground-truth corpora, scored by the same harness (`evaluate.py`),
which runs the actual detection pipeline (not a separate mock) line by
line and matches predicted redaction events against hand-annotated
ground truth (case-insensitive substring match, so minor span-boundary
differences don't count as a miss).

**1. Real-document sample** (`ground_truth/general_information_sample.py`)
80 consecutive lines from the uploaded prospectus's "General
Information" chapter — the densest PII section (registered/corporate
office details, book-running lead managers, registrar, escrow bank,
all with named contact persons, emails, phones, and addresses).
Hand-annotated by manually reading every line, deciding what should
count as PII under the policy in the README, and recording the exact
expected text and label. This is real, in-the-wild data, so it tests
detector behavior on actual document noise (merged cells, split
addresses, legal boilerplate).

**2. Synthetic sample** (`ground_truth/synthetic_sample.py`)
The uploaded prospectus contains no SSNs, credit cards, IP addresses,
or dates of birth (expected — it's a securities filing, not a form
with that kind of data), so those detectors couldn't be evaluated
against real instances. Ten synthetic sentences were written, one to
three PII instances each, covering typical real-world formatting
(dashed/spaced SSNs, dashed/spaced credit cards including a
Luhn-invalid one, IPv4 in log-style text, DOB written three different
ways). Five additional **negative-control** sentences (order/ticket
numbers, financial-year ranges, CINs, SEBI registration numbers, a
version-looking number) were mixed in specifically to test precision
against the exact kind of numeric strings the assignment calls out
("Order"/"Ticket" numbers) — these are structured entirely to try to
fool a naive digit-regex.

### Why "accuracy" is reported but de-emphasized

This is an extraction/span-detection task, not a classification task
with a fixed, enumerable set of "negative" instances — there's no
natural denominator for "correctly predicted absence of PII" at the
character level, so an accuracy number is included below for
completeness but precision/recall/F1 (computed per PII type) are the
metrics that actually mean something here, and are what's discussed
throughout.

## Results

### Real-document sample (General Information chapter, 80 lines)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| ADDRESS | 8 | 0 | 3 | 100.0% | 72.7% | 84.2% |
| COMPANY | 8 | 2 | 1 | 80.0% | 88.9% | 84.2% |
| EMAIL | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| PERSON | 9 | 6 | 5 | 60.0% | 64.3% | 62.1% |
| PHONE | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| **TOTAL** | **53** | **8** | **9** | **86.9%** | **85.5%** | **86.2%** |

### Synthetic sample (SSN / credit card / IP / DOB, 10 lines + 5 negative controls)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| SSN | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| CREDIT_CARD | 3 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| IP_ADDRESS | 3 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| DATE_OF_BIRTH | 3 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| COMPANY (incidental) | 0 | 2 | 0 | — | — | — |
| **TOTAL** | **11** | **2** | **0** | **84.6%** | **100.0%** | **91.7%** |

All 5 negative-control sentences (order numbers, financial-year
ranges, CINs, SEBI registration numbers) produced **zero** false
redactions — the structured detectors correctly ignored every one.

The 2 COMPANY false positives in this sample weren't from the
negative controls — they were spaCy tagging "Visa" and "Mastercard"
as `ORG` inside the credit-card test sentences. Arguably these *are*
legitimate brand/company names (not really false positives in the
everyday sense), just outside the scope this synthetic set was
designed to measure — noted rather than "fixed" by suppressing them.

### Combined

| Metric | Value |
|---|---|
| True Positives | 64 |
| False Positives | 10 |
| False Negatives | 9 |
| **Precision** | **86.5%** |
| **Recall** | **87.7%** |
| **F1** | **87.1%** |
| "Accuracy" (TP / (TP+FP+FN), span-level) | 77.1% |

## Discussion

**Structured types (EMAIL, PHONE, SSN, CREDIT_CARD, IP_ADDRESS,
DATE_OF_BIRTH) all hit 100% precision and recall** on their respective
test sets — expected, since they have a fixed, regex-learnable shape,
and the negative controls confirm the regexes don't over-trigger on
similarly-shaped non-PII numbers (order numbers, CINs, financial
years).

**ADDRESS: 100% precision, 72.7% recall.** Every address the tool
flagged was really an address (no false positives). The 3 misses all
share one root cause: the PIN code wasn't preceded by a dash
("Pune 411 045" instead of "Pune – 410 501"), which the detector
requires as an anchor to avoid matching arbitrary 6-digit numbers next
to place names. This is a deliberate, documented precision/recall
tradeoff (see README).

**COMPANY: 80% precision, 88.9% recall.** The main remaining false
positive here ("Montreal Business Centre Off Pallod Farms") is a
business-park name that structurally looks like a company. The one
miss ("Trilegal") has no legal suffix, so it relies entirely on
spaCy's ORG tagging, which didn't fire for it in this context.

**PERSON: 60% precision, 64.3% recall — the weakest detector.** All 6
false positives are Indian place names ("Baner", "Vikhroli", "Bandra
Kurla Complex", "Village Birdewadi", "Taluka-Khed") that spaCy's small
English model, trained on general (largely Western) news text,
mis-tagged as people. The 5 misses are mostly names inside
slash-separated lists ("Sachin Gawade/ Pravin Teli/") that spaCy only
partially split into separate entities, plus one name spaCy missed
entirely ("Lokesh Shah"). This is the single biggest quality gap in
the tool and the most worthwhile place to invest further — either a
larger transformer-based spaCy model (`en_core_web_trf`), a
fine-tuned/Indian-names-aware NER model, or a curated Indian
place-name gazetteer used as a PERSON-candidate suppressor.

## How to reproduce

```bash
python evaluate.py
```

Runs both corpora through the live pipeline and prints the tables
above, plus a full itemized list of every false positive and false
negative for manual review.
