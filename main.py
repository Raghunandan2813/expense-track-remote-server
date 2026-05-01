from fastmcp import FastMCP
import os
import aiosqlite
import sqlite3
import json
import tempfile

# ==============================
# SAFE PATH (WORKS EVERYWHERE)
# ==============================
BASE_DIR = tempfile.gettempdir()  # 🔥 always writable
DB_PATH = os.path.join(BASE_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

print(f"📁 Using DB path: {DB_PATH}")

# ==============================
# MCP SERVER
# ==============================
server = FastMCP("ExpenseTracker")

# ==============================
# DB INIT CONTROL
# ==============================
_db_initialized = False

def init_db():
    try:
        os.makedirs(BASE_DIR, exist_ok=True)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)

        print("✅ Database initialized")

    except Exception as e:
        print(f"❌ DB INIT ERROR: {e}")
        raise

def ensure_db():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True

# ==============================
# TOOLS
# ==============================

@server.tool()
async def add_expense(date: str, amount: float, category: str, subcategory: str = "", note: str = ""):
    """Add a new expense entry."""
    try:
        ensure_db()

        async with aiosqlite.connect(DB_PATH, timeout=10) as db:
            await db.execute("PRAGMA journal_mode=WAL")

            cursor = await db.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?, ?, ?, ?, ?)",
                (date, amount, category, subcategory, note)
            )

            await db.commit()

            return {
                "status": "success",
                "id": cursor.lastrowid,
                "message": "Expense added successfully"
            }

    except Exception as e:
        return {"status": "error", "message": str(e)}


@server.tool()
async def list_expenses(start_date: str, end_date: str):
    """List expenses between two dates."""
    try:
        ensure_db()

        async with aiosqlite.connect(DB_PATH, timeout=10) as db:
            cursor = await db.execute("""
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
            """, (start_date, end_date))

            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]

            return [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        return {"status": "error", "message": str(e)}


@server.tool()
async def summarize(start_date: str, end_date: str, category: str | None = None):
    """Summarize expenses."""
    try:
        ensure_db()

        async with aiosqlite.connect(DB_PATH, timeout=10) as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT category, SUM(amount) as total, COUNT(*) as count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total DESC"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            if not rows:
                return {"content": ["No expenses found."]}

            return {
                "content": [
                    f"{row['category']} → ₹{row['total']} ({row['count']} entries)"
                    for row in rows
                ]
            }

    except Exception as e:
        return {"content": [f"Error: {str(e)}"]}

# ==============================
# RESOURCE
# ==============================

@server.resource("expense:///categories", mime_type="application/json")
def categories():
    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other"
        ]
    }

    try:
        if os.path.exists(CATEGORIES_PATH):
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return json.dumps(default_categories, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})

# ==============================
# RUN SERVER
# ==============================
if __name__ == "__main__":
    print("🚀 Starting MCP Expense Tracker Server...")
    ensure_db()

    server.run(
        transport="http",
        host="0.0.0.0",
        port=8000
    )