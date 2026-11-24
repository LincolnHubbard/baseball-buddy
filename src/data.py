import pandas as pd
from pybaseball import batting_stats_bref

from src.database import get_connection, init_db

BATTING_COLUMNS = {
    "mlbID": "player_id",
    "Name": "full_name",
    "Tm": "team",
    "G": "g",
    "PA": "pa",
    "HR": "hr",
    "BA": "avg",
    "OBP": "obp",
    "SLG": "slg",
    "OPS": "ops",
}

# without this, the database will think LAA and LAD are the same team
CITY_LEAGUE_TO_BBREF = {
    ("Los Angeles", "AL"): "LAA",
    ("Los Angeles", "NL"): "LAD",
    ("Chicago", "AL"): "CHW",
    ("Chicago", "NL"): "CHC",
    ("New York", "AL"): "NYY",
    ("New York", "NL"): "NYM",
}

TEAM_NAME_TO_BBREF = {
    "Arizona": "ARI",
    "Atlanta": "ATL",
    "Baltimore": "BAL",
    "Boston": "BOS",
    "Cincinnati": "CIN",
    "Cleveland": "CLE",
    "Colorado": "COL",
    "Detroit": "DET",
    "Houston": "HOU",
    "Kansas City": "KCR",
    "Miami": "MIA",
    "Milwaukee": "MIL",
    "Minnesota": "MIN",
    "Oakland": "OAK",
    "Philadelphia": "PHI",
    "Pittsburgh": "PIT",
    "San Diego": "SDP",
    "San Francisco": "SFG",
    "Seattle": "SEA",
    "St. Louis": "STL",
    "Tampa Bay": "TBR",
    "Texas": "TEX",
    "Toronto": "TOR",
    "Washington": "WSN",
}


def resolve_bbref_codes(raw_team: object, lev: str = "") -> list[str]:
    if not raw_team or not isinstance(raw_team, str):
        return []

    lev_upper = lev.upper()
    league = "AL" if "AL" in lev_upper else ("NL" if "NL" in lev_upper else "")
    codes: list[str] = []

    for part in raw_team.split(","):
        token = part.strip()
        if not token:
            continue
        upper = token.upper()

        if len(upper) == 3 and upper[0].isdigit() and upper.endswith("TM"):
            continue
        if league and (token, league) in CITY_LEAGUE_TO_BBREF:
            code = CITY_LEAGUE_TO_BBREF[(token, league)]
        elif token in TEAM_NAME_TO_BBREF:
            code = TEAM_NAME_TO_BBREF[token]
        else:
            code = upper

        if code not in codes:
            codes.append(code)

    return codes


def fix_name(name):
    if not isinstance(name, str):
        return name
    name = name.rstrip("*#").strip()  # these are unneeded bbref markers
    try:
        return name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def fetch_season(season: int) -> pd.DataFrame:
    df = batting_stats_bref(season)
    df = df[df["Lev"].astype(str).str.startswith("Maj")]  # in case I forgot, 'Lev' refers to MLB/AAA/AA, etc.
    df = df.dropna(subset=["mlbID"])

    lev_series = df["Lev"].astype(str).tolist()
    df = df[list(BATTING_COLUMNS)].rename(columns=BATTING_COLUMNS)
    df["full_name"] = df["full_name"].map(fix_name)
    df["player_id"] = df["player_id"].astype(int)
    df["season"] = season
    df["ops_plus"] = None
    df["war"] = None

    clean_df = df.astype(object).where(pd.notna(df), None)
    rows: list[dict] = []
    for record, lev in zip(clean_df.to_dict("records"), lev_series):
        for code in resolve_bbref_codes(record.get("team"), lev):
            item = dict(record)
            item["team"] = code
            rows.append(item)

    return pd.DataFrame(rows)


def load_batting_seasons(start: int, end: int) -> int:
    init_db()
    df = pd.concat(
        [fetch_season(s) for s in range(start, end + 1)],
        ignore_index=True,
    )

    players = df[["player_id", "full_name"]].drop_duplicates("player_id")
    rows = df.astype(object).where(pd.notna(df), None).to_dict("records")

    with get_connection() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO players (player_id, full_name) VALUES (?, ?)",
            list(players.itertuples(index=False, name=None)),
        )
        conn.executemany(
            """INSERT OR REPLACE INTO batting_seasons
               (player_id, season, team, g, pa, hr, avg, obp, slg, ops, ops_plus, war)
               VALUES (:player_id, :season, :team, :g, :pa, :hr, :avg, :obp, :slg, :ops, :ops_plus, :war)""",
            rows,
        )
    return len(rows)


if __name__ == "__main__":
    count = load_batting_seasons(2020, 2026)
    print(f"Loaded {count} batting rows")
