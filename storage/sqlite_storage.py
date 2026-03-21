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
                        last_signal_time REAL,
                        cycle_target_profit REAL
                    )
                """)
                try:
                    conn.execute("ALTER TABLE symbol_state ADD COLUMN cycle_target_profit REAL")
                except:
                    pass
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS profit_state (
                        symbol           TEXT PRIMARY KEY,
                        cycle_number     INTEGER,
                        entry_fees       REAL,
                        funding_total    REAL,
                        cycle_start_time INTEGER,
                        updated_at       INTEGER
                    )
                """)
                try:
                    conn.execute("ALTER TABLE profit_state ADD COLUMN cycle_start_time INTEGER")
                except:
                    pass
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS target_profit_overrides (
                        symbol       TEXT,
                        cycle_number INTEGER,
                        value        REAL,
                        PRIMARY KEY (symbol, cycle_number)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS symbols (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol      TEXT NOT NULL,
                        exchange    TEXT NOT NULL,
                        account     TEXT NOT NULL,
                        strategy    TEXT NOT NULL,
                        active      INTEGER NOT NULL DEFAULT 0,
                        created_at  INTEGER
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
                "cycle_active":        bool(row["cycle_active"]),
                "bias":                row["bias"],
                "long_size":           row["long_size"],
                "short_size":          row["short_size"],
                "cycle_number":        row["cycle_number"],
                "blocked":             bool(row["blocked"]),
                "last_signal":         row["last_signal"],
                "last_signal_time":    row["last_signal_time"],
                "cycle_target_profit": row["cycle_target_profit"],
            }
        return result

    def save_state(self, symbol: str, state: dict):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO symbol_state (
                        symbol, cycle_active, bias, long_size, short_size,
                        cycle_number, blocked, last_signal, last_signal_time,
                        cycle_target_profit
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        cycle_active        = excluded.cycle_active,
                        bias                = excluded.bias,
                        long_size           = excluded.long_size,
                        short_size          = excluded.short_size,
                        cycle_number        = excluded.cycle_number,
                        blocked             = excluded.blocked,
                        last_signal         = excluded.last_signal,
                        last_signal_time    = excluded.last_signal_time,
                        cycle_target_profit = excluded.cycle_target_profit
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
                    state.get("cycle_target_profit"),
                ))
                conn.commit()
            finally:
                conn.close()

    def save_profit_state(self, symbol: str, cycle_number: int, entry_fees: float, funding_total: float, cycle_start_time: int = None):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO profit_state (
                        symbol, cycle_number, entry_fees, funding_total, cycle_start_time, updated_at
                    ) VALUES (?, ?, ?, ?, ?, strftime('%s','now'))
                    ON CONFLICT(symbol) DO UPDATE SET
                        cycle_number     = excluded.cycle_number,
                        entry_fees       = excluded.entry_fees,
                        funding_total    = excluded.funding_total,
                        cycle_start_time = excluded.cycle_start_time,
                        updated_at       = excluded.updated_at
                """, (symbol, cycle_number, entry_fees, funding_total, cycle_start_time))
                conn.commit()
            finally:
                conn.close()

    def get_profit_state(self, symbol: str) -> dict | None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    "SELECT * FROM profit_state WHERE symbol = ?", (symbol,)
                )
                row = cursor.fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return {
            "cycle_number":    row["cycle_number"],
            "entry_fees":      row["entry_fees"],
            "funding_total":   row["funding_total"],
            "cycle_start_time": row["cycle_start_time"],
            "updated_at":      row["updated_at"],
        }

    def save_target_profit(self, symbol: str, cycle_number: int, value: float):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO target_profit_overrides (symbol, cycle_number, value)
                    VALUES (?, ?, ?)
                    ON CONFLICT(symbol, cycle_number) DO UPDATE SET value = excluded.value
                """, (symbol, int(cycle_number), float(value)))
                conn.commit()
            finally:
                conn.close()

    def load_target_profits(self, symbol: str) -> dict:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    "SELECT cycle_number, value FROM target_profit_overrides WHERE symbol = ?",
                    (symbol,)
                )
                rows = cursor.fetchall()
            finally:
                conn.close()
        return {row["cycle_number"]: row["value"] for row in rows}

    def create_symbol(self, symbol: str, exchange: str, account: str, strategy: str):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO symbols (symbol, exchange, account, strategy, active, created_at)
                    VALUES (?, ?, ?, ?, 0, strftime('%s','now'))
                """, (symbol, exchange, account, strategy))
                conn.commit()
            finally:
                conn.close()

    def activate_symbol(self, symbol: str):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("UPDATE symbols SET active = 1 WHERE symbol = ?", (symbol,))
                conn.commit()
            finally:
                conn.close()

    def deactivate_symbol(self, symbol: str):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("UPDATE symbols SET active = 0 WHERE symbol = ?", (symbol,))
                conn.commit()
            finally:
                conn.close()

    def get_symbol(self, symbol: str) -> dict | None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    "SELECT symbol, exchange, account, strategy, active FROM symbols WHERE symbol = ?",
                    (symbol,)
                )
                row = cursor.fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return {
            "symbol":   row["symbol"],
            "exchange": row["exchange"],
            "account":  row["account"],
            "strategy": row["strategy"],
            "active":   bool(row["active"]),
        }

    def get_active_symbols(self) -> list:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    "SELECT symbol, exchange, account, strategy, active FROM symbols WHERE active = 1"
                )
                rows = cursor.fetchall()
            finally:
                conn.close()
        return [
            {
                "symbol":   row["symbol"],
                "exchange": row["exchange"],
                "account":  row["account"],
                "strategy": row["strategy"],
                "active":   bool(row["active"]),
            }
            for row in rows
        ]
