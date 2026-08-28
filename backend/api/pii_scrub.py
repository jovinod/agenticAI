"""
Basic PII scrubbing for /search's free-form query -- the one place in this
app a user can type genuinely open-ended text (every other input, the
ticker and market, is a tightly constrained value, not free text). Applied
before the query is embedded or echoed back, and before Phase 10's tracing
work would otherwise capture it verbatim in a log or trace.

Deliberately basic, matching Phase 9's stated scope: pattern-based
detection of the two most common accidental-PII shapes (email addresses,
phone numbers), not a general-purpose PII classifier. A user asking "what
did we say about AAPL's earnings" has no reason to type an email or phone
number into a stock-research search box in the first place -- this is a
safety net for the accidental case, not a defense against a determined
attacker trying to smuggle data through.
"""
import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# A loose phone-number shape: optional country code, then 7+ digits with
# common separators (space, dash, dot, parens) -- deliberately permissive
# since under-matching (a real phone number slipping through) is worse
# here than over-matching (a long ticker-like number getting redacted).
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4,6}\b")


def scrub_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    return text
