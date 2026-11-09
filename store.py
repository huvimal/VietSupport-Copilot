"""SQLite-backed fictional orders and one-time cancellation approvals."""
import secrets
import sqlite3
import time
from contextlib import contextmanager


class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY, customer TEXT NOT NULL, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    token TEXT PRIMARY KEY, customer TEXT NOT NULL, order_id TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                INSERT OR IGNORE INTO orders VALUES
                    ('VN1001', 'demo-a', 'processing'),
                    ('VN1002', 'demo-a', 'shipped'),
                    ('VN2001', 'demo-b', 'processing');
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def status(self, customer, order_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT status FROM orders WHERE id = ? AND customer = ?", (order_id, customer)
            ).fetchone()
        return row[0] if row else None

    def propose(self, customer, order_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM orders WHERE id = ? AND customer = ?", (order_id, customer)
            ).fetchone()
            status = row[0] if row else None
            if status != "processing":
                return status, None
            now = time.time()
            db.execute("DELETE FROM approvals WHERE expires_at <= ?", (now,))
            token = secrets.token_urlsafe(24)
            db.execute("INSERT INTO approvals VALUES (?, ?, ?, ?)", (token, customer, order_id, now + 300))
            return status, token

    def confirm(self, customer, token):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT order_id FROM approvals WHERE token = ? AND customer = ? AND expires_at > ?",
                (token, customer, time.time()),
            ).fetchone()
            if row is None:
                return None
            order_id = row[0]
            changed = db.execute(
                "UPDATE orders SET status = 'cancelled' WHERE id = ? AND customer = ? AND status = 'processing'",
                (order_id, customer),
            ).rowcount
            db.execute("DELETE FROM approvals WHERE order_id = ? AND customer = ?", (order_id, customer))
            return order_id if changed else None
