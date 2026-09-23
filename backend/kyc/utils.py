"""Sensitive-data helpers for the KYC layer.

Every national-ID / provider-reference value leaving the API passes through a
mask. Full values live only in DB fields the API never serializes directly.
"""


def mask_identifier(value, keep=4):
    """Mask an identifier, showing only its last ``keep`` characters.

    ``XXXXXXXX1234`` for a 12-char value with keep=4.
    """
    if not value:
        return ""
    value = str(value)
    if len(value) <= keep:
        return "*" * max(len(value) - 1, 1) + value[-1:]
    return "*" * (len(value) - keep) + value[-keep:]


def mask_name(value):
    """Mask a name to its first letter and last name.

    ``Jane Mfaume`` -> ``J. M****e`` (keeps ordering/identity safe while
    remaining greppable by staff who already know the member).
    """
    if not value:
        return ""
    parts = str(value).split()
    if not parts:
        return ""
    if len(parts) == 1:
        head = parts[0][0] if parts[0] else ""
        return f"{head}." if head else ""
    first = parts[0][0] if parts[0] else ""
    last = parts[-1]
    if len(last) <= 2:
        return f"{first}. {last}"
    return f"{first}. {last[0]}****{last[-1]}"