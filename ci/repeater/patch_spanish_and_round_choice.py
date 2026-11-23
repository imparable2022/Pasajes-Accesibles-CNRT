"""Localiza la experiencia principal de Repeater al español y permite terminar entre rondas.

Se aplica después de patch_fsrs_anki_style.py, contra la versión fijada
de Repeater. Conserva los comandos y el formato Q:/A:/C: para no alterar
mazos existentes, el algoritmo FSRS ni los datos ya guardados.
"""
from pathlib import Path

ROOT = Path("repeater")


def edit(path, changes):
    file = ROOT / path
    source = file.read_text(encoding="utf-8")
    for before, after in changes:
        count = source.count(before)
        if count != 1:
            raise AssertionError(f"{path}: esperaba una coincidencia y encontré {count}: {before[:90]!r}")
        source = source.replace(before, after, 1)
    file.write_text(source, encoding="utf-8")


# Los valores internos de FSRS son estables (1-4); solo se traducen las etiquetas.
edit("src/fsrs.rs", [
    ('ReviewStatus::Again => "Again",', 'ReviewStatus::Again => "Otra vez",'),
    ('ReviewStatus::Fail => "Fail",', 'ReviewStatus::Fail => "Otra vez",'),
    ('ReviewStatus::Hard => "Hard",', 'ReviewStatus::Hard => "Difícil",'),
    ('ReviewStatus::Good => "Good",', 'ReviewStatus::Good => "Bien",'),
    ('ReviewStatus::Pass => "Pass",', 'ReviewStatus::Pass => "Bien",'),
    ('ReviewStatus::Easy => "Easy",', 'ReviewStatus::Easy => "Fácil",'),
])

