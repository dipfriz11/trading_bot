import sqlite3
import threading


class SQLiteStorage:

    def __init__(self, db_path="bot.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS symbol_state (
                        symbol          TEXT PRIMARY KEY,
                        cycle_active    INTEGER,
                        bias            TEXT,
                        long_size       REAL,
                        short_size      REAL,
                        cycle_number    INTEGER,
                        blocked         INTEGER,
                        last_signal     TEXT,
                        last_signal_time REAL
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def load_all_states(self) -> dict:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute("SELECT * FROM symbol_state")
                rows = cursor.fetchall()
            finally:
                conn.close()

        result = {}
        for row in rows:
            result[row["symbol"]] = {
                "cycle_active":     bool(row["cycle_active"]),
                "bias":             row["bias"],
                "long_size":        row["long_size"],
                "short_size":       row["short_size"],
                "cycle_number":     row["cycle_number"],
                "blocked":          bool(row["blocked"]),
                "last_signal":      row["last_signal"],
                "last_signal_time": row["last_signal_time"],
            }
        return result

    def save_state(self, symbol: str, state: dict):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO symbol_state (
                        symbol, cycle_active, bias, long_size, short_size,
                        cycle_number, blocked, last_signal, last_signal_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        cycle_active     = excluded.cycle_active,
                        bias             = excluded.bias,
                        long_size        = excluded.long_size,
                        short_size       = excluded.short_size,
                        cycle_number     = excluded.cycle_number,
                        blocked          = excluded.blocked,
                        last_signal      = excluded.last_signal,
                        last_signal_time = excluded.last_signal_time
                """, (
                    symbol,
                    int(state["cycle_active"]),
                    state["bias"],
                    state["long_size"],
                    state["short_size"],
                    state["cycle_number"],
                    int(state["blocked"]),
                    state["last_signal"],
                    state["last_signal_time"],
                ))
                conn.commit()
            finally:
                conn.close()
