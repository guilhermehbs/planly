import json
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from backend.access import authorized_client, client_for_user, require_role
from backend.auth import create_initial_admin, login_user, me_payload, register_user
from backend.config import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ALLOWED_ORIGINS,
    APP_ENV,
    COOKIE_SECURE,
    HOST,
    MAX_REQUEST_BYTES,
    PAYMENT_METHODS,
    PORT,
    PUBLIC_ERROR_DETAILS,
    REQUIRE_CSRF,
    ROLES,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_NAME,
    SESSION_TTL_HOURS,
    validate_production_config,
)
from backend.dashboard import build_dashboard
from backend.report import build_client_report
from backend.serializers import row_to_dict, rows_to_dicts
from backend.validators import current_month, integer, numeric, optional_text, require_text
from core.config import DB_PATH
from data.database import Database


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "PlanlyAPI"
    sys_version = ""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_PUT(self):
        self.handle_request("PUT")

    def do_DELETE(self):
        self.handle_request("DELETE")

    def handle_request(self, method):
        self.extra_headers = []
        self.session = None
        self.session_token = None
        try:
            parsed = urlparse(self.path)
            parts = [part for part in parsed.path.split("/") if part]
            if not parts or parts[0] != "api":
                self.send_json({"error": "Rota nao encontrada"}, status=404)
                return

            payload = self.read_json() if method in {"POST", "PUT"} else {}
            query = parse_qs(parsed.query)
            db = Database(DB_PATH)
            validate_production_config(DB_PATH)
            create_initial_admin(db, ADMIN_EMAIL, ADMIN_PASSWORD)
            db.delete_expired_sessions(SESSION_TTL_HOURS)
            db.backfill_installments()
            result = self.dispatch(db, method, parts[1:], payload, query)
            if isinstance(result, tuple) and len(result) == 3:
                body, status, session_token = result
                self.set_session_cookie(session_token)
            elif isinstance(result, tuple):
                body, status = result
            else:
                body, status = result, 200
            self.send_json(body, status=status)
        except PermissionError as error:
            self.send_json({"error": str(error)}, status=403)
        except ValueError as error:
            self.send_json({"error": str(error)}, status=400)
        except Exception as error:
            message = f"Erro interno: {error}" if PUBLIC_ERROR_DETAILS else "Erro interno."
            self.send_json({"error": message}, status=500)

    def dispatch(self, db, method, parts, payload, query):
        if method == "GET" and parts == ["health"]:
            return {"status": "ok"}

        if parts == ["auth", "register"] and method == "POST":
            return register_user(db, payload)

        if parts == ["auth", "login"] and method == "POST":
            return login_user(db, payload)

        user = self.require_user(db)
        self.require_csrf(method, parts)

        if parts == ["auth", "logout"] and method == "POST":
            token = self.auth_token()
            if token:
                db.delete_session(token)
            self.clear_session_cookie()
            return {"ok": True}

        if parts == ["me"] and method == "GET":
            return {"user": me_payload(db, user), "csrfToken": self.session["csrf_token"] if self.session else None}

        if parts == ["admin", "users"] and method == "GET":
            require_role(user, "admin")
            return rows_to_dicts(db.list_users())

        if len(parts) == 4 and parts[:2] == ["admin", "users"] and parts[3] == "role" and method == "PUT":
            require_role(user, "admin")
            role = require_text(payload, "role")
            if role not in ROLES:
                raise ValueError("Tipo de usuario invalido")
            db.update_user_role(int(parts[2]), role)
            return {"ok": True}

        if len(parts) == 3 and parts[:2] == ["admin", "users"] and method == "DELETE":
            require_role(user, "admin")
            user_id = int(parts[2])
            if user_id == user["id"]:
                raise ValueError("O admin nao pode excluir a propria conta")
            if not db.get_user(user_id):
                return {"error": "Usuario nao encontrado"}, 404
            db.delete_user(user_id)
            return {"ok": True}

        if parts == ["categories"] and method == "GET":
            if user["role"] not in {"admin", "planner", "client"}:
                raise PermissionError("Acesso negado")
            category_type = query.get("type", [None])[0]
            return rows_to_dicts(db.list_global_categories(include_inactive=user["role"] != "client", category_type=category_type))

        if parts == ["categories"] and method == "POST":
            if user["role"] not in {"admin", "planner"}:
                raise PermissionError("Acesso negado")
            category_id = db.add_global_category(
                require_text(payload, "name"),
                require_text(payload, "type"),
                1 if payload.get("active", True) else 0,
            )
            return row_to_dict(db.get_global_category(category_id)), 201

        if len(parts) == 2 and parts[0] == "categories" and method in {"PUT", "DELETE"}:
            if user["role"] not in {"admin", "planner"}:
                raise PermissionError("Acesso negado")
            category_id = int(parts[1])
            if method == "PUT":
                db.update_global_category(
                    category_id,
                    require_text(payload, "name"),
                    require_text(payload, "type"),
                    1 if payload.get("active", True) else 0,
                )
                return row_to_dict(db.get_global_category(category_id))
            db.delete_global_category(category_id)
            return {"ok": True}

        if parts == ["planner", "clients"] and method == "GET":
            require_role(user, "planner")
            return {
                "assigned": rows_to_dicts(db.list_planner_clients(user["id"])),
                "available": rows_to_dicts(db.list_unassigned_clients()),
            }

        if len(parts) == 4 and parts[:2] == ["planner", "clients"] and parts[3] == "assign" and method == "POST":
            require_role(user, "planner")
            db.assign_client_to_planner(int(parts[2]), user["id"])
            return row_to_dict(db.get_client(int(parts[2])))

        if parts == ["clients"] and method == "GET":
            if user["role"] == "admin":
                return rows_to_dicts(db.list_clients())
            if user["role"] == "planner":
                return rows_to_dicts(db.list_planner_clients(user["id"]))
            return [row_to_dict(client_for_user(db, user))]

        if parts == ["clients"] and method == "POST":
            require_role(user, "planner")
            client_id = db.add_client(
                require_text(payload, "name"),
                optional_text(payload, "email"),
                optional_text(payload, "phone"),
                optional_text(payload, "notes"),
                planner_id=user["id"],
                salary=numeric(payload, "salary"),
            )
            return row_to_dict(db.get_client(client_id)), 201

        if len(parts) >= 2 and parts[0] == "clients":
            client_id = int(parts[1])
            client = authorized_client(db, user, client_id)

            if len(parts) == 2 and method == "GET":
                return row_to_dict(client)

            if len(parts) == 2 and method == "PUT":
                if user["role"] not in {"admin", "planner"}:
                    raise PermissionError("Acesso negado")
                db.update_client(
                    client_id,
                    require_text(payload, "name"),
                    optional_text(payload, "email"),
                    optional_text(payload, "phone"),
                    optional_text(payload, "notes"),
                    numeric(payload, "salary"),
                )
                return row_to_dict(db.get_client(client_id))

            if len(parts) == 2 and method == "DELETE":
                if user["role"] != "admin":
                    raise PermissionError("Acesso negado")
                db.delete_client(client_id)
                return {"ok": True}

            if len(parts) == 3 and parts[2] == "categories":
                return self.handle_budgets(db, user, client_id, method, payload)

            if len(parts) == 3 and parts[2] == "budgets":
                return self.handle_budgets(db, user, client_id, method, payload)

            if len(parts) == 3 and parts[2] == "incomes":
                return self.handle_incomes(db, user, client_id, method, payload, query)

            if len(parts) == 3 and parts[2] == "expenses":
                return self.handle_expenses(db, user, client_id, method, payload, query)

            if len(parts) == 3 and parts[2] == "debts":
                return self.handle_debts(db, user, client_id, method, payload, query)

            if len(parts) == 3 and parts[2] == "dashboard" and method == "GET":
                return build_dashboard(db, client_id, query.get("month", [current_month()])[0])

            if len(parts) == 3 and parts[2] == "meetings" and method == "GET":
                if user["role"] == "client":
                    raise PermissionError("Acesso negado")
                return rows_to_dicts(db.list_meetings(client_id))

            if len(parts) == 3 and parts[2] == "meetings" and method == "POST":
                require_role(user, "planner")
                meeting_id = db.add_meeting(
                    client_id,
                    optional_text(payload, "meeting_date"),
                    require_text(payload, "summary"),
                    optional_text(payload, "progress"),
                    optional_text(payload, "next_steps"),
                )
                return rows_to_dicts([row for row in db.list_meetings(client_id) if row["id"] == meeting_id])[0], 201

            if len(parts) == 3 and parts[2] == "goals" and method == "GET":
                if user["role"] == "client":
                    raise PermissionError("Acesso negado")
                return rows_to_dicts(db.list_goals(client_id))

            if len(parts) == 3 and parts[2] == "goals" and method == "POST":
                require_role(user, "planner")
                goal_id = db.add_goal(
                    client_id,
                    require_text(payload, "name"),
                    numeric(payload, "target_amount"),
                    numeric(payload, "current_amount"),
                    numeric(payload, "monthly_contribution"),
                    numeric(payload, "allocation_percent"),
                    optional_text(payload, "money_place"),
                    optional_text(payload, "deadline"),
                    optional_text(payload, "notes"),
                )
                return row_to_dict(db.get_goal(goal_id)), 201

            if len(parts) == 3 and parts[2] in {"report", "report.txt"} and method == "GET":
                if user["role"] == "client":
                    raise PermissionError("Acesso negado")
                text = build_client_report(client, db.list_meetings(client_id), db.list_goals(client_id))
                if parts[2] == "report.txt" or query.get("format") == ["text"]:
                    return {"filename": self.report_filename(client), "content": text}
                return {"content": text}

        if len(parts) == 2 and parts[0] == "client-budgets":
            return self.handle_budget_by_id(db, user, int(parts[1]), method, payload)

        if len(parts) == 2 and parts[0] == "incomes":
            return self.handle_income_by_id(db, user, int(parts[1]), method, payload)

        if len(parts) == 2 and parts[0] == "expenses":
            return self.handle_expense_by_id(db, user, int(parts[1]), method, payload)

        if len(parts) == 2 and parts[0] == "debts":
            return self.handle_debt_by_id(db, user, int(parts[1]), method, payload)

        if len(parts) == 2 and parts[0] == "meetings" and method == "DELETE":
            require_role(user, "planner")
            db.delete_meeting(int(parts[1]))
            return {"ok": True}

        if len(parts) == 2 and parts[0] == "goals":
            require_role(user, "planner")
            goal_id = int(parts[1])
            goal = db.get_goal(goal_id)
            if not goal:
                return {"error": "Meta nao encontrada"}, 404
            authorized_client(db, user, goal["client_id"])
            if method == "PUT":
                db.update_goal(
                    goal_id,
                    require_text(payload, "name"),
                    numeric(payload, "target_amount"),
                    numeric(payload, "current_amount"),
                    numeric(payload, "monthly_contribution"),
                    numeric(payload, "allocation_percent"),
                    optional_text(payload, "money_place"),
                    optional_text(payload, "deadline"),
                    optional_text(payload, "notes"),
                )
                return row_to_dict(db.get_goal(goal_id))
            if method == "DELETE":
                db.delete_goal(goal_id)
                return {"ok": True}

        return {"error": "Rota nao encontrada"}, 404

    def handle_budgets(self, db, user, client_id, method, payload):
        if method == "GET":
            return rows_to_dicts(db.list_categories(client_id, include_inactive=user["role"] != "client"))
        require_role(user, "planner")
        if method == "POST":
            category = db.get_global_category(integer(payload, "category_id"))
            if not category or category["type"] not in {"expense", "both"}:
                raise ValueError("Categoria de gasto invalida")
            budget_id = db.add_client_budget(
                client_id,
                category["id"],
                numeric(payload, "allocation_percent"),
                1 if payload.get("active", True) else 0,
            )
            return row_to_dict(db.get_category(budget_id)), 201
        return {"error": "Metodo invalido"}, 405

    def handle_budget_by_id(self, db, user, budget_id, method, payload):
        budget = db.get_client_budget(budget_id)
        if not budget:
            return {"error": "Orcamento nao encontrado"}, 404
        authorized_client(db, user, budget["client_id"])
        require_role(user, "planner")
        if method == "PUT":
            db.update_client_budget(
                budget_id,
                numeric(payload, "allocation_percent"),
                1 if payload.get("active", True) else 0,
            )
            return row_to_dict(db.get_category(budget_id))
        if method == "DELETE":
            db.delete_category(budget_id)
            return {"ok": True}
        return {"error": "Metodo invalido"}, 405

    def handle_incomes(self, db, user, client_id, method, payload, query):
        if method == "GET":
            return rows_to_dicts(db.list_incomes(client_id, query.get("month", [None])[0]))
        if method == "POST":
            category = db.get_global_category(integer(payload, "category_id"))
            if not category or category["type"] not in {"income", "both"}:
                raise ValueError("Categoria de ganho invalida")
            income_id = db.add_income(
                client_id,
                category["id"],
                require_text(payload, "income_date"),
                numeric(payload, "amount"),
                optional_text(payload, "description"),
            )
            return row_to_dict(db.get_income(income_id)), 201
        return {"error": "Metodo invalido"}, 405

    def handle_income_by_id(self, db, user, income_id, method, payload):
        income = db.get_income(income_id)
        if not income:
            return {"error": "Ganho nao encontrado"}, 404
        authorized_client(db, user, income["client_id"])
        if method == "PUT":
            category = db.get_global_category(integer(payload, "category_id"))
            if not category or category["type"] not in {"income", "both"}:
                raise ValueError("Categoria de ganho invalida")
            db.update_income(
                income_id,
                category["id"],
                require_text(payload, "income_date"),
                numeric(payload, "amount"),
                optional_text(payload, "description"),
            )
            return row_to_dict(db.get_income(income_id))
        if method == "DELETE":
            db.delete_income(income_id)
            return {"ok": True}
        return {"error": "Metodo invalido"}, 405

    def handle_expenses(self, db, user, client_id, method, payload, query):
        if method == "GET":
            return rows_to_dicts(db.list_expenses(client_id, query.get("month", [None])[0]))
        if method == "POST":
            category = db.get_global_category(integer(payload, "category_id"))
            if not category or category["type"] not in {"expense", "both"}:
                raise ValueError("Categoria invalida")
            payment_method = require_text(payload, "payment_method")
            if payment_method not in PAYMENT_METHODS:
                raise ValueError("Modo de pagamento invalido")
            installments = integer(payload, "installments", 1)
            if payment_method == "credito" and installments < 1:
                raise ValueError("Informe o numero de parcelas")
            expense_id = db.add_expense(
                client_id,
                category["id"],
                require_text(payload, "expense_date"),
                numeric(payload, "amount"),
                payment_method,
                installments if payment_method == "credito" else 1,
                optional_text(payload, "description"),
            )
            return row_to_dict(db.get_expense(expense_id)), 201
        return {"error": "Metodo invalido"}, 405

    def handle_expense_by_id(self, db, user, expense_id, method, payload):
        expense = db.get_expense(expense_id)
        if not expense:
            return {"error": "Gasto nao encontrado"}, 404
        authorized_client(db, user, expense["client_id"])
        if method == "PUT":
            if user["role"] not in {"planner", "client"}:
                raise PermissionError("Acesso negado")
            category = db.get_global_category(integer(payload, "category_id"))
            if not category or category["type"] not in {"expense", "both"}:
                raise ValueError("Categoria invalida")
            payment_method = require_text(payload, "payment_method")
            if payment_method not in PAYMENT_METHODS:
                raise ValueError("Modo de pagamento invalido")
            installments = integer(payload, "installments", 1)
            db.update_expense(
                expense_id,
                category["id"],
                require_text(payload, "expense_date"),
                numeric(payload, "amount"),
                payment_method,
                installments if payment_method == "credito" else 1,
                optional_text(payload, "description"),
            )
            return row_to_dict(db.get_expense(expense_id))
        if method == "DELETE":
            db.delete_expense(expense_id)
            return {"ok": True}
        return {"error": "Metodo invalido"}, 405

    def handle_debts(self, db, user, client_id, method, payload, query):
        if method == "GET":
            return rows_to_dicts(db.list_debts(client_id, query.get("month", [None])[0]))
        if method == "POST":
            debt_id = db.add_debt(
                client_id,
                require_text(payload, "title"),
                require_text(payload, "description"),
                numeric(payload, "original_amount"),
                numeric(payload, "current_amount"),
                numeric(payload, "interest_rate"),
                integer(payload, "installments", 1),
                optional_text(payload, "due_date"),
                require_text(payload, "debt_type"),
                optional_text(payload, "creditor"),
                integer(payload, "paid_installments", 0),
                optional_text(payload, "status") or "open",
            )
            return row_to_dict(db.get_debt(debt_id)), 201
        return {"error": "Metodo invalido"}, 405

    def handle_debt_by_id(self, db, user, debt_id, method, payload):
        debt = db.get_debt(debt_id)
        if not debt:
            return {"error": "Divida nao encontrada"}, 404
        authorized_client(db, user, debt["client_id"])
        if method == "PUT":
            db.update_debt(
                debt_id,
                require_text(payload, "title"),
                require_text(payload, "description"),
                numeric(payload, "original_amount"),
                numeric(payload, "current_amount"),
                numeric(payload, "interest_rate"),
                integer(payload, "installments", 1),
                optional_text(payload, "due_date"),
                require_text(payload, "debt_type"),
                optional_text(payload, "creditor"),
                integer(payload, "paid_installments", 0),
                optional_text(payload, "status") or "open",
            )
            return row_to_dict(db.get_debt(debt_id))
        if method == "DELETE":
            db.delete_debt(debt_id)
            return {"ok": True}
        return {"error": "Metodo invalido"}, 405

    def auth_token(self):
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header[7:]
        cookie_header = self.headers.get("Cookie", "")
        if cookie_header:
            cookies = SimpleCookie()
            cookies.load(cookie_header)
            if SESSION_COOKIE_NAME in cookies:
                return cookies[SESSION_COOKIE_NAME].value
        return None

    def require_user(self, db):
        token = self.auth_token()
        if not token:
            raise PermissionError("Login obrigatorio")
        session = db.get_session(token)
        if not session:
            raise PermissionError("Sessao invalida")
        if not session["csrf_token"]:
            db.update_session_csrf(token, secrets.token_urlsafe(32))
            session = db.get_session(token)
        user = db.get_session_user(token)
        if not user:
            raise PermissionError("Sessao invalida")
        self.session = session
        self.session_token = token
        return user

    def require_csrf(self, method, parts):
        if not REQUIRE_CSRF or method not in {"POST", "PUT", "DELETE"}:
            return
        if parts in (["auth", "login"], ["auth", "register"], ["auth", "logout"]):
            return
        expected = self.session["csrf_token"] if self.session else None
        received = self.headers.get("X-CSRF-Token", "")
        if not expected or not received or received != expected:
            raise PermissionError("Token CSRF invalido")

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        if length > MAX_REQUEST_BYTES:
            raise ValueError("Requisicao muito grande")
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def send_json(self, body, status=200):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if APP_ENV == "production":
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for name, value in getattr(self, "extra_headers", []):
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def send_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")

    def set_session_cookie(self, token):
        max_age = SESSION_TTL_HOURS * 60 * 60
        cookie = f"{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite={SESSION_COOKIE_SAMESITE}"
        if COOKIE_SECURE:
            cookie += "; Secure"
        self.extra_headers.append(("Set-Cookie", cookie))

    def clear_session_cookie(self):
        cookie = f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite={SESSION_COOKIE_SAMESITE}"
        if COOKIE_SECURE:
            cookie += "; Secure"
        self.extra_headers.append(("Set-Cookie", cookie))

    def report_filename(self, client):
        safe_name = "".join(char for char in client["name"] if char.isalnum() or char in (" ", "-", "_")).strip()
        return f"resumo_{safe_name.replace(' ', '_')}.txt"

    def log_message(self, format, *args):
        return


def main():
    validate_production_config(DB_PATH)
    db = Database(DB_PATH)
    create_initial_admin(db, ADMIN_EMAIL, ADMIN_PASSWORD)
    db.backfill_installments()
    server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    print(f"API rodando em http://{HOST}:{PORT}")
    if ADMIN_EMAIL:
        print("Admin inicial configurado por variavel de ambiente.")
    server.serve_forever()


if __name__ == "__main__":
    main()
