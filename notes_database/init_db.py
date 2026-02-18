#!/usr/bin/env python3
"""Initialize SQLite database for notes_database.

This script is safe to run multiple times:
- Existing tables are preserved (no drops).
- New tables for the notes app are created if missing.
- Seed data is inserted in an idempotent way (INSERT OR IGNORE/UPSERT patterns).

Tables added for the notes app:
- notes
- tags
- note_tags (many-to-many join table)

Useful indexes are created to support listing, filtering, and tag joins.
"""

import os
import sqlite3

DB_NAME = "myapp.db"
DB_USER = "kaviasqlite"  # Not used for SQLite, but kept for consistency
DB_PASSWORD = "kaviadefaultpassword"  # Not used for SQLite, but kept for consistency
DB_PORT = "5000"  # Not used for SQLite, but kept for consistency


def _enable_foreign_keys(cursor: sqlite3.Cursor) -> None:
    """Enable SQLite foreign key enforcement for the current connection."""
    cursor.execute("PRAGMA foreign_keys = ON")


def _create_core_tables(cursor: sqlite3.Cursor) -> None:
    """Create existing/core tables used by this template/container."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # A sample users table exists in this template; we preserve it and optionally use it for seeds.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _create_notes_schema(cursor: sqlite3.Cursor) -> None:
    """Create notes, tags, and note_tags tables with constraints + indexes.

    Notes are independent from users for now, but optionally can be attributed to a user_id.
    Many-to-many relationship is modeled through note_tags.
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            user_id INTEGER NULL,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (note_id, tag_id),
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
        """
    )

    # Helpful indexes for typical app access patterns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_archived ON notes(is_archived)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id)")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_tags_tag_id ON note_tags(tag_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_tags_note_id ON note_tags(note_id)")


def _ensure_notes_title_unique_index(cursor: sqlite3.Cursor) -> None:
    """Create a unique constraint on notes.title via a unique index if not already present.

    We avoid changing an existing table definition (SQLite doesn't support ALTER to add UNIQUE easily),
    so we use a unique index for seed idempotency keyed on title.
    """
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_notes_title ON notes(title)")


def _upsert_app_info(cursor: sqlite3.Cursor) -> None:
    """Insert/replace template app metadata."""
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("project_name", "notes_database"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("version", "0.2.0"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("author", "John Doe"),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
        ("description", "SQLite database for the Notemaster notes app (notes, tags, note_tags)"),
    )


def _ensure_seed_user(cursor: sqlite3.Cursor) -> int:
    """Ensure there is at least one user for seed notes; return its id."""
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (username, email)
        VALUES (?, ?)
        """,
        ("demo", "demo@example.com"),
    )
    cursor.execute("SELECT id FROM users WHERE username = ?", ("demo",))
    row = cursor.fetchone()
    return int(row[0])


def _seed_tags(cursor: sqlite3.Cursor) -> None:
    """Seed a small set of tags for UI testing."""
    seed_tags = [
        ("work", "#3b82f6"),
        ("personal", "#06b6d4"),
        ("ideas", "#64748b"),
        ("urgent", "#ef4444"),
    ]
    for name, color in seed_tags:
        cursor.execute(
            """
            INSERT OR IGNORE INTO tags (name, color)
            VALUES (?, ?)
            """,
            (name, color),
        )


def _seed_notes(cursor: sqlite3.Cursor, user_id: int) -> None:
    """Seed a few notes for UI testing (idempotent by title)."""
    seed_notes = [
        (
            "Welcome to Notemaster",
            "This is a demo note to help you verify the UI end-to-end.\n\n"
            "Try editing this note, adding tags, and searching for keywords like 'demo' or 'Notemaster'.",
            user_id,
            0,
        ),
        (
            "Retro checklist",
            "- Create a new note\n- Add tags\n- Search notes\n- Archive notes\n\n"
            "If you can do all of these, the core UX is working.",
            user_id,
            0,
        ),
        (
            "Meeting notes (sample)",
            "Agenda:\n1) Status updates\n2) Blockers\n3) Next steps\n\n"
            "Action items:\n- Follow up on API integration\n- Confirm database schema supports tags",
            user_id,
            0,
        ),
        (
            "Archived example",
            "This is an archived note to test filtered views.",
            user_id,
            1,
        ),
    ]

    for title, content, uid, is_archived in seed_notes:
        cursor.execute(
            """
            INSERT INTO notes (title, content, user_id, is_archived)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(title) DO UPDATE SET
                content=excluded.content,
                user_id=excluded.user_id,
                is_archived=excluded.is_archived,
                updated_at=CURRENT_TIMESTAMP
            """,
            (title, content, uid, is_archived),
        )


