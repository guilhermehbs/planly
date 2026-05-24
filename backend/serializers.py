def row_to_dict(row):
    return dict(row) if row else None


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def public_user(user):
    data = row_to_dict(user)
    if data:
        data.pop("password_hash", None)
    return data
