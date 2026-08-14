# PII Redaction Tool

Redacts PII from a `.docx` file and replaces every instance with a
consistent fake value (same original -> same fake, everywhere in the
document), so the document stays internally coherent after redaction.

## Usage

```bash
pip install python-docx faker spacy
python -m spacy download en_core_web_sm

python redact.py Red_Herring_Prospectus.docx redacted_output.docx --log audit_log.csv
```

`--log` is optional; if given, writes a CSV audit trail of every
redaction (`label, original, fake_replacement`).

## Approach: hybrid regex + spaCy NER

| PII type | Detector |
|---|---|
| Email | Regex |
| Phone | Regex (Indian mobile/landline formats: `+91 XXXXX XXXXX`, STD-code-dash-number) |
| SSN | Regex (`XXX-XX-XXXX`) |
| Credit card | Regex candidate (13-19 digits) + **Luhn check** |
| IP address | Regex (IPv4) |
| Date of birth | Regex, but only when near context words ("date of birth", "DOB", "born") — a bare date isn't PII by itself |
| Address | PIN-code anchor (Indian 6-digit PIN preceded by a dash) + an address keyword (state/city/"Road"/"Village"/etc.) in the same paragraph -> the **whole paragraph** is redacted |
| Person | spaCy `en_core_web_sm` NER (`PERSON` label) |
| Company | Regex for legal suffixes (Ltd/Limited/LLP/Pvt Ltd/Inc/Corp) **plus** spaCy NER (`ORG` label) for unsuffixed names (e.g. "Trilegal") |

Structured types (email/phone/SSN/credit card/IP/DOB) are regex-based
because they have a fixed, learnable shape — this gets clean, near-100%
precision and recall. Names and company names don't have a fixed shape,
so those need statistical NER, which is inherently noisier — see
Known Limitations below.

**Why whole-paragraph address redaction:** this document keeps each
address in its own table cell or paragraph rather than one contiguous
sentence, so word-level street-address parsing would be fragile. A
PIN-code anchor is a much more reliable signal, and since it typically
appears in an address-only paragraph, replacing the whole paragraph is
both simpler and safer than trying to carve out just the "address part."

### Overlap resolution & consistent fake values

All detectors run over every paragraph; when spans overlap, priority
goes structured-PII > address > company > person (a whole-paragraph
address redaction "wins" over a company name embedded in it, since
that company mention would be removed anyway). Every unique original
value is mapped to one fake value on first sight and reused everywhere
after (via `Faker`, seeded for reproducibility), so "Sarthak Malvadkar"
becomes the same fake name whether it's mentioned once or fifty times.

### Explicit policy calls

- **SEBI/RBI/BSE/NSE/RoC/CDSL/NSDL/MCA** and similar public regulatory
  bodies are **not** treated as "company names" — they're generic
  regulators, not the issuer's or a person's identifying information,
  same logic as not redacting "SEC" in a US filing.
- **CINs, SEBI registration numbers, order/ticket/registration
  numbers** are **not** redacted — they're reference identifiers, not
  personal or company-identifying data, and were explicitly excluded
  per the assignment's guidance on "Order"/"Ticket" numbers.
- **Company names ARE redacted**, including the issuer itself
  (KSH International Limited), per the assignment's literal "at
  minimum: ... Company names" requirement. This does reduce
  readability of the redacted document but maximizes anonymization.
- Website URLs (e.g. `www.nuvama.com`) are **not** redacted — not in
  the required PII list, and a domain isn't personally identifying on
  its own.

## Known limitations / false positives & negatives

1. **PERSON precision is the weakest detector (~60-88% depending on
   sample).** spaCy's small English model is trained on general news
   text, not Indian prospectuses, and regularly mistags Indian place
   names as people — e.g. "Baner", "Vikhroli", "Bandra Kurla Complex"
   were flagged as `PERSON`. A larger spaCy model (`en_core_web_trf`)
   or a gazetteer of Indian place names would reduce this
   meaningfully, at the cost of speed/dependencies.
2. **Legal-document "defined terms."** Prospectuses Title-Case terms
   like "the Bid cum Application Form" or "Anchor Investor Application
   Form", which spaCy's capitalization-sensitive NER tends to treat as
   named entities. We mitigate with a structural filter (reject any
   NER candidate containing a digit, starting with an article, or
   built entirely from short ALL-CAPS acronyms like "PAN"/"UPI") plus
   a small hand-built jargon stoplist — this cut false positives by
   roughly 2/3 in testing, but is inherently incomplete for a new
   document with different boilerplate.
3. **Address PIN-anchor requires a dash.** "Pune – 410 501" is caught;
   "Pune 411 045" (space, no dash) is not. This was a deliberate
   precision/recall tradeoff — dropping the dash requirement caught a
   few more addresses but also matched plain financial figures next to
   place names as false positives.
4. **Slash-separated name lists** ("Eric Bacha/ Sachin Gawade/ Pravin
   Teli") are sometimes only partially split by spaCy into separate
   `PERSON` entities, occasionally merging two names or leaving a
   trailing slash on one.
5. **Paragraph-level formatting loss.** When a paragraph is redacted,
   the tool keeps the *first run's* formatting for the whole rewritten
   text and blanks the other runs, so mixed-formatting paragraphs
   (e.g. a bolded name inside a plain sentence) lose that mid-paragraph
   styling. Preserving run-level formatting exactly would require
   diffing old/new text token-by-token against original run
   boundaries — judged not worth the complexity here.
6. **Merged table cells.** Word represents a horizontally/vertically
   merged cell as several `Cell` objects wrapping the *same*
   underlying paragraph. Without de-duplicating by the XML element
   (which this tool does), a merged cell gets processed twice — the
   second pass would find spaCy entities inside the *already-fake*
   text and corrupt it further. Caught and fixed during development;
   documented here since it's a genuinely non-obvious python-docx trap.

## Extending to a new PII type

1. Write `detect_<type>(text, nlp=None) -> list[Span]` in `detectors.py`.
2. Add it to the `DETECTORS` dict at the bottom of that file.
3. Add a fake-value case for the new label in `Redactor._generate_fake`
   in `redactor.py`.
4. (Optional) Add it to `PRIORITY` in `redactor.py` if it should win or
   lose specific overlap conflicts with other types.

No other file needs to change — `docx_io.py`, `redact.py`, and
`evaluate.py` all work off the `DETECTORS` registry automatically.

## Files

```
redact.py                  CLI entry point
evaluate.py                Evaluation harness (precision/recall/F1)
pii_redactor/
  detectors.py              Detection logic, one function per PII type
  redactor.py                Overlap resolution + fake-value generation
  docx_io.py                  docx-specific paragraph/table walking & rewriting
ground_truth/
  general_information_sample.py   Hand-annotated real-document sample
  synthetic_sample.py             Synthetic SSN/credit-card/IP/DOB + negative controls
evaluation_report.md       Full metrics writeup
redacted_output.docx       Redacted copy of the uploaded prospectus
audit_log.csv              Every redaction applied (label, original, fake)
```
