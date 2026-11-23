"""GitHub Actions Windows black-box test against 105 actual mathematics flashcards.

This validates exported Markdown content, not direct original APKG import.
Uses isolated SQLite; verifies every reveal, grade and persistence.
"""
from pathlib import Path
import os
import re
import sqlite3
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
DECKS = ROOT / "test_data_matematica"
EXE = Path(os.environ["REPEATER_TEST_EXE"]).resolve()

def call(args, env, stdin=None, timeout=180):
    result = subprocess.run([str(EXE), *map(str, args)], input=stdin,
                            text=True, encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=timeout, env=env)
    if result.returncode != 0:
        raise AssertionError(f"Command {args} exited {result.returncode}:\n{result.stdout[-6000:]}")
    return result.stdout

def main():
    paths = sorted(DECKS.glob("*.md"))
    assert len(paths) == 2, paths
    counts = {}
    for path in paths:
        content = path.read_text(encoding="utf-8")
        questions = re.findall(r"(?m)^Q: ", content)
        answers = re.findall(r"(?m)^A: ", content)
        assert len(questions) == len(answers), path.name
        counts[path.stem] = len(questions)
    assert sorted(counts.values()) == [50,55], counts
    assert sum(counts.values()) == 105, counts
    with tempfile.TemporaryDirectory(prefix="repeater-math-windows-") as td:
        env = os.environ.copy()
        env["REPEATER_DATA_DIR"] = str(Path(td) / "repeater-db")
        status = call(["check", "--plain", DECKS], env, timeout=90)
        print("CHECK OUTPUT:", status[-2000:], flush=True)
        stdin = "\n4\n" * 105 + "q\n"
        output = call(["drill", "--accessible", "--card-limit", "105",
                       "--new-card-limit", "105", DECKS], env, stdin, timeout=300)
        q_count = len(re.findall(r"Card \d+ of \d+\. Question:", output))
        a_count = output.count("Answer:")
        saved_count = output.count("Review saved:")
        dbpath = Path(env["REPEATER_DATA_DIR"]) / "cards.db"
        assert dbpath.exists(), dbpath
        with sqlite3.connect(dbpath) as con:
            grades = con.execute("SELECT rating,COUNT(*) FROM review_log GROUP BY rating").fetchall()
            card_count = con.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            state_count = con.execute("SELECT COUNT(*) FROM cards WHERE review_count >= 1").fetchone()[0]
        print(f"Decks: {counts}", flush=True)
        print(f"Questions: {q_count}, answers: {a_count}, saved: {saved_count}", flush=True)
        print(f"SQLite: cards={card_count}, reviewed={state_count}, ratings={grades}", flush=True)
        assert (q_count,a_count,saved_count) == (105,105,105), (q_count,a_count,saved_count)
        assert grades == [(4,105)], grades
        assert card_count == 105 and state_count == 105, (card_count,state_count)
        print("PASS: all 105 mathematics cards reviewed and persisted in Windows", flush=True)

if __name__ == "__main__":
    main()
