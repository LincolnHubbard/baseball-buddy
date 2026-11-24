from google.genai import types

from src import database as db

SEASON_MIN, SEASON_MAX = 2020, 2026


def lookup_player_stats(name: str, season: int | None = None) -> dict:
    matches = db.find_players(name)
    if not matches:
        return {"error": f"No player found matching '{name}'."}

    normalized_query = db.normalize_name(name)
    exact = [m for m in matches if db.normalize_name(m["full_name"]) == normalized_query]
    if exact:
        matches = exact
    if len(matches) > 1:
        return {
            "ambiguous": True,
            "message": "More than one player matches. Ask the user which one they mean.",
            "candidates": [m["full_name"] for m in matches],
        }

    player = matches[0]
    stats = db.get_player_stats(player["player_id"], season)
    if not stats:
        return {"player": player["full_name"], "error": "No batting data found for that request."}
    return {"player": player["full_name"], "seasons": stats}


def get_stat_leaders(stat: str, season: int, limit: int = 10) -> dict:
    try:
        leaders = db.get_leaders(stat, season, limit)
    except ValueError as e:
        return {"error": str(e)}
    return {"stat": stat, "season": season, "leaders": leaders}


def get_team_batting(team: str, season: int) -> dict:
    rows = db.get_team_season(team.upper(), season)
    if not rows:
        return {"error": f"No batting data for team '{team}' in {season}."}
    return {"team": team.upper(), "season": season, "batters": rows}


TOOL_FUNCTIONS = {
    "lookup_player_stats": lookup_player_stats,
    "get_stat_leaders": get_stat_leaders,
    "get_team_batting": get_team_batting,
}

_season_prop = types.Schema(
    type=types.Type.INTEGER,
    description=f"Season year, from {SEASON_MIN} to {SEASON_MAX}.",
)

# these 'types' are from Google's SDK but Anthropic, OpenAI, etc. have their own
# https://googleapis.github.io/python-genai/#types
TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="lookup_player_stats",
        description=(
            "Look up batting stats for one player by name. Use for any question about "
            "a specific player's numbers, including comparisons, where you call it once per player. "
            "Omit season to get all seasons."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(type=types.Type.STRING, description="Player's name, e.g. 'Aaron Judge'."),
                "season": _season_prop,
            },
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_stat_leaders",
        description=(
            "Get the top players in one batting stat for a season. Only players with "
            "at least 300 plate appearances are included. Supported stats: hr, avg, obp, slg, "
            "ops, ops_plus, war, pa, g."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "stat": types.Schema(type=types.Type.STRING, description="Stat column, e.g. 'hr' or 'ops'."),
                "season": _season_prop,
                "limit": types.Schema(type=types.Type.INTEGER, description="How many players to return. Default 10."),
            },
            required=["stat", "season"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_team_batting",
        description=(
            "Get all batters for a team in one season. Use Baseball Reference team codes "
            "such as NYY, LAD, BOS, SFG, or CHC."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "team": types.Schema(type=types.Type.STRING, description="Team code, e.g. 'NYY'."),
                "season": _season_prop,
            },
            required=["team", "season"],
        ),
    ),
]

GEMINI_TOOLS = [types.Tool(function_declarations=TOOL_DECLARATIONS)]
