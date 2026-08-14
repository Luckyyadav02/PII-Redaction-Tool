"""
Hand-annotated ground truth for eval_sample.txt (lines 469-548 of the
prospectus's "General Information" chapter, one dict per source line;
line numbers below are 1-indexed into eval_sample.txt itself).

Policy decisions made while annotating (documented again in README):
  * SEBI registration numbers, CINs, and RoC registration numbers are
    NOT treated as PII (they're regulatory/entity identifiers, not
    personal data) -- same bucket as order/ticket numbers.
  * "Registrar of Companies" (a government body) is NOT counted as a
    COMPANY -- same treatment as SEBI/RBI/BSE/NSE.
  * When a paragraph is anchored by both a PIN code (-> ADDRESS, whole
    paragraph) and a company name, the company mention is *subsumed*
    into the ADDRESS redaction by design (see redactor.py PRIORITY).
    Those company mentions are deliberately excluded from the COMPANY
    ground truth below, with a comment marking where this happens --
    the text is still fully redacted, just under a different label.
  * Three ADDRESS instances (marked NOTE below) use "Mumbai 400 051"
    style formatting with no dash before the PIN code. The detector's
    PIN anchor regex requires a dash, so these are known, expected
    false negatives -- included here so recall reflects that honestly.
"""

GROUND_TRUTH = [
    # line, type, text
    (2, "COMPANY", "KSH International Limited"),
    (4, "ADDRESS", "Pune – 410 501"),
    (7, "COMPANY", "KSH International Limited"),
    (9, "ADDRESS", "Pune 411 045 Maharashtra, India"),  # NOTE: no dash before PIN -> expected miss
    (16, "ADDRESS", "PCNTDA Green Building Block A 1st and 2nd floor Near Akurdi Railway Station Akurdi, Pune – 411 044 Maharashtra, India"),
    (21, "PERSON", "Sarthak Malvadkar"),
    (22, "ADDRESS", "Taluka Khed, District Pune – 410 501"),
    (24, "PHONE", "+ 91 20 45053237"),
    (25, "EMAIL", "Sarthak.malvadkar@kshinterantional.com"),
    (31, "COMPANY", "Nuvama Wealth Management Limited"),
    (33, "ADDRESS", "Bandra East, Mumbai – 400 051 Maharashtra, India"),
    (34, "PHONE", "+91 22 40094400"),
    (34, "EMAIL", "ksh.ipo@nuvama.com"),
    (35, "EMAIL", "customerservice.mb@nuvama.com"),
    (36, "PERSON", "Lokesh Shah"),
    (36, "PERSON", "Soumavo Sarkar"),
    (38, "ADDRESS", "ICICI Securities Limited ICICI Venture House Appasaheb Marathe Marg Prabhadevi, Mumbai – 400 025 Maharashtra, India"),
    # (38, COMPANY "ICICI Securities Limited") intentionally omitted -- subsumed into the ADDRESS above
    (39, "PHONE", "+91 22 6807 7100"),
    (39, "EMAIL", "ksh@icicisecurities.com"),
    (39, "EMAIL", "customercare@icicisecurities.com"),
    (40, "PERSON", "Kishan Rastogi"),
    (40, "PERSON", "Abhijit Diwan"),
    (45, "COMPANY", "Nuvama Wealth Management Limited"),
    (47, "ADDRESS", "Bandra Kurla Complex, Bandra East Mumbai 400 051"),  # NOTE: no dash before PIN -> expected miss
    (49, "PHONE", "+ 91 22 4009 4400"),
    (50, "EMAIL", "ksh.ipo@nuvama.com"),
    (50, "EMAIL", "prakash.boricha@nuvama.com"),
    (50, "EMAIL", "sheetal.parab@nuvama.com"),
    (52, "PERSON", "Prakash Boricha"),
    (54, "ADDRESS", "ICICI Securities Limited ICICI Venture House Appasaheb Marathe Marg Prabhadevi, Mumbai – 400 025 Maharashtra, India"),
    # (54, COMPANY "ICICI Securities Limited") intentionally omitted -- subsumed, see line 38
    (55, "PHONE", "+91 22 6807 7100"),
    (55, "EMAIL", "ksh@icicisecurities.com"),
    (56, "EMAIL", "customercare@icicisecurities.com"),
    (57, "PERSON", "Kishan Rastogi"),
    (57, "PERSON", "Abhijit Diwan"),
    (59, "COMPANY", "Trilegal"),
    (62, "ADDRESS", "Senapati Bapat Marg, Lower Parel (West) Mumbai – 400 013"),
    (64, "EMAIL", "ipo@trilegal.com"),
    (65, "PHONE", "+91 22 4079 1000"),
    (67, "COMPANY", "MUFG Intime India Private Limited"),
    (67, "COMPANY", "Link Intime India Private Limited"),
    (68, "ADDRESS", "1st Floor, L B S Marg, Vikhroli (West) Mumbai 400083, (Maharashtra), India Telephone: +91 81081 14949"),  # NOTE: no dash before PIN -> expected miss
    (68, "PHONE", "+91 81081 14949"),
    (69, "EMAIL", "kshinternational.ipo@in.mpms.mufg.com"),
    (70, "EMAIL", "kshinternational.ipo@in.mpms.mufg.com"),
    (71, "PERSON", "Shanti Gopalkrishnan"),
    (74, "COMPANY", "HDFC Bank Limited"),
    (75, "COMPANY", "HDFC Bank Limited"),
    (76, "ADDRESS", "Next to Kanjurmarg Railway Station, Kanjurmarg (East) Mumbai – 400042, Maharashtra, India"),
    (77, "PHONE", "+91 22 30752929"),
    (77, "PHONE", "+91 22 30752928"),
    (77, "PHONE", "+91 22 30752914"),
    (78, "EMAIL", "siddharth.jadhav@hdfcbank.com"),
    (78, "EMAIL", "sachin.gawade@hdfcbank.com"),
    (78, "EMAIL", "eric.bacha@hdfcbank.com"),
    (78, "EMAIL", "tushar.gavankar@hdfcbank.com"),
    (78, "EMAIL", "pravin.teli2@hdfcbank.com"),
    (79, "PERSON", "Eric Bacha"),
    (79, "PERSON", "Sachin Gawade"),
    (79, "PERSON", "Pravin Teli"),
    (79, "PERSON", "Siddharth Jadhav"),
    (79, "PERSON", "Tushar Gavankar"),
]