p = ROOT / "src/commands/drill.rs"
s = p.read_text(encoding="utf-8")
start = s.index("async fn start_accessible_session(")
end = s.index("\nfn validate_retention(", start)
# No vuelve a leer la pregunta al revelar la respuesta, para evitar que NVDA
# repita texto. Ante fin de entrada, guarda lo calificado y sale sin bloquearse.
new = r'''async fn start_accessible_session(
    db: &DB,
    cards: Vec<Card>,
    drill_preprocessor: DrillPreprocessor,
    retention: f32,
    shuffle: bool,
) -> Result<()> {
    use std::io::Write;

    let mut state = DrillState::new(db, cards, retention, shuffle);
    println!("Modo de estudio accesible. Confirma cada opción con Enter. Para salir, escribe Q y presiona Enter.");
    let mut prompt = String::new();

    while !state.is_complete() {
        // Es importante preguntar ANTES de current_card(): esa función
        // cambia automáticamente a la lista de repaso.
        if state.current_idx >= state.cards.len() && !state.redo_cards.is_empty() {
            println!();
            println!(
                "Terminaste {} tarjetas de esta ronda. Tienes {} tarjetas para volver a repasar.",
                state.cards.len(),
                state.redo_cards.len()
            );
            println!("¿Quieres repasarlas ahora? Escribe S y presiona Enter para continuar. Presiona Enter o escribe N para terminar.");
            io::stdout().flush()?;
            loop {
                prompt.clear();
                if io::stdin().read_line(&mut prompt)? == 0 {
                    println!("Sesión finalizada. Tu progreso está guardado.");
                    return Ok(());
                }
                match prompt.trim().to_lowercase().as_str() {
                    "s" | "si" | "sí" => break,
                    "" | "n" | "no" | "q" => {
                        println!("Sesión finalizada. Tu progreso está guardado.");
                        return Ok(());
                    }
                    _ => {
                        println!("Opción no reconocida. Escribe S para repasar o N para terminar y presiona Enter.");
                        io::stdout().flush()?;
                    }
                }
            }
            println!("Comienza la ronda de repaso.");
        }

        let mut card = state.current_card().expect("card is due");
        if matches!(
            card.ai_status,
            AIStatus::ClozeNeedDeletion | AIStatus::QuestionNeedRephrasing
        ) {
            println!("Preparando pregunta...");
            io::stdout().flush()?;
            drill_preprocessor
                .preprocess_cards(std::slice::from_mut(&mut card))
                .await?;
            state.apply_ai_update(AiUpdate {
                card_hash: card.card_hash.clone(),
                card: card.clone(),
            });
        }

        println!();
        println!("Tarjeta {} de {}. Pregunta:", state.current_idx + 1, state.cards.len());
        match &card.content {
            CardContent::Basic { question, .. } => println!("{question}"),
            CardContent::Cloze { .. } => println!("{}", format_card_text(&card, false)),
        }
        println!("Presiona Enter para mostrar la respuesta o escribe Q y presiona Enter para salir.");
        io::stdout().flush()?;
        loop {
            prompt.clear();
            if io::stdin().read_line(&mut prompt)? == 0 { return Ok(()); }
            if prompt.trim().eq_ignore_ascii_case("q") { return Ok(()); }
            if prompt.trim().is_empty() { break; }
            println!("Presiona Enter para ver la respuesta o escribe Q para salir.");
            io::stdout().flush()?;
        }

        println!("Respuesta:");
        match &card.content {
            CardContent::Basic { answer, .. } => println!("{answer}"),
            CardContent::Cloze { .. } => println!("{}", format_card_text(&card, true)),
        }
        println!("Califica tu recuerdo: 1 Otra vez, 2 Difícil, 3 Bien, 4 Fácil. Enter equivale a Bien. Q para salir.");
        io::stdout().flush()?;
        loop {
            prompt.clear();
            if io::stdin().read_line(&mut prompt)? == 0 { return Ok(()); }
            let action = match prompt.trim().to_lowercase().as_str() {
                "q" => return Ok(()),
                "1" | "a" | "again" | "otra vez" => ReviewStatus::Again,
                "2" | "h" | "hard" | "d" | "difícil" | "dificil" => ReviewStatus::Hard,
                "" | "3" | "g" | "good" | "p" | "b" | "bien" => ReviewStatus::Good,
                "4" | "e" | "easy" | "fácil" | "facil" => ReviewStatus::Easy,
                "f" | "fail" => ReviewStatus::Again,
                _ => {
                    println!("Opción no reconocida. Escribe 1, 2, 3 o 4. Enter equivale a Bien. Q para salir.");
                    io::stdout().flush()?;
                    continue;
                }
            };
            state.handle_review(action).await?;
            println!("Repaso guardado: {}.", action.label());
            io::stdout().flush()?;
            break;
        }
    }

    println!("Sesión de estudio completada. Tu progreso está guardado.");
    Ok(())
}
'''
s = s[:start] + new + s[end:]
# Modo de terminal a pantalla completa: preguntar también, sin perder el
# restaurado de la pantalla si se elige no.
anchor = "            while let Ok(update) = ai_updates_rx.try_recv() {\n"
assert s.count(anchor) == 1
s = s.replace(anchor, '''            if state.current_idx >= state.cards.len() && !state.redo_cards.is_empty() {
                terminal.draw(|frame| {
                    let area = frame.area();
                    frame.render_widget(Theme::backdrop(), area);
                    let aviso = Paragraph::new(vec![
                        Line::from(format!(
                            "Terminaste {} tarjetas de esta ronda. Hay {} pendientes para repasar.",
                            state.cards.len(),
                            state.redo_cards.len()
                        )),
                        Line::from("S: repasar ahora. N o Enter: terminar. Esc: salir."),
                    ])
                    .block(Theme::panel("¿Quieres continuar repasando?"));
                    frame.render_widget(aviso, area);
                })?;
                let continuar = loop {
                    if event::poll(Duration::from_millis(100))?
                        && let Event::Key(key) = event::read()?
                    {
                        if key.kind != KeyEventKind::Press {
                            continue;
                        }
                        match key.code {
                            KeyCode::Char('s' | 'S') => break true,
                            KeyCode::Char('n' | 'N' | 'q' | 'Q') | KeyCode::Enter | KeyCode::Esc => break false,
                            KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => break false,
                            _ => {}
                        }
                    }
                };
                if !continuar {
                    break Ok(());
                }
            }

''' + anchor, 1)

