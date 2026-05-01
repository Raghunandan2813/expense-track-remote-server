def init_db():
    try:
        import sqlite3

        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)

        print("✅ Database initialized successfully")

    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise