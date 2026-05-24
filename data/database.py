import sqlite3
import os
from datetime import datetime, timedelta

from core.config import DATABASE_URL


class PostgresCursor:
    def __init__(self, connection, cursor):
        self.connection = connection
        self.cursor = cursor

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        with self.connection.raw.cursor() as cursor:
            cursor.execute("SELECT lastval() AS id")
            row = cursor.fetchone()
            return row["id"]


class PostgresConnection:
    def __init__(self, database_url):
        import psycopg
        from psycopg.rows import dict_row

        self.raw = psycopg.connect(database_url, row_factory=dict_row)

    def execute(self, query, params=None):
        cursor = self.raw.cursor()
        cursor.execute(self.translate(query), params or ())
        return PostgresCursor(self, cursor)

    def executescript(self, script):
        for statement in [part.strip() for part in script.split(";") if part.strip()]:
            self.execute(statement)

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()

    def translate(self, query):
        return query.replace("?", "%s")


class BaseDatabase:
    def __init__(self, path):
        self.is_postgres = bool(DATABASE_URL)
        if self.is_postgres:
            self.conn = PostgresConnection(DATABASE_URL)
        else:
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_schema()
        if not self.is_postgres:
            self.restrict_database_file_permissions(path)

    def restrict_database_file_permissions(self, path):
        if os.name != "posix":
            return
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def create_schema(self):
        if self.is_postgres:
            self.conn.executescript(POSTGRES_SCHEMA)
        else:
            self.conn.executescript(SQLITE_SCHEMA)
        self.ensure_column("clients", "user_id", "INTEGER UNIQUE")
        self.ensure_column("clients", "planner_id", "INTEGER")
        self.ensure_column("sessions", "csrf_token", "TEXT")
        self.ensure_column("clients", "salary", "REAL NOT NULL DEFAULT 0")
        self.ensure_column("expenses", "original_amount", "REAL")
        self.ensure_column("expenses", "global_category_id", "INTEGER")
        self.ensure_column("debts", "global_category_id", "INTEGER")
        self.ensure_column("debts", "title", "TEXT DEFAULT ''")
        self.ensure_column("debts", "original_amount", "REAL NOT NULL DEFAULT 0")
        self.ensure_column("debts", "current_amount", "REAL NOT NULL DEFAULT 0")
        self.ensure_column("debts", "interest_rate", "REAL NOT NULL DEFAULT 0")
        self.ensure_column("debts", "debt_type", "TEXT NOT NULL DEFAULT 'outro'")
        self.ensure_column("debts", "creditor", "TEXT DEFAULT ''")
        self.ensure_column("debts", "paid_installments", "INTEGER NOT NULL DEFAULT 0")
        self.conn.commit()

    def ensure_column(self, table, column, definition):
        if self.is_postgres:
            row = self.conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = ?
                  AND column_name = ?
                """,
                (table, column),
            ).fetchone()
            if row:
                return
        else:
            columns = [row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if column in columns:
                return
        definition = definition.replace(" UNIQUE", "")
        self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def insert_and_get_id(self, query, params):
        if self.is_postgres:
            cursor = self.conn.execute(f"{query} RETURNING id", params)
            return cursor.fetchone()["id"]
        cursor = self.conn.execute(query, params)
        return cursor.lastrowid

    def reset_sequence(self, table):
        if not self.is_postgres:
            return
        safe_table = "".join(char for char in table if char.isalnum() or char == "_")
        if safe_table != table:
            raise ValueError("Nome de tabela invalido")
        self.conn.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                (SELECT MAX(id) FROM {table}) IS NOT NULL
            )
            """
        )


