from fastmcp import FastMCP
import mcp.types as types
import os
import io
import base64
from dotenv import load_dotenv
import sqlite3

# Load environment variables from .env file
load_dotenv()

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Get the absolute path to the directory where main.py is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "expenses.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create user_tokens if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL
        )
    """)
    
    # Create expenses if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
    """)
    
    # Add user_id to expenses if missing
    cursor.execute("PRAGMA table_info(expenses)")
    columns = [info['name'] for info in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN user_id TEXT")
        
    conn.commit()
    conn.close()

# Initialize the database and schemas on startup
init_db()

# -----------------------
# USER AUTH & REGISTRATION
# -----------------------

async def get_user_id(token: str) -> str:
    """
    Validates the token. 
    If the token is new, it automatically registers it as a new user (Zero Touch).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_tokens WHERE token = ?", (token,))
    row = cursor.fetchone()
    
    if row:
        # User already exists
        conn.close()
        return row["user_id"]
    else:
        # NEW USER: Automatically register them on the fly!
        # We use the token itself (or a portion of it) as their user_id
        new_user_id = f"auto_{token[:10]}" 
        
        cursor.execute("INSERT INTO user_tokens (token, user_id) VALUES (?, ?)", (token, new_user_id))
        conn.commit()
        conn.close()
        return new_user_id

# -----------------------
# MCP INIT
# -----------------------
mcp = FastMCP("ExpenseTracker")

# -----------------------
# ADD EXPENSE
# -----------------------
@mcp.tool()
async def add_expense(
    token: str = "",
    date: str = "",
    amount: float = 0.0,
    category: str = "",
    subcategory: str = "",
    note: str = ""
):
    """
    Add a new expense. 
    Requires a valid secret 'token' for authentication.
    """
    user_id = await get_user_id(token)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (user_id, date, amount, category, subcategory, note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, date, amount, category, subcategory, note))
    conn.commit()
    
    # Fetch inserted row to return it
    cursor.execute("SELECT * FROM expenses WHERE id = ?", (cursor.lastrowid,))
    inserted_row = dict(cursor.fetchone())
    conn.close()
    
    return {
        "status": "success",
        "message": f"Added expense for user: {user_id}",
        "data": [inserted_row]
    }

# -----------------------
# LIST EXPENSES
# -----------------------
@mcp.tool()
async def list_expenses(start_date: str, end_date: str, token: str = ""):
    """
    List expenses for a specific period.
    Requires a valid secret 'token' for authentication.
    """
    user_id = await get_user_id(token)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM expenses 
        WHERE user_id = ? AND date >= ? AND date <= ?
        ORDER BY id ASC
    """, (user_id, start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# -----------------------
# SUMMARY + GRAPH
# -----------------------
@mcp.tool()
async def summarize(start_date: str, end_date: str, token: str = ""):
    """
    Get a spending summary and graph.
    Requires a valid secret 'token' for authentication.
    """
    user_id = await get_user_id(token)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, amount FROM expenses 
        WHERE user_id = ? AND date >= ? AND date <= ?
    """, (user_id, start_date, end_date))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "No expenses found for this period."

    # -----------------------
    # PROCESS DATA
    # -----------------------
    summary = {}
    for r in rows:
        summary[r["category"]] = summary.get(r["category"], 0) + r["amount"]

    total_amount = sum(summary.values())

    # -----------------------
    # ADVICE
    # -----------------------
    advice = f"### 📊 Expense Summary (User: {user_id})\n"
    advice += f"**Total Spending: ₹{total_amount:.2f}**\n\n"

    for cat, amt in summary.items():
        pct = (amt / total_amount * 100) if total_amount else 0
        advice += f"- {cat}: ₹{amt:.2f} ({pct:.1f}%)\n"

    # -----------------------
    # GRAPH (DONUT STYLE)
    # -----------------------
    NAVY_BG = "#020617"
    CYAN = "#38bdf8"
    INDIGO = "#6366f1"
    TEXT_GRAY = "#cbd5e1"

    categories = list(summary.keys())
    amounts = list(summary.values())

    plt.figure(figsize=(8, 8), facecolor=NAVY_BG)
    ax = plt.gca()
    ax.set_facecolor(NAVY_BG)

    colors = [CYAN, INDIGO, "#4f46e5", "#1e293b", "#334155", "#475569"]

    wedges, texts, autotexts = plt.pie(
        amounts,
        labels=categories,
        autopct='%1.1f%%',
        startangle=140,
        colors=colors,
        pctdistance=0.85,
        wedgeprops=dict(width=0.4, edgecolor=NAVY_BG)
    )

    plt.setp(autotexts, size=11, weight="bold", color=NAVY_BG)
    plt.setp(texts, size=13, weight="bold", color=TEXT_GRAY)

    plt.title("Expense Summary", fontsize=18, fontweight='bold', color=CYAN)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    plt.close()
    buf.seek(0)

    image_base64 = base64.b64encode(buf.read()).decode('utf-8')

    return [
        types.TextContent(type="text", text=advice),
        types.ImageContent(type="image", data=image_base64, mimeType="image/png")
    ]


# -----------------------
# CATEGORIES RESOURCE
# -----------------------
@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    return {
        "categories": [
            "Food",
            "Transport",
            "Shopping",
            "Education",
            "Bills",
            "Health",
            "Other"
        ]
    }

# -----------------------
# RUN SERVER
# -----------------------
if __name__ == "__main__":
    # Render and other cloud hosts provide a PORT environment variable
    # We still use this as a fallback even if running locally.
    port = int(os.getenv("PORT", 8000))
    # Use host="0.0.0.0" so the server is accessible from the internet/local network
    mcp.run(transport="sse", host="0.0.0.0", port=port)