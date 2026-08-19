"""
Camada de persistência (SQLite). Guarda usuários, status de assinatura e pagamentos.
Usa sqlite3 puro (sem ORM) para manter o projeto simples e sem dependências extras.
"""
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

from bot.config import settings


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Cria as tabelas caso não existam. Deve ser chamado uma vez ao iniciar o serviço."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                subscription_end TEXT,
                status TEXT DEFAULT 'never',   -- never | active | expired
                warned INTEGER DEFAULT 0,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                mp_payment_id TEXT UNIQUE,
                amount REAL,
                status TEXT DEFAULT 'pending', -- pending | approved | rejected
                created_at TEXT
            )
            """
        )


def create_user_if_not_exists(telegram_id: int, username: str, full_name: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, status, created_at)
            VALUES (?, ?, ?, 'never', ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (telegram_id, username, full_name, datetime.now().isoformat()),
        )


def get_user(telegram_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_users():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY subscription_end").fetchall()
        return [dict(r) for r in rows]


def get_all_active_users():
    """Usuários que estão (ou estavam) ativos e precisam ser checados pelo agendador."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE status = 'active' AND subscription_end IS NOT NULL"
        ).fetchall()
        return [dict(r) for r in rows]


def set_user_status(telegram_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET status = ? WHERE telegram_id = ?", (status, telegram_id)
        )


def mark_user_warned(telegram_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET warned = 1 WHERE telegram_id = ?", (telegram_id,)
        )


def extend_subscription(telegram_id: int, days: int) -> datetime:
    """
    Estende a assinatura a partir de hoje ou da data de expiração atual (o que for maior),
    permitindo renovações antecipadas sem perder dias já pagos.
    """
    user = get_user(telegram_id)
    now = datetime.now()

    if user and user.get("subscription_end"):
        current_end = datetime.fromisoformat(user["subscription_end"])
        base = current_end if current_end > now else now
    else:
        base = now

    new_end = base + timedelta(days=days)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, subscription_end, status, warned, created_at)
            VALUES (?, ?, 'active', 0, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                subscription_end = excluded.subscription_end,
                status = 'active',
                warned = 0
            """,
            (telegram_id, new_end.isoformat(), now.isoformat()),
        )
    return new_end


def register_payment(telegram_id: int, mp_payment_id, amount: float):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO payments (telegram_id, mp_payment_id, amount, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (telegram_id, str(mp_payment_id), amount, datetime.now().isoformat()),
        )


def get_payment_by_mp_id(mp_payment_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE mp_payment_id = ?", (str(mp_payment_id),)
        ).fetchone()
        return dict(row) if row else None


def update_payment_status(mp_payment_id, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE payments SET status = ? WHERE mp_payment_id = ?",
            (status, str(mp_payment_id)),
        )