SQLITE_SCHEMA = """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'client',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_token TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                planner_id INTEGER,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                salary REAL NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (planner_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                meeting_date TEXT NOT NULL,
                summary TEXT NOT NULL,
                progress TEXT DEFAULT '',
                next_steps TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                target_amount REAL NOT NULL DEFAULT 0,
                current_amount REAL NOT NULL DEFAULT 0,
                monthly_contribution REAL NOT NULL DEFAULT 0,
                allocation_percent REAL NOT NULL DEFAULT 0,
                money_place TEXT NOT NULL DEFAULT '',
                deadline TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL DEFAULT 'expense',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS client_category_budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                allocation_percent REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(client_id, category_id),
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                income_date TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                expense_date TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL,
                installments INTEGER NOT NULL DEFAULT 1,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS expense_installments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                installment_date TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                installment_number INTEGER NOT NULL DEFAULT 1,
                installments_total INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                category_id INTEGER,
                description TEXT NOT NULL,
                total_amount REAL NOT NULL DEFAULT 0,
                installments INTEGER NOT NULL DEFAULT 1,
                installment_amount REAL NOT NULL DEFAULT 0,
                due_date TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS debt_installments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debt_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                category_id INTEGER,
                due_date TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                installment_number INTEGER NOT NULL DEFAULT 1,
                installments_total INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'open',
                FOREIGN KEY (debt_id) REFERENCES debts(id) ON DELETE CASCADE,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            );
"""


POSTGRES_SCHEMA = SQLITE_SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")


