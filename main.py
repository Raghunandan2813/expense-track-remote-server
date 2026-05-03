from fastmcp import FastMCP
import mcp.types as types
import os
import io
import base64
from dotenv import load_dotenv
import httpx
import json
import secrets

# Load environment variables from .env file
load_dotenv()

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# -----------------------
# SUPABASE CONFIG
# -----------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
# Ensure the URL is just the base (e.g., https://xyz.supabase.co)
if "/rest/v1" in SUPABASE_URL:
    SUPABASE_URL = SUPABASE_URL.split("/rest/v1")[0]

SUPABASE_KEY = os.getenv("SUPABASE_KEY")



# -----------------------
# USER AUTH & REGISTRATION
# -----------------------

async def get_user_id(token: str) -> str:
    """
    Validates the token. 
    If the token is new, it automatically registers it as a new user (Zero Touch).
    """
    params = {"token": f"eq.{token}", "select": "user_id"}
    res = await supabase_request("GET", "user_tokens", params=params)
    
    if res:
        # User already exists
        return res[0]["user_id"]
    else:
        # NEW USER: Automatically register them on the fly!
        # We use the token itself (or a portion of it) as their user_id
        new_user_id = f"auto_{token[:10]}" 
        
        data = {
            "token": token,
            "user_id": new_user_id
        }
        await supabase_request("POST", "user_tokens", data=data)
        return new_user_id


# -----------------------
# SUPABASE REQUEST HANDLER
# -----------------------

async def supabase_request(method: str, table: str, params: dict = None, data: dict = None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("Configuration Error: Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
        
    url = f"{SUPABASE_URL}/rest/v1/{table}"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    async with httpx.AsyncClient() as client:
        if method.upper() == "POST":
            resp = await client.post(url, headers=headers, json=data)
        elif method.upper() == "GET":
            resp = await client.get(url, headers=headers, params=params)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if resp.status_code >= 400:
            try:
                err_data = resp.json()
            except:
                err_data = resp.text
            raise Exception(f"Supabase Error ({resp.status_code}): {err_data}")
            
        return resp.json()

# -----------------------
# MCP INIT
# -----------------------
mcp = FastMCP("ExpenseTracker")

# -----------------------
# ADD EXPENSE
# -----------------------
@mcp.tool()
async def add_expense(
    token: str,
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = ""
):
    """
    Add a new expense. 
    Requires a valid secret 'token' for authentication.
    """
    user_id = await get_user_id(token)
    
    data = {
        "user_id": user_id,
        "date": date,
        "amount": amount,
        "category": category,
        "subcategory": subcategory,
        "note": note
    }
    
    res = await supabase_request("POST", "expenses", data=data)
    return {
        "status": "success",
        "message": f"Added expense for user: {user_id}",
        "data": res
    }

# -----------------------
# LIST EXPENSES
# -----------------------
@mcp.tool()
async def list_expenses(token: str, start_date: str, end_date: str):
    """
    List expenses for a specific period.
    Requires a valid secret 'token' for authentication.
    """
    user_id = await get_user_id(token)
    
    params = {
        "user_id": f"eq.{user_id}",
        "date": f"and(gte.{start_date},lte.{end_date})",
        "order": "id.asc"
    }
    
    return await supabase_request("GET", "expenses", params=params)

# -----------------------
# SUMMARY + GRAPH
# -----------------------
@mcp.tool()
async def summarize(token: str, start_date: str, end_date: str):
    """
    Get a spending summary and graph.
    Requires a valid secret 'token' for authentication.
    """
    user_id = await get_user_id(token)
    
    params = {
        "user_id": f"eq.{user_id}",
        "date": f"and(gte.{start_date},lte.{end_date})",
        "select": "category,amount"
    }
    
    rows = await supabase_request("GET", "expenses", params=params)

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
    import os
    # Render and other cloud hosts provide a PORT environment variable
    port = int(os.getenv("PORT", 8000))
    # Use host="0.0.0.0" so the server is accessible from the internet
    mcp.run(transport="sse", host="0.0.0.0", port=port)