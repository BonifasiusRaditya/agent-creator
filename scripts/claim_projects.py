"""Give projects created before accounts existed to one user.

Projects saved under the old single-password workspace have no owner and are
hidden from every account until claimed. Preview first, then apply:

    uv run python -m scripts.claim_projects --username your-name
    uv run python -m scripts.claim_projects --username your-name --apply

Uses the database configured in .env (Turso or local SQLite). Stop the server first.
"""
import argparse
import json

from trendforge.auth import normalize_username
from trendforge.config import DATA
from trendforge.db import Database


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    database = Database(DATA / "trendforge.sqlite3")
    user = database.user_by_username(normalize_username(args.username))
    if not user:
        raise SystemExit("No account with that username. Register it in the website first.")
    with database.connect() as c:
        unowned = [json.loads(r["data"]) for r in c.execute("SELECT data FROM projects WHERE owner_id IS NULL").fetchall()]
    print(json.dumps({"username": user["username"], "backend": database.backend, "apply": args.apply,
                      "unowned_projects": [{"id": p["id"], "niche": p.get("niche")} for p in unowned]}, indent=2))
    if args.apply:
        claimed = database.claim_projects(user["id"])
        print(f"Assigned {len(claimed)} project(s) to {user['username']}.")
    elif unowned:
        print("Preview only. Run again with --apply to assign these projects.")


if __name__ == "__main__":
    main()
