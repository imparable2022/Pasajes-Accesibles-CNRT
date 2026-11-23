"""Windows black-box regression: Spanish prompts, optional additional rounds, persistence.

Use only temporary REPEATER_DATA_DIR locations; never touch the user's study DB.
"""
from pathlib import Path
from contextlib import closing
import os
import sqlite3
import subprocess
import tempfile

EXE = Path(os.environ["REPEATER_TEST_EXE"]).resolve()


def run(deck, dbdir, answers):
    env = dict(os.environ, REPEATER_DATA_DIR=str(dbdir), NO_COLOR="1")
    result = subprocess.run(
        [str(EXE), "drill", "--accessible", str(deck)],
        input=answers, text=True, encoding="utf-8", errors="replace",
        capture_output=True, env=env, timeout=45,
    )
    print(result.stdout, flush=True)
    assert result.returncode == 0, result.stderr
    with closing(sqlite3.connect(dbdir / "cards.db")) as conn:
        history = conn.execute("SELECT rating FROM review_log ORDER BY id").fetchall()
        review_count = conn.execute("SELECT review_count FROM cards").fetchone()[0]
    return result.stdout, history, review_count


with tempfile.TemporaryDirectory(prefix="repeater-rondas-es-") as temp:
    base = Path(temp)
    deck = base / "matematica.md"
    deck.write_text(
        "Q: ¿Cuál es la intersección de A y B?\n"
        "A: Son los elementos que pertenecen a ambos conjuntos.\n",
        encoding="utf-8",
    )

    for answer, action in [("\n2\nn\n", "n"),
                           ("\n2\n\n", "enter"),
                           ("\n2\nq\n", "q")]:
        output, ratings, count = run(deck, base / ("skip-" + action), answer)
        assert "Tarjeta 1 de 1. Pregunta:" in output
        assert "Respuesta:" in output
        assert "¿Quieres repasarlas ahora?" in output, output
        assert "Sesión finalizada. Tu progreso está guardado." in output
        assert "Comienza la ronda de repaso." not in output
        assert ratings == [(2,)] and count == 1, (ratings, count)
        print("PASS: elección de salir", action, flush=True)

    output, ratings, count = run(deck, base / "continue", "\n2\ns\nq\n")
    assert "¿Quieres repasarlas ahora?" in output
    assert "Comienza la ronda de repaso." in output
    assert output.count("Tarjeta 1 de 1. Pregunta:") == 2
    assert ratings == [(2,)] and count == 1, (ratings, count)
    print("PASS: S inicia nueva ronda y Q conserva la revisión anterior", flush=True)

    output, ratings, count = run(deck, base / "easy", "\n4\n")
    assert "¿Quieres repasarlas ahora?" not in output
    assert "Sesión de estudio completada." in output
    assert ratings == [(4,)] and count == 1
    print("PASS: Fácil no obliga a repaso inmediato", flush=True)

    env = dict(os.environ, REPEATER_DATA_DIR=str(base / "helpdb"), NO_COLOR="1")
    help_result = subprocess.run(
        [str(EXE), "drill", "--help"], text=True, encoding="utf-8",
        errors="replace", capture_output=True, env=env, timeout=15,
    )
    assert help_result.returncode == 0
    assert "Modo de estudio accesible" in help_result.stdout, help_result.stdout
    assert "--accessible" in help_result.stdout
    print("PASS: ayuda del comando también aparece en español", flush=True)

print("PASS: elección al terminar ronda + interfaz principal en español")