def _seed_note_tags(cursor: sqlite3.Cursor) -> None:
    """Associate seed notes with tags (idempotent through PK(note_id, tag_id))."""
    mappings = {
        "Welcome to Notemaster": ["ideas", "personal"],
        "Retro checklist": ["work", "urgent"],
        "Meeting notes (sample)": ["work"],
        "Archived example": ["personal"],
    }

    for note_title, tag_names in mappings.items():
        cursor.execute("SELECT id FROM notes WHERE title = ?", (note_title,))
        note_row = cursor.fetchone()
        if not note_row:
            continue
        note_id = int(note_row[0])

        for tag_name in tag_names:
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_row = cursor.fetchone()
            if not tag_row:
                continue
            tag_id = int(tag_row[0])

            cursor.execute(
                """
                INSERT OR IGNORE INTO note_tags (note_id, tag_id)
                VALUES (?, ?)
                """,
                (note_id, tag_id),
            )


def _write_connection_files() -> None:
    """Update db_connection.txt and db_visualizer/sqlite.env with the current DB absolute path."""
    current_dir = os.getcwd()
    connection_string = f"sqlite:///{current_dir}/{DB_NAME}"

    try:
        with open("db_connection.txt", "w") as f:
            f.write("# SQLite connection methods:\n")
            f.write(f"# Python: sqlite3.connect('{DB_NAME}')\n")
            f.write(f"# Connection string: {connection_string}\n")
            f.write(f"# File path: {current_dir}/{DB_NAME}\n")
        print("Connection information saved to db_connection.txt")
    except Exception as e:
        print(f"Warning: Could not save connection info: {e}")

    db_path = os.path.abspath(DB_NAME)
    if not os.path.exists("db_visualizer"):
        os.makedirs("db_visualizer", exist_ok=True)
        print("Created db_visualizer directory")

    try:
        with open("db_visualizer/sqlite.env", "w") as f:
            f.write(f'export SQLITE_DB="{db_path}"\n')
        print("Environment variables saved to db_visualizer/sqlite.env")
    except Exception as e:
        print(f"Warning: Could not save environment variables: {e}")


def main() -> None:
    """Initialize database schema and seed data."""
    print("Starting SQLite setup...")

    db_exists = os.path.exists(DB_NAME)
    if db_exists:
        print(f"SQLite database already exists at {DB_NAME}")
        try:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("SELECT 1")
            conn.close()
            print("Database is accessible and working.")
        except Exception as e:
            print(f"Warning: Database exists but may be corrupted: {e}")
    else:
        print("Creating new SQLite database...")

    conn = sqlite3.connect(DB_NAME)
    try:
        cursor = conn.cursor()
        _enable_foreign_keys(cursor)

        _create_core_tables(cursor)
        _create_notes_schema(cursor)
        _ensure_notes_title_unique_index(cursor)

        _upsert_app_info(cursor)

        # Seed data for initial UI testing
        demo_user_id = _ensure_seed_user(cursor)
        _seed_tags(cursor)
        _seed_notes(cursor, demo_user_id)
        _seed_note_tags(cursor)

        conn.commit()

        # Stats
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM notes")
        notes_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tags")
        tags_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM note_tags")
        note_tags_count = cursor.fetchone()[0]

        _write_connection_files()

        print("\nSQLite setup complete!")
        print(f"Database: {DB_NAME}")
        print(f"Location: {os.getcwd()}/{DB_NAME}")
        print("")
        print("To use with Node.js viewer, run: source db_visualizer/sqlite.env")
        print("")
        print("Database statistics:")
        print(f"  Tables: {table_count}")
        print(f"  Notes: {notes_count}")
        print(f"  Tags: {tags_count}")
        print(f"  Note-Tag relations: {note_tags_count}")

        # If sqlite3 CLI is available, show how to use it
        try:
            import subprocess

            result = subprocess.run(["which", "sqlite3"], capture_output=True, text=True)
            if result.returncode == 0:
                print("")
                print("SQLite CLI is available. You can also use:")
                print(f"  sqlite3 {DB_NAME}")
        except Exception:
            pass

        print("\nScript completed successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
