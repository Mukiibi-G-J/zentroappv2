"""Login identifier resolution: email, phone, or username."""

from __future__ import annotations

import re

from authentication.models import CustomUser as User

_PHONE_CHARS_RE = re.compile(r"^[\d\s\-+()]+$")
_PLACEHOLDER_PHONE_PREFIX = "NO_PHONE_"


def is_phone_identifier(identifier: str) -> bool:
    """True when identifier looks like a phone number (no @, mostly digits)."""
    if not identifier or "@" in identifier:
        return False
    stripped = identifier.strip()
    if not stripped or not _PHONE_CHARS_RE.match(stripped):
        return False
    digits = re.sub(r"\D", "", stripped)
    return len(digits) >= 9


def normalize_phone_number(raw: str) -> str | None:
    """Normalize to international digits without + (e.g. 256750123456)."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw.strip())
    if not digits:
        return None
    if digits.startswith("256") and len(digits) >= 12:
        return digits
    if digits.startswith("0") and len(digits) >= 10:
        return "256" + digits[1:]
    if len(digits) == 9 and digits[0] in "789":
        return "256" + digits
    if len(digits) >= 9:
        return digits
    return None


def phone_lookup_variants(raw: str) -> list[str]:
    """Return distinct phone forms to match against stored phone_number."""
    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str | None) -> None:
        if not value or value in seen:
            return
        seen.add(value)
        variants.append(value)

    stripped = (raw or "").strip()
    add(stripped)
    if stripped.startswith("+"):
        add(stripped[1:])

    normalized = normalize_phone_number(stripped)
    add(normalized)
    if normalized and normalized.startswith("256") and len(normalized) > 3:
        local = "0" + normalized[3:]
        add(local)
        add("+" + normalized)

    return variants


def is_placeholder_phone(phone: str | None) -> bool:
    return bool(phone and phone.startswith(_PLACEHOLDER_PHONE_PREFIX))


def find_user_by_phone(identifier: str) -> User | None:
    """Look up user by phone variants; excludes placeholder phone numbers."""
    for variant in phone_lookup_variants(identifier):
        user = User.objects.filter(phone_number=variant).first()
        if user and not is_placeholder_phone(user.phone_number):
            return user
    return None


def resolve_login_identifier(identifier: str) -> tuple[User | None, str, bool]:
    """
    Resolve login identifier to a user email for JWT auth.

    Returns:
        (user_or_none, resolved_email, login_via_phone)
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return None, "", False

    if "@" in identifier:
        return None, identifier, False

    if is_phone_identifier(identifier):
        user = find_user_by_phone(identifier)
        if user:
            return user, user.email, True

    user = User.objects.filter(username__iexact=identifier).first()
    if user:
        return user, user.email, False

    return None, identifier, False
