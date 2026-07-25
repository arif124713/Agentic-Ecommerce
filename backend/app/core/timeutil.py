"""MySQL's DATETIME has no timezone-aware variant, so every datetime SQLAlchemy reads back is
naive even though models declare DateTime(timezone=True) (this bit auth_service.py once already
— see done.MD). The app's convention is that every stored timestamp is UTC wall-clock; new code
should use `utcnow()` everywhere (for both storage and comparisons) so naive-vs-aware never comes
up again."""

import datetime


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
