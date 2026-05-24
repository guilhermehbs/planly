def require_role(user, role):
    if user["role"] != role:
        raise PermissionError("Acesso negado")


def client_for_user(db, user):
    client = db.get_client_by_user(user["id"])
    if not client:
        db.ensure_client_for_user(user)
        client = db.get_client_by_user(user["id"])
    return client


def authorized_client(db, user, client_id):
    client = db.get_client(client_id)
    if not client:
        raise ValueError("Cliente nao encontrado")
    if user["role"] == "admin":
        return client
    if user["role"] == "planner" and client["planner_id"] == user["id"]:
        return client
    if user["role"] == "client" and client["user_id"] == user["id"]:
        return client
    raise PermissionError("Acesso negado")