class Database(BaseDatabase):

    def ensure_global_category(self, name, category_type="expense"):
        existing = self.conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
        if existing:
            return existing["id"]
        cursor = self.conn.execute(
            "INSERT INTO categories (name, type, active, created_at) VALUES (?, ?, 1, ?)",
            (name, category_type, datetime.now().isoformat(timespec="seconds")),
        )
        return cursor.lastrowid

    def create_admin_if_missing(self, password_hash, email):
        existing = self.conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if existing:
            return
        self.add_user("Administrador", email, password_hash, "admin")

    def add_user(self, name, email, password_hash, role="client"):
        cursor = self.conn.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email.lower(), password_hash, role, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_user(self, user_id):
        return self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def get_user_by_email(self, email):
        return self.conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()

    def list_users(self):
        return self.conn.execute("SELECT id, name, email, role, created_at FROM users ORDER BY name").fetchall()

    def update_user_role(self, user_id, role):
        self.conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        self.conn.commit()

    def delete_user(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return
        if user["role"] == "planner":
            self.conn.execute("UPDATE clients SET planner_id = NULL WHERE planner_id = ?", (user_id,))
        if user["role"] == "client":
            client = self.get_client_by_user(user_id)
            if client:
                self.conn.execute("DELETE FROM clients WHERE id = ?", (client["id"],))
        self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()

    def add_session(self, token, user_id, csrf_token):
        self.conn.execute(
            "INSERT INTO sessions (token, user_id, csrf_token, created_at) VALUES (?, ?, ?, ?)",
            (token, user_id, csrf_token, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def get_session(self, token):
        return self.conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()

    def update_session_csrf(self, token, csrf_token):
        self.conn.execute("UPDATE sessions SET csrf_token = ? WHERE token = ?", (csrf_token, token))
        self.conn.commit()


    def get_session_user(self, token):
        return self.conn.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()

    def delete_expired_sessions(self, ttl_hours):
        expires_before = (datetime.now() - timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
        self.conn.execute("DELETE FROM sessions WHERE created_at < ?", (expires_before,))
        self.conn.commit()

    def delete_session(self, token):
        self.conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        self.conn.commit()

    def add_client(self, name, email, phone, notes, user_id=None, planner_id=None, salary=0):
        cursor = self.conn.execute(
            """
            INSERT INTO clients (user_id, planner_id, name, email, phone, salary, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, planner_id, name, email, phone, salary, notes, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_client(self, client_id, name, email, phone, notes, salary=None):
        if salary is None:
            salary = self.get_client(client_id)["salary"]
        self.conn.execute(
            "UPDATE clients SET name = ?, email = ?, phone = ?, salary = ?, notes = ? WHERE id = ?",
            (name, email, phone, salary, notes, client_id),
        )
        self.conn.commit()

    def update_client_salary(self, client_id, salary):
        self.conn.execute("UPDATE clients SET salary = ? WHERE id = ?", (salary, client_id))
        self.conn.commit()

    def assign_client_to_planner(self, client_id, planner_id):
        client = self.conn.execute(
            """
            SELECT clients.*, users.role AS user_role
            FROM clients
            LEFT JOIN users ON users.id = clients.user_id
            WHERE clients.id = ?
            """,
            (client_id,),
        ).fetchone()
        if not client:
            raise ValueError("Cliente nao encontrado")
        if client["user_id"] == planner_id:
            raise ValueError("O planejador nao pode assumir o proprio cadastro como cliente")
        if client["user_id"] is not None and client["user_role"] != "client":
            raise ValueError("Apenas usuarios com login de cliente podem ser assumidos")
        self.conn.execute("UPDATE clients SET planner_id = ? WHERE id = ?", (planner_id, client_id))
        self.conn.commit()

    def delete_client(self, client_id):
        self.conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        self.conn.commit()

    def list_clients(self):
        return self.conn.execute("SELECT * FROM clients ORDER BY name").fetchall()

    def list_unassigned_clients(self):
        return self.conn.execute(
            """
            SELECT clients.*
            FROM clients
            JOIN users ON users.id = clients.user_id
            WHERE clients.planner_id IS NULL
              AND users.role = 'client'
            ORDER BY clients.name
            """
        ).fetchall()

    def list_planner_clients(self, planner_id):
        return self.conn.execute(
            "SELECT * FROM clients WHERE planner_id = ? ORDER BY name",
            (planner_id,),
        ).fetchall()

    def get_client(self, client_id):
        return self.conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()

    def get_client_by_user(self, user_id):
        return self.conn.execute("SELECT * FROM clients WHERE user_id = ?", (user_id,)).fetchone()

    def ensure_client_for_user(self, user):
        client = self.get_client_by_user(user["id"])
        if client:
            return client["id"]
        return self.add_client(user["name"], user["email"], "", "", user_id=user["id"])

    def add_meeting(self, client_id, meeting_date, summary, progress, next_steps):
        cursor = self.conn.execute(
            """
            INSERT INTO meetings (client_id, meeting_date, summary, progress, next_steps, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                meeting_date,
                summary,
                progress,
                next_steps,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_meetings(self, client_id):
        return self.conn.execute(
            "SELECT * FROM meetings WHERE client_id = ? ORDER BY meeting_date DESC, id DESC",
            (client_id,),
        ).fetchall()

    def delete_meeting(self, meeting_id):
        self.conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        self.conn.commit()

    def add_goal(
        self,
        client_id,
        name,
        target_amount,
        current_amount,
        monthly_contribution,
        allocation_percent,
        money_place,
        deadline,
        notes,
    ):
        cursor = self.conn.execute(
            """
            INSERT INTO goals (
                client_id, name, target_amount, current_amount, monthly_contribution,
                allocation_percent, money_place, deadline, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                name,
                target_amount,
                current_amount,
                monthly_contribution,
                allocation_percent,
                money_place,
                deadline,
                notes,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_goal(
        self,
        goal_id,
        name,
        target_amount,
        current_amount,
        monthly_contribution,
        allocation_percent,
        money_place,
        deadline,
        notes,
    ):
        self.conn.execute(
            """
            UPDATE goals
            SET name = ?, target_amount = ?, current_amount = ?, monthly_contribution = ?,
                allocation_percent = ?, money_place = ?, deadline = ?, notes = ?
            WHERE id = ?
            """,
            (
                name,
                target_amount,
                current_amount,
                monthly_contribution,
                allocation_percent,
                money_place,
                deadline,
                notes,
                goal_id,
            ),
        )
        self.conn.commit()

    def list_goals(self, client_id):
        return self.conn.execute(
            "SELECT * FROM goals WHERE client_id = ? ORDER BY allocation_percent DESC, name",
            (client_id,),
        ).fetchall()

    def get_goal(self, goal_id):
        return self.conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()

    def delete_goal(self, goal_id):
        self.conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        self.conn.commit()

    def add_global_category(self, name, category_type, active=1):
        cursor = self.conn.execute(
            "INSERT INTO categories (name, type, active, created_at) VALUES (?, ?, ?, ?)",
            (name, category_type, active, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_global_category(self, category_id, name, category_type, active=1):
        self.conn.execute(
            "UPDATE categories SET name = ?, type = ?, active = ? WHERE id = ?",
            (name, category_type, active, category_id),
        )
        self.conn.commit()

    def list_global_categories(self, include_inactive=True, category_type=None):
        params = []
        where = []
        if not include_inactive:
            where.append("active = 1")
        if category_type:
            where.append("(type = ? OR type = 'both')")
            params.append(category_type)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return self.conn.execute(f"SELECT * FROM categories {clause} ORDER BY active DESC, name", params).fetchall()

    def get_global_category(self, category_id):
        return self.conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()

    def delete_global_category(self, category_id):
        self.conn.execute("UPDATE categories SET active = 0 WHERE id = ?", (category_id,))
        self.conn.commit()

    def add_client_budget(self, client_id, category_id, allocation_percent, active=1):
        if self.is_postgres:
            cursor = self.conn.execute(
                """
                INSERT INTO client_category_budgets (client_id, category_id, allocation_percent, active, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(client_id, category_id)
                DO UPDATE SET allocation_percent = excluded.allocation_percent, active = excluded.active
                RETURNING id
                """,
                (client_id, category_id, allocation_percent, active, datetime.now().isoformat(timespec="seconds")),
            )
            budget_id = cursor.fetchone()["id"]
            self.conn.commit()
            return budget_id
        cursor = self.conn.execute(
            """
            INSERT INTO client_category_budgets (client_id, category_id, allocation_percent, active, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(client_id, category_id)
            DO UPDATE SET allocation_percent = excluded.allocation_percent, active = excluded.active
            """,
            (client_id, category_id, allocation_percent, active, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_client_budget(self, budget_id, allocation_percent, active=1):
        self.conn.execute(
            "UPDATE client_category_budgets SET allocation_percent = ?, active = ? WHERE id = ?",
            (allocation_percent, active, budget_id),
        )
        self.conn.commit()

    def list_client_budgets(self, client_id, include_inactive=True):
        where = "WHERE client_category_budgets.client_id = ?"
        if not include_inactive:
            where += " AND client_category_budgets.active = 1 AND categories.active = 1"
        return self.conn.execute(
            f"""
            SELECT client_category_budgets.*, categories.name, categories.type
            FROM client_category_budgets
            JOIN categories ON categories.id = client_category_budgets.category_id
            {where}
            ORDER BY client_category_budgets.active DESC, categories.name
            """,
            (client_id,),
        ).fetchall()

    def get_client_budget(self, budget_id):
        return self.conn.execute("SELECT * FROM client_category_budgets WHERE id = ?", (budget_id,)).fetchone()

    # Backward-compatible wrappers for the older Tkinter/API surface.
    def add_category(self, client_id, name, allocation_percent, description, active=1):
        category_id = self.ensure_global_category(name, "expense")
        return self.add_client_budget(client_id, category_id, allocation_percent, active)

    def update_category(self, category_id, name, allocation_percent, description, active=1):
        budget = self.get_client_budget(category_id)
        if budget:
            self.update_client_budget(category_id, allocation_percent, active)

    def list_categories(self, client_id, include_inactive=True):
        return self.list_client_budgets(client_id, include_inactive)

    def get_category(self, category_id):
        budget = self.get_client_budget(category_id)
        if budget:
            return self.conn.execute(
                """
                SELECT client_category_budgets.*, categories.name, categories.type
                FROM client_category_budgets
                JOIN categories ON categories.id = client_category_budgets.category_id
                WHERE client_category_budgets.id = ?
                """,
                (category_id,),
            ).fetchone()
        return self.get_global_category(category_id)

    def delete_category(self, category_id):
        self.conn.execute("UPDATE client_category_budgets SET active = 0 WHERE id = ?", (category_id,))
        self.conn.commit()

    def add_income(self, client_id, category_id, income_date, amount, description):
        cursor = self.conn.execute(
            """
            INSERT INTO incomes (client_id, category_id, income_date, amount, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (client_id, category_id, income_date, amount, description, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_income(self, income_id, category_id, income_date, amount, description):
        self.conn.execute(
            "UPDATE incomes SET category_id = ?, income_date = ?, amount = ?, description = ? WHERE id = ?",
            (category_id, income_date, amount, description, income_id),
        )
        self.conn.commit()

    def list_incomes(self, client_id, month=None):
        params = [client_id]
        where = "WHERE incomes.client_id = ?"
        if month:
            where += " AND substr(income_date, 1, 7) = ?"
            params.append(month)
        return self.conn.execute(
            f"""
            SELECT incomes.*, categories.name AS category_name
            FROM incomes
            JOIN categories ON categories.id = incomes.category_id
            {where}
            ORDER BY income_date DESC, incomes.id DESC
            """,
            params,
        ).fetchall()

    def get_income(self, income_id):
        return self.conn.execute("SELECT * FROM incomes WHERE id = ?", (income_id,)).fetchone()

    def delete_income(self, income_id):
        self.conn.execute("DELETE FROM incomes WHERE id = ?", (income_id,))
        self.conn.commit()

    def add_expense(self, client_id, category_id, expense_date, amount, payment_method, installments, description):
        cursor = self.conn.execute(
            """
            INSERT INTO expenses (
                client_id, category_id, global_category_id, expense_date, amount, original_amount,
                payment_method, installments, description, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                category_id,
                category_id,
                expense_date,
                amount,
                amount,
                payment_method,
                installments,
                description,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        expense_id = cursor.lastrowid
        self.recreate_expense_installments(expense_id, client_id, category_id, expense_date, amount, installments)
        self.conn.commit()
        return expense_id

    def update_expense(self, expense_id, category_id, expense_date, amount, payment_method, installments, description):
        expense = self.get_expense(expense_id)
        self.conn.execute(
            """
            UPDATE expenses
            SET category_id = ?, global_category_id = ?, expense_date = ?, amount = ?, original_amount = ?,
                payment_method = ?, installments = ?, description = ?
            WHERE id = ?
            """,
            (category_id, category_id, expense_date, amount, amount, payment_method, installments, description, expense_id),
        )
        self.recreate_expense_installments(expense_id, expense["client_id"], category_id, expense_date, amount, installments)
        self.conn.commit()

    def recreate_expense_installments(self, expense_id, client_id, category_id, expense_date, amount, installments):
        self.conn.execute("DELETE FROM expense_installments WHERE expense_id = ?", (expense_id,))
        installments = max(int(installments or 1), 1)
        installment_amount = round(float(amount) / installments, 2)
        for number in range(1, installments + 1):
            installment_date = add_months(expense_date, number - 1)
            value = installment_amount
            if number == installments:
                value = round(float(amount) - installment_amount * (installments - 1), 2)
            self.conn.execute(
                """
                INSERT INTO expense_installments (
                    expense_id, client_id, category_id, installment_date, amount,
                    installment_number, installments_total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (expense_id, client_id, category_id, installment_date, value, number, installments),
            )

    def list_expenses(self, client_id, month=None):
        params = [client_id]
        where = "WHERE expense_installments.client_id = ?"
        if month:
            where += " AND substr(expense_installments.installment_date, 1, 7) = ?"
            params.append(month)
        return self.conn.execute(
            f"""
            SELECT
                expense_installments.id AS installment_id,
                expense_installments.installment_date,
                expense_installments.amount AS installment_amount,
                expense_installments.installment_number,
                expense_installments.installments_total,
                expenses.*,
                categories.name AS category_name
            FROM expense_installments
            JOIN expenses ON expenses.id = expense_installments.expense_id
            JOIN categories ON categories.id = expense_installments.category_id
            {where}
            ORDER BY expense_installments.installment_date DESC, expenses.id DESC
            """,
            params,
        ).fetchall()

    def get_expense(self, expense_id):
        return self.conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()

    def delete_expense(self, expense_id):
        self.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        self.conn.commit()

    def add_debt(
        self,
        client_id,
        title,
        description,
        original_amount,
        current_amount,
        interest_rate,
        installments,
        due_date,
        debt_type,
        creditor,
        paid_installments,
        status,
    ):
        cursor = self.conn.execute(
            """
            INSERT INTO debts (
                client_id, category_id, global_category_id, title, description, total_amount,
                original_amount, current_amount, interest_rate, installments, installment_amount,
                due_date, debt_type, creditor, paid_installments, status, created_at
            )
            VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                title,
                description,
                current_amount,
                original_amount,
                current_amount,
                interest_rate,
                installments,
                round(float(current_amount) / max(int(installments or 1), 1), 2),
                due_date,
                debt_type,
                creditor,
                paid_installments,
                status,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        debt_id = cursor.lastrowid
        self.recreate_debt_installments(debt_id, client_id, due_date, current_amount, installments, paid_installments, status)
        self.conn.commit()
        return debt_id

    def update_debt(
        self,
        debt_id,
        title,
        description,
        original_amount,
        current_amount,
        interest_rate,
        installments,
        due_date,
        debt_type,
        creditor,
        paid_installments,
        status,
    ):
        debt = self.get_debt(debt_id)
        self.conn.execute(
            """
            UPDATE debts
            SET category_id = NULL, global_category_id = NULL, title = ?, description = ?,
                total_amount = ?, original_amount = ?, current_amount = ?, interest_rate = ?,
                installments = ?, installment_amount = ?, due_date = ?, debt_type = ?,
                creditor = ?, paid_installments = ?, status = ?
            WHERE id = ?
            """,
            (
                title,
                description,
                current_amount,
                original_amount,
                current_amount,
                interest_rate,
                installments,
                round(float(current_amount) / max(int(installments or 1), 1), 2),
                due_date,
                debt_type,
                creditor,
                paid_installments,
                status,
                debt_id,
            ),
        )
        self.recreate_debt_installments(debt_id, debt["client_id"], due_date, current_amount, installments, paid_installments, status)
        self.conn.commit()

    def recreate_debt_installments(self, debt_id, client_id, due_date, current_amount, installments, paid_installments, status):
        self.conn.execute("DELETE FROM debt_installments WHERE debt_id = ?", (debt_id,))
        installments = max(int(installments or 1), 1)
        paid_installments = max(min(int(paid_installments or 0), installments), 0)
        installment_amount = round(float(current_amount) / installments, 2)
        base_date = due_date or datetime.now().date().isoformat()
        for number in range(1, installments + 1):
            installment_date = add_months(base_date, number - 1)
            value = installment_amount
            if number == installments:
                value = round(float(current_amount) - installment_amount * (installments - 1), 2)
            installment_status = "paid" if number <= paid_installments else status
            self.conn.execute(
                """
                INSERT INTO debt_installments (
                    debt_id, client_id, category_id, due_date, amount,
                    installment_number, installments_total, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (debt_id, client_id, None, installment_date, value, number, installments, installment_status),
            )

    def list_debts(self, client_id, month=None):
        params = [client_id]
        where = "WHERE debt_installments.client_id = ?"
        if month:
            where += " AND substr(debt_installments.due_date, 1, 7) = ?"
            params.append(month)
        return self.conn.execute(
            f"""
            SELECT
                debt_installments.id AS installment_id,
                debt_installments.due_date AS installment_due_date,
                debt_installments.amount AS installment_amount,
                debt_installments.installment_number,
                debt_installments.installments_total,
                debt_installments.status AS installment_status,
                debts.*,
                debts.debt_type AS category_name
            FROM debt_installments
            JOIN debts ON debts.id = debt_installments.debt_id
            {where}
            ORDER BY debt_installments.status, debt_installments.due_date, debts.id DESC
            """,
            params,
        ).fetchall()

    def get_debt(self, debt_id):
        return self.conn.execute("SELECT * FROM debts WHERE id = ?", (debt_id,)).fetchone()

    def delete_debt(self, debt_id):
        self.conn.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
        self.conn.commit()

    def backfill_installments(self):
        expenses = self.conn.execute("SELECT * FROM expenses").fetchall()
        for expense in expenses:
            exists = self.conn.execute(
                "SELECT id FROM expense_installments WHERE expense_id = ? LIMIT 1",
                (expense["id"],),
            ).fetchone()
            if not exists:
                category_id = expense["global_category_id"] or expense["category_id"]
                if not self.get_global_category(category_id):
                    category_id = self.ensure_global_category("Outros", "expense")
                self.recreate_expense_installments(
                    expense["id"],
                    expense["client_id"],
                    category_id,
                    expense["expense_date"],
                    expense["original_amount"] or expense["amount"],
                    expense["installments"],
                )
        debts = self.conn.execute("SELECT * FROM debts").fetchall()
        for debt in debts:
            exists = self.conn.execute("SELECT id FROM debt_installments WHERE debt_id = ? LIMIT 1", (debt["id"],)).fetchone()
            if not exists:
                category_id = debt["global_category_id"] or debt["category_id"]
                if category_id and not self.get_global_category(category_id):
                    category_id = self.ensure_global_category("Outros", "expense")
                self.recreate_debt_installments(
                    debt["id"],
                    debt["client_id"],
                    debt["due_date"],
                    debt["current_amount"] or debt["total_amount"],
                    debt["installments"],
                    debt["paid_installments"] if "paid_installments" in debt.keys() else 0,
                    debt["status"],
                )
        self.conn.commit()


def add_months(date_text, months):
    year, month, day = [int(part) for part in date_text.split("-")]
    month += months
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    month_lengths = [31, 29 if is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(day, month_lengths[month - 1])
    return f"{year:04d}-{month:02d}-{day:02d}"


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
