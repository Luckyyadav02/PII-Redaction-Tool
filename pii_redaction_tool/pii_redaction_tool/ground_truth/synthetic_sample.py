"""
Synthetic sentences for PII types the real prospectus doesn't contain
(SSN, credit card, IP address, date of birth) plus a batch of
"should NOT be flagged" negative controls -- ticket/order/reference
numbers, version numbers, financial-year ranges, and other digit
strings that a careless regex would false-positive on. These are
scored the same way as the real-document sample.
"""

SYNTHETIC_LINES = [
    "Please verify the applicant's SSN, 245-11-8734, before processing the refund.",
    "For identity verification we have his SSN 002-14-9834 on file.",
    "The customer's Visa card number is 4539 1488 0343 6467, expiring next year.",
    "Card on file: 5555555555554444 (Mastercard test number).",
    "Payment was declined on card 4111-1111-1111-1111 due to insufficient funds.",
    "The intrusion originated from IP address 192.168.1.104 on the internal network.",
    "Server logs show repeated login attempts from 8.8.8.8 and 203.0.113.7.",
    "Date of birth: 14/03/1988 as recorded in the employee file.",
    "Her DOB is March 3, 1990, per the passport copy submitted.",
    "He was born on 1975-11-02 according to the affidavit.",
]

SYNTHETIC_GROUND_TRUTH = [
    # 1-indexed line numbers, matching SYNTHETIC_LINES above
    (1, "SSN", "245-11-8734"),
    (2, "SSN", "002-14-9834"),
    (3, "CREDIT_CARD", "4539 1488 0343 6467"),
    (4, "CREDIT_CARD", "5555555555554444"),
    (5, "CREDIT_CARD", "4111-1111-1111-1111"),
    (6, "IP_ADDRESS", "192.168.1.104"),
    (7, "IP_ADDRESS", "8.8.8.8"),
    (7, "IP_ADDRESS", "203.0.113.7"),
    (8, "DATE_OF_BIRTH", "14/03/1988"),
    (9, "DATE_OF_BIRTH", "March 3, 1990"),
    (10, "DATE_OF_BIRTH", "1975-11-02"),
]

# Negative controls: none of these should trigger ANY redaction event.
# Mixed into the same corpus for the precision count.
NEGATIVE_CONTROL_LINES = [
    "Order number 20220803-40 was processed on the same day as ticket 000011179.",
    "Financial year 2024-2025 revenue grew compared to 2022-2023.",
    "Registration number: 141032. Corporate identity number: U28129PN1979PLC141032.",
    "SEBI registration no.: INM000013004 and INZ000166136 were both verified.",
    "The build number is 20.4.5053237 and the invoice total was 4,200.00 rupees.",
]
