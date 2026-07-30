"""
تست منطق CRUD (insert/upsert/select/delete) با sqlite3 استاندارد پایتون.

⚠️ نکته: چون در این sandbox امکان pip install برای asyncpg نبود، این فایل
از SQL *معادل* با SQLite تست می‌کنه، نه عیناً همون رشته‌ی SQL که تو
database/repository.py برای Postgres نوشته شده (که از $1/$2 و NOW() استفاده می‌کنه
به‌جای ? و datetime('now')). یعنی این تست فقط درستیِ *منطق* upsert/query رو
تضمین می‌کنه (که بین SQLite و Postgres یکسانه)، نه دقیقاً syntax فایل واقعی.
تست نهایی و واقعی باید با یه دیتابیس Postgres/Neon واقعی انجام بشه.
"""
import json
import sqlite3
import sys

from game.state import Game, Team, Role

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id     TEXT PRIMARY KEY,
    chat_id     INTEGER NOT NULL,
    host_id     INTEGER NOT NULL,
    status      TEXT NOT NULL,
    state_json  TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_games_chat_id ON games(chat_id);
"""


def check(cond, msg):
    if not cond:
        print(f"❌ FAIL: {msg}")
        sys.exit(1)
    print(f"✅ OK: {msg}")


def main():
    conn = sqlite3.connect(":memory:")
    conn.executescript(_SQLITE_SCHEMA)
    conn.commit()

    g = Game(game_id="abc123", chat_id=555, host_id=1, team_size_mode=4)
    g.join_slot(1, "Ali", Team.RED, Role.SPYMASTER, slot=0)
    g.join_slot(2, "Reza", Team.RED, Role.OPERATIVE, slot=0)
    g.join_slot(3, "Sara", Team.BLUE, Role.SPYMASTER, slot=0)
    g.join_slot(4, "Neda", Team.BLUE, Role.OPERATIVE, slot=0)

    def upsert(game: Game):
        conn.execute(
            """
            INSERT INTO games (game_id, chat_id, host_id, status, state_json, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(game_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                host_id = excluded.host_id,
                status = excluded.status,
                state_json = excluded.state_json,
                updated_at = datetime('now')
            """,
            (game.game_id, game.chat_id, game.host_id, game.status.value, game.to_json()),
        )
        conn.commit()

    # --- تست insert ---
    upsert(g)
    row = conn.execute("SELECT state_json FROM games WHERE game_id = ?", (g.game_id,)).fetchone()
    check(row is not None, "بازی باید بعد از insert پیدا بشه")
    g2 = Game.from_json(row[0])
    check(len(g2.players) == 4, "هر ۴ بازیکن باید بعد از بارگذاری برگردن")

    # --- تست upsert ---
    g2.start_game(json.load(open("data/words_fa.json", encoding="utf-8")))
    upsert(g2)

    count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    check(count == 1, "با game_id تکراری نباید ردیف جدید بسازه (باید آپدیت بشه)")

    row = conn.execute("SELECT state_json FROM games WHERE game_id = ?", (g.game_id,)).fetchone()
    g3 = Game.from_json(row[0])
    check(len(g3.board) == 25, "بعد آپدیت باید نسخه‌ی جدید (با برد ۲۵تایی) خونده بشه")

    # --- تست load_active_game_by_chat ---
    row2 = conn.execute(
        """
        SELECT state_json FROM games
        WHERE chat_id = ? AND status != 'finished'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (555,),
    ).fetchone()
    check(row2 is not None, "بازی فعال این چت باید پیدا بشه")

    # --- تست delete ---
    conn.execute("DELETE FROM games WHERE game_id = ?", (g.game_id,))
    conn.commit()
    row3 = conn.execute("SELECT * FROM games WHERE game_id = ?", (g.game_id,)).fetchone()
    check(row3 is None, "بعد از حذف نباید دیگه پیدا بشه")

    print("\n🎉 همه‌ی تست‌های منطق دیتابیس (معادل SQLite) رد شدن.")
    print("⚠️ یادت باشه: تست نهایی با Postgres/Neon واقعی هنوز لازمه.")


if __name__ == "__main__":
    main()