# Etiquetas y avisos de la interfaz de estudio normal.
pairs = [
    ('Palette::paint(Palette::SUCCESS, "All caught up—no cards due today.")', 'Palette::paint(Palette::SUCCESS, "No tienes tarjetas pendientes por hoy.")'),
    ('" {} (See again in {})"', '" {} (Volver a ver dentro de {})"'),
    ('show_again.push_str("<15 mins");', 'show_again.push_str("menos de 15 minutos");'),
    ('show_again.push_str("<30 mins");', 'show_again.push_str("menos de 30 minutos");'),
    ('show_again.push_str("<12 hours");', 'show_again.push_str("menos de 12 horas");'),
    ('show_again.push_str("<1 day");', 'show_again.push_str("menos de un día");'),
    ('format!("{} days", self.show_again_duration as i64)', 'format!("{} días", self.show_again_duration as i64)'),
    ('"{} coming again"', '"{} para repasar"'),
    ('Theme::key_chip("AI enhanced")', 'Theme::key_chip("Mejorada con IA")'),
    ('"Enhancing this card with AI...\\n\\nPlease wait."', '"Mejorando esta tarjeta con IA...\\n\\nEspera un momento."'),
    ('Theme::panel_with_line(Theme::section_header("Controls"))', 'Theme::panel_with_line(Theme::section_header("Controles"))'),
    ('Theme::span("Enhancing card with AI")', 'Theme::span("Mejorando tarjeta con IA")'),
    ('Theme::span(" exit")', 'Theme::span(" salir")'),
    ('Theme::span(" show answer")', 'Theme::span(" mostrar respuesta")'),
    ('Theme::span(" open")', 'Theme::span(" abrir")'),
    ('Theme::span("Last:")', 'Theme::span("Última respuesta:")'),
    ('Theme::span(" Hard")', 'Theme::span(" Difícil")'),
    ('Theme::span(" Easy")', 'Theme::span(" Fácil")'),
    ('Span::styled(" Again", Theme::danger())', 'Span::styled(" Otra vez", Theme::danger())'),
    ('Span::styled(" Good", Theme::success())', 'Span::styled(" Bien", Theme::success())'),
    ('Theme::span(" Good")', 'Theme::span(" Bien")'),
    ('let mut text = format!("Q:\\n{}\\n\\nA:\\n", question);', 'let mut text = format!("Pregunta:\\n{}\\n\\nRespuesta:\\n", question);'),
]
for before, after in pairs:
    assert s.count(before) >= 1, ("drill", before, s.count(before))
    s = s.replace(before, after)
# No se modifica 'Q:' o 'A:' en los archivos; siguen siendo marcadores de datos.
p.write_text(s, encoding="utf-8")

# CLI: mantener 'drill', 'import', '--accessible' como comandos de la API estable.
p = ROOT / "src/main.rs"
s = p.read_text(encoding="utf-8")
cli = {
    'about = "Spaced repetition for the terminal."', 'about = "Estudia con tarjetas y repetición espaciada desde la terminal."',
}
for old, newtext in [
    ('/// Plain-text, screen-reader-friendly study mode with line prompts.', '/// Modo de estudio accesible para lectores de pantalla como NVDA.'),
    ('/// Maximum number of cards to drill in a session. By default, all cards due today are drilled.', '/// Máximo de tarjetas por sesión.'),
    ('/// Maximum number of new cards to drill in a session.', '/// Máximo de tarjetas nuevas por sesión.'),
    ('/// Paths to cards or directories containing them.', '/// Rutas de archivos o carpetas con tarjetas.'),
    ('/// You can pass a single file, multiple files, or a directory.', '/// Puedes indicar uno o varios archivos o carpetas.'),
    ('/// Rephrase  card questions via the LLM helper before the session starts.', '/// Reescribir preguntas con ayuda de la IA.'),
    ('/// Randomize the order of cards in the drill session.', '/// Mezclar el orden de las tarjetas.'),
    ('/// Goal retention FSRS should use, this is your target probability of recalling a card at review time.', '/// Probabilidad deseada de recordar una tarjeta para FSRS.'),
    ('/// Drill cards from Apple Notes instead of local files (macOS only).', '/// Estudiar tarjetas desde Apple Notes (solo macOS).'),
    ('/// Drill cards', '/// Estudiar tarjetas'),
    ('/// Re-index decks and show collection stats', '/// Actualizar el índice y consultar estadísticas'),
    ('/// Print a plain summary instead of the TUI dashboard', '/// Mostrar un resumen en texto, accesible para lectores de pantalla'),
    ('/// Check cards from Apple Notes instead of local files (macOS only).', '/// Revisar tarjetas de Apple Notes (solo macOS).'),
    ('/// Create or append to a card', '/// Crear tarjetas o añadir nuevas'),
    ('/// Card path', '/// Ruta de la tarjeta'),
    ('/// Import from Anki', '/// Importar un mazo desde Anki'),
    ('/// Anki export path. Must be an apkg file', '/// Archivo .apkg exportado desde Anki'),
    ('/// Directory to export to', '/// Carpeta donde guardar las tarjetas convertidas'),
    ('/// Learn personalized FSRS parameters from your review history.', '/// Ajustar FSRS a partir de tu historial de repasos.'),
    ('/// Manage LLM helper settings', '/// Configurar el asistente de IA'),
    ('/// Store a new API key in the local auth file', '/// Guardar la clave de API localmente'),
    ('/// Remove the stored API key from the local auth file', '/// Eliminar la clave de API guardada'),
    ('/// Verify the configured API key by calling the OpenAI API', '/// Comprobar la clave de API configurada'),
    ('"Optimized FSRS from {reviews} reviews. Saved {} personalized parameters."', '"FSRS ajustado con {reviews} repasos. Se guardaron {} parámetros personalizados."'),
    ('"Enter your OpenAI API key:"', '"Ingresa tu clave de API de OpenAI:"'),
    ('"Stored the LLM config in the local auth file."', '"Configuración de IA guardada localmente."'),
    ('"Removed the stored LLM config."', '"Configuración de IA eliminada."'),
    ('"The stored LLM config did not exist."', '"No había configuración de IA guardada."'),
    ('"LLM config from the"', '"La configuración de IA desde"'),
    ('"is valid."', '"es válida."'),
    ('"No action provided. Use --set, --clear, or --test."', '"Falta indicar una acción: --set, --clear o --test."'),
]:
    assert old in s, ("main", old)
    s = s.replace(old,newtext)
assert 'about = "Spaced repetition for the terminal."' in s
s=s.replace('about = "Spaced repetition for the terminal."', 'about = "Estudia con tarjetas y repetición espaciada desde la terminal."')
p.write_text(s,encoding="utf-8")

