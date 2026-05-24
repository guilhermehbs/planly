from datetime import date


def require_text(payload, field):
    value = str(payload.get(field, "")).strip()
    if not value:
        raise ValueError(f"Campo obrigatorio: {field}")
    return value


def optional_text(payload, field):
    return str(payload.get(field, "") or "").strip()


def numeric(payload, field):
    value = payload.get(field, 0)
    if value in ("", None):
        return 0.0
    return float(value)


def integer(payload, field, default=1):
    value = payload.get(field, default)
    if value in ("", None):
        return default
    return int(value)


def current_month():
    return date.today().isoformat()[:7]
