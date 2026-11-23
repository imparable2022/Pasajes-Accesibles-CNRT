"""Black-box tests for four FSRS ratings and personalized optimization."""
import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

exe = Path(os.environ["REPEATER_TEST_EXE"]).resolve()
assert exe.is_file(), exe

def run(cmd, *, env, input_text=None, timeout=120):
    p = subprocess.run(cmd, input=input_text, text=True, capture_output=True, env=env, timeout=timeout)
    print("$", " ".join(map(str, cmd)))
    print(p.stdout)
    print(p.stderr)
    assert p.returncode == 0, f"command failed ({p.returncode})"
    return p

root = Path(tempfile.mkdtemp(prefix="repeater-four-ratings-"))
deck = root / "one.md"
deck.write_text("Q: Rating test question?\nA: Rating test answer.\n", encoding="utf-8")

# Every visible choice must persist the canonical FSRS 1..4 rating.
for expected in (1, 2, 3, 4):
    data = root / f"data-{expected}"
    env = dict(os.environ, REPEATER_DATA_DIR=str(data), NO_COLOR="1")
    p = run(
        [str(exe), "drill", "--accessible", str(deck)],
        env=env,
        input_text=f"\n{expected}\nq\n",
        timeout=30,
    )
    assert "Review saved:" in p.stdout
    with sqlite3.connect(data / "cards.db") as db:
        ratings = db.execute("SELECT rating FROM review_log ORDER BY id").fetchall()
        counts = db.execute("SELECT review_count FROM cards").fetchall()
    assert ratings == [(expected,)], (expected, ratings)
    assert counts == [(1,)], (expected, counts)

# Build a realistic multi-card history and run the actual fsrs-rs optimizer.
data = root / "optimizer-data"
env = dict(os.environ, REPEATER_DATA_DIR=str(data), NO_COLOR="1")
run([str(exe), "check", "--plain", str(deck)], env=env, timeout=30)
dbpath = data / "cards.db"
start = datetime(2026, 1, 1, tzinfo=timezone.utc)
with sqlite3.connect(dbpath) as db:
    for card_index in range(32):
        t = start + timedelta(days=card_index % 7)
        for review_index in range(8):
            rating = ((card_index + review_index) % 4) + 1
            if review_index:
                t += timedelta(days=(review_index % 4) + 1)
            db.execute(
                "INSERT INTO review_log(card_hash, reviewed_at, rating) VALUES (?, ?, ?)",
                (f"synthetic-{card_index:03d}", t.isoformat(), rating),
            )
    db.commit()

optimized = run([str(exe), "optimize"], env=env, timeout=240)
assert "Optimized FSRS from" in optimized.stdout
with sqlite3.connect(dbpath) as db:
    row = db.execute(
        "SELECT parameters_json, review_count FROM fsrs_settings WHERE id=1"
    ).fetchone()
assert row is not None, "optimizer did not persist settings"
params = json.loads(row[0])
assert len(params) >= 19, f"unexpected optimized parameter count: {len(params)}"
assert row[1] == 32 * 8, row[1]
print(f"PASS: persisted four canonical ratings and {len(params)} personalized FSRS parameters")
