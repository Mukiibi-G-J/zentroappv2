"""Restaurant app PIN: format validation and per-tenant uniqueness."""

from django.contrib.auth.hashers import check_password

from rest_framework import serializers as drf_serializers


RESTAURANT_PIN_MIN_LEN = 4
RESTAURANT_PIN_MAX_LEN = 6


def validate_restaurant_pin_format(pin) -> str:
    """
    Return normalized digit string or raise ValidationError.
    Empty string means clear PIN (caller should handle before hashing).
    """
    if pin is None:
        return ""
    raw = str(pin).strip()
    if raw == "":
        return ""
    if not raw.isdigit():
        raise drf_serializers.ValidationError(
            "Restaurant PIN must contain only digits."
        )
    if not (RESTAURANT_PIN_MIN_LEN <= len(raw) <= RESTAURANT_PIN_MAX_LEN):
        raise drf_serializers.ValidationError(
            f"Restaurant PIN must be between {RESTAURANT_PIN_MIN_LEN} and "
            f"{RESTAURANT_PIN_MAX_LEN} digits."
        )
    return raw


def restaurant_pin_taken_in_tenant(pin: str, *, exclude_user_id=None) -> bool:
    """True if another user in the current DB schema already has this PIN."""
    from authentication.models import CustomUser

    qs = (
        CustomUser.objects.filter(is_active=True)
        .exclude(restaurant_pin_hash__isnull=True)
        .exclude(restaurant_pin_hash="")
    )
    if exclude_user_id is not None:
        qs = qs.exclude(pk=exclude_user_id)
    for user in qs.iterator():
        if check_password(pin, user.restaurant_pin_hash):
            return True
    return False
