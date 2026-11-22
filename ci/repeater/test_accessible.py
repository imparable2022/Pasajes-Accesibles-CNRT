"""Black-box acceptance test of Repeater's accessible plain-text mode and SQLite persistence."""
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path

exe = Path(os.environ["REPEATER_TEST_EXE"]).resolve()
assert exe.is_file(), exe
with tempfile.TemporaryDirectory(prefix="repeater-accessible-") as folder:
    root = Path(folder)
    deck = root / "accessible.md"
    deck.write_text(
        "Q: What is the first accessibility question?\n"
        "A: The first accessible answer.\n\n"
        "Q: What is the second accessibility question?\n"
        "A: The second accessible answer.\n",
        encoding="utf-8",
    )
    env = dict(os.environ, REPEATER_DATA_DIR=str(root / "data"), NO_COLOR="1")
    cmd = [str(exe), "drill", "--accessible", str(deck)]
    proc = subprocess.run(cmd, input="\n\nq\n", text=True, capture_output=True, env=env, timeout=30)
    print("EXE:", exe)
    print("STDOUT:", proc.stdout)
    print("STDERR:", proc.stderr)
    assert proc.returncode == 0, f"exit code {proc.returncode}"
    stdout = proc.stdout
    assert "first accessibility question" in stdout.lower()
    assert "first accessible answer" in stdout.lower()
    assert stdout.index("first accessibility question") < stdout.index("first accessible answer")
    assert "Review saved: Pass." in stdout, "no persisted grade acknowledgement"
    dbpath = root / "data" / "cards.db"
    assert dbpath.is_file(), "missing SQLite database"
    with sqlite3.connect(dbpath) as db:
        rows = db.execute("SELECT review_count FROM cards ORDER BY review_count DESC").fetchall()
    assert rows and rows[0][0] == 1, f"review count not stored in DB: {rows}"
    print("PASS: plain-text question + reveal + successful FSRS database update")
