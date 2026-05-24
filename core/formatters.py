def br_money(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_money(value):
    value = value.strip().replace("R$", "").replace(" ", "")
    if not value:
        return 0.0
    value = value.replace(".", "").replace(",", ".")
    return float(value)


def parse_percent(value):
    value = value.strip().replace("%", "").replace(",", ".")
    if not value:
        return 0.0
    return float(value)
