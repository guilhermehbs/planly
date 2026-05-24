import secrets

from backend.security import hash_password, verify_password
from backend.serializers import public_user, row_to_dict
from backend.validators import require_text


def create_initial_admin(db, email, password):
    if not email or not password:
        return
    db.create_admin_if_missing(hash_password(password), email)


def create_login_response(db, user):
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    db.add_session(token, user["id"], csrf_token)
    return {"user": me_payload(db, user), "csrfToken": csrf_token}, token


def register_user(db, payload):
    name = require_text(payload, "name")
    email = require_text(payload, "email").lower()
    password = require_text(payload, "password")
    if db.get_user_by_email(email):
        return {"error": "E-mail ja cadastrado"}, 400
    user_id = db.add_user(name, email, hash_password(password), "client")
    user = db.get_user(user_id)
    db.ensure_client_for_user(user)
    body, token = create_login_response(db, user)
    return body, 201, token


def login_user(db, payload):
    user = db.get_user_by_email(require_text(payload, "email"))
    if not user or not verify_password(require_text(payload, "password"), user["password_hash"]):
        return {"error": "E-mail ou senha invalidos"}, 401
    body, token = create_login_response(db, user)
    return body, 200, token


def me_payload(db, user):
    data = public_user(user)
    client = db.get_client_by_user(user["id"])
    data["client"] = row_to_dict(client)
    data["planner"] = public_user(db.get_user(client["planner_id"])) if client and client["planner_id"] else None
    return data