# Mensajes del importador; los nombres y contenidos de los mazos no se traducen.
p = ROOT / "src/import.rs"
s = p.read_text(encoding="utf-8")
for old, newtext in [
    ('"{} decks and {} models in DB schema"', '"La base de Anki tiene {} mazos y {} tipos de nota"'),
    ('"{} cards in DB"', '"{} tarjetas encontradas en Anki"'),
    ('"Removing {} duplicates"', '"{} tarjetas duplicadas omitidas"'),
    ('"{} unexportable cards"', '"{} tarjetas que no se pudieron exportar"'),
    ('"Deck {} has {} cards"', '"El mazo {} contiene {} tarjetas"'),
    ('"There are {} decks with at least one card"', '"Hay {} mazos que contienen tarjetas"'),
    ('"Writing {} cards to {}"', '"Guardando {} tarjetas en {}"'),
    ('"Card with an unknown model id found: {}"', '"Tarjeta con tipo de nota desconocido: {}"'),
]:
    assert s.count(old) == 1, ("import", old)
    s = s.replace(old, newtext, 1)
p.write_text(s,encoding="utf-8")

# Resumen textual de estadísticas y rótulos del tablero.
p = ROOT / "src/commands/check.rs"
s = p.read_text(encoding="utf-8")
labels = {
    "Collection Summary":"Resumen de la colección",
    "Cards found:":"Tarjetas encontradas:",
    "New:":"Nuevas:",
    "Young:":"Recientes:",
    "Mature:":"Consolidadas:",
    "Files containing cards:":"Archivos con tarjetas:",
    "Markdowns parsed:":"Archivos Markdown procesados:",
    "Files searched:":"Archivos examinados:",
    "Total cards indexed in DB:":"Tarjetas guardadas en la base de datos:",
    "Due Status":"Estado de los repasos",
    "Due load:":"Porcentaje pendiente:",
    "Due now:":"Para repasar ahora:",
    "Next 7 days:":"Próximos 7 días:",
    "Next 30 days:":"Próximos 30 días:",
    "Next due:":"Próximo repaso:",
    "Next 7 Days Histogram":"Repasos de los próximos 7 días",
    "You're clear for the next 7 days.":"No tienes repasos previstos para los próximos 7 días.",
    "FSRS Memory Health":"Estadísticas de memoria FSRS",
    "No FSRS statistics to display":"Todavía no hay estadísticas de FSRS.",
    "Difficulty":"Dificultad",
    "The higher the difficulty, the slower stability will increase.":"Cuanto más difícil resulte, más tiempo llevará consolidar el recuerdo.",
    "Retrievability":"Probabilidad de recordar",
    "The probability of recalling a card today.":"Probabilidad de recordar una tarjeta hoy.",
    "Snapshot covers":"El resumen incluye",
    "Rerun command anytime to refresh data":"Vuelve a ejecutar el comando para actualizar los datos.",
    "Average:":"Promedio:",
    "in {} days":"dentro de {} días",
    "in {} hours":"dentro de {} horas",
    "in {} min":"dentro de {} minutos",
    "NA - No cards reviewed":"Sin datos: todavía no hay repasos",
    "Cards Found":"Tarjetas encontradas",
    "New":"Nuevas",
    "Young":"Recientes",
    "Mature":"Consolidadas",
    "Files Containing Cards":"Archivos con tarjetas",
    "Markdowns Parsed":"Markdown procesados",
    "Files Searched":"Archivos examinados",
    "Total Cards Indexed in DB":"Tarjetas en la base de datos",
    "Collection":"Colección",
}
for old, translated in labels.items():
    oldlit = '"' + old + '"'
    if oldlit in s:
        s=s.replace(oldlit,'"' + translated + '"')
p.write_text(s,encoding="utf-8")

# La interfaz TUI de creación se conserva, con mensajes principales traducidos.
p = ROOT / "src/commands/create.rs"
s = p.read_text(encoding="utf-8")
for a,b in [
    ('"Card saved."', '"Tarjeta guardada."'),
    ('"{saved_count} cards saved."', '"{saved_count} tarjetas guardadas."'),
    ('"Unable to save card: {}"', '"No se pudo guardar la tarjeta: {}"'),
]:
    assert a in s, ("create",a)
    s = s.replace(a,b)
p.write_text(s, encoding="utf-8")
print("Traducción principal al español y elección entre rondas aplicadas.")
