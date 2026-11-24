import sqlite3
import unicodedata
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "diamond.db"

ALLOWED_STATS = {"hr", "avg", "obp", "slg", "ops", "ops_plus", "war", "pa", "g"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    player_id   INTEGER PRIMARY KEY,   
    full_name   TEXT NOT NULL,
    bbref_id    TEXT,                  
    birth_year  INTEGER
);

CREATE TABLE IF NOT EXISTS batting_seasons (
    player_id   INTEGER NOT NULL,
    season      INTEGER NOT NULL,
    team        TEXT NOT NULL,         
    g           INTEGER,
    pa          INTEGER,
    hr          INTEGER,
    avg         REAL,
    obp         REAL,
    slg         REAL,
    ops         REAL,
    ops_plus    REAL,                  
    war         REAL,                  
    PRIMARY KEY (player_id, season, team),
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE INDEX IF NOT EXISTS idx_batting_season ON batting_seasons(season);
CREATE INDEX IF NOT EXISTS idx_batting_team_season ON batting_seasons(team, season);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# this should fix the "julio rodriguez vs rodríguez" problem
def normalize_name(text: str) -> str:
    fixed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(ch for ch in fixed if not unicodedata.combining(ch))


def find_players(name: str, limit: int = 5) -> list[dict]:
    normalized_name = normalize_name(name)
    if not normalized_name:
        return []

    with get_connection() as conn:
        rows = conn.execute("SELECT player_id, full_name FROM players").fetchall()

    return [
        {"player_id": row["player_id"], "full_name": row["full_name"]}
        for row in rows
        if normalized_name in normalize_name(row["full_name"])
    ]


def get_player_stats(player_id: int, season: int | None = None) -> list[dict]:
    sql = """
        SELECT p.full_name, b.season, b.team, b.g, b.pa, b.hr,
               b.avg, b.obp, b.slg, b.ops, b.ops_plus, b.war
        FROM batting_seasons b
        JOIN players p ON p.player_id = b.player_id
        WHERE b.player_id = ?
    """
    params: list = [player_id]
    if season is not None:
        sql += " AND b.season = ?"
        params.append(season)
    sql += " ORDER BY b.season, b.team"
    with get_connection() as conn:
        return _rows_to_dicts(conn.execute(sql, params).fetchall())


def get_leaders(stat: str, season: int, limit: int = 10, min_pa: int = 300) -> list[dict]:
    if stat not in ALLOWED_STATS:
        raise ValueError(f"Unsupported stat: {stat}")
    sql = f"""
        SELECT p.full_name, b.team, b.{stat} AS value, b.pa
        FROM batting_seasons b
        JOIN players p ON p.player_id = b.player_id
        WHERE b.season = ? AND b.pa >= ? AND b.{stat} IS NOT NULL
        ORDER BY b.{stat} DESC
        LIMIT ?
    """
    with get_connection() as conn:
        return _rows_to_dicts(conn.execute(sql, (season, min_pa, limit)).fetchall())


def get_team_season(team: str, season: int, db_path: Path = DB_PATH) -> list[dict]:
    normalized_team = team.strip().upper()
    sql = """
        SELECT p.full_name, b.team, b.g, b.pa, b.hr, b.avg, b.obp, b.slg, b.ops, b.war
        FROM batting_seasons b
        JOIN players p ON p.player_id = b.player_id
        WHERE UPPER(b.team) = ? AND b.season = ?
        ORDER BY b.pa DESC
    """
    with get_connection(db_path) as conn:
        return _rows_to_dicts(conn.execute(sql, (normalized_team, season)).fetchall())


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH}")
