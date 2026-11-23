"""Add an opt-in accessible, line-oriented study mode to Repeater.

This avoids ratatui's alternate-screen redraw loop, emits each question and
answer only once, and accepts simple Enter-terminated keyboard commands.
"""
from pathlib import Path

root = Path("repeater")
main = root / "src/main.rs"
s = main.read_text(encoding="utf-8")
anchor = "        /// Maximum number of cards to drill in a session. By default, all cards due today are drilled."
assert s.count(anchor) == 1
s = s.replace(anchor, """        /// Plain-text, screen-reader-friendly study mode with line prompts.
        #[arg(long, default_value_t = false)]
        accessible: bool,
""" + anchor)
anchor = "            card_limit,\n            new_card_limit,\n"
assert s.count(anchor) == 1
s = s.replace(anchor, "            card_limit,\n            new_card_limit,\n            accessible,\n")
anchor = "                card_limit,\n                new_card_limit,\n"
assert s.count(anchor) == 1
s = s.replace(anchor, "                card_limit,\n                new_card_limit,\n                accessible,\n")
main.write_text(s, encoding="utf-8")

drill = root / "src/commands/drill.rs"
s = drill.read_text(encoding="utf-8")
anchor = "    pub card_limit: Option<usize>,\n"
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + "    pub accessible: bool,\n", 1)
anchor = "    start_drill_session(\n"
assert s.count(anchor) == 1
s = s.replace(anchor, """    if opts.accessible {
        return start_accessible_session(db, cards_due_today, drill_preprocessor, opts.retention, opts.shuffle).await;
    }
""" + anchor, 1)

new = r'''
/// Accessible mode deliberately uses the normal terminal buffer, avoiding
/// repeated full-screen redraws and preserving readable scrollback for NVDA.
/// Commands need Enter: Enter = show answer; P/Enter = pass; F = fail;
/// Q = quit. FSRS reviews still use the existing DrillState implementation.
async fn start_accessible_session(
    db: &DB,
    cards: Vec<Card>,
    drill_preprocessor: DrillPreprocessor,
    retention: f32,
    shuffle: bool,
) -> Result<()> {
    use std::io::Write;

    let mut state = DrillState::new(db, cards, retention, shuffle);
    println!("Accessible study mode. All commands require Enter. Q quits.");
    let mut prompt = String::new();
    while !state.is_complete() {
        let mut card = state.current_card().expect("card is due");
        if matches!(
            card.ai_status,
            AIStatus::ClozeNeedDeletion | AIStatus::QuestionNeedRephrasing
        ) {
            println!("Preparing question...");
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
        println!("Card {} of {}. Question:", state.current_idx + 1, state.cards.len());
        // Printing just the question avoids leaking the answer into NVDA speech.
        println!("{}", format_card_text(&card, false));
        println!("Press Enter to show answer. Type Q then Enter to quit.");
        io::stdout().flush()?;
        loop {
            prompt.clear();
            if io::stdin().read_line(&mut prompt)? == 0 { return Ok(()); }
            if prompt.trim().eq_ignore_ascii_case("q") { return Ok(()); }
            if prompt.trim().is_empty() { break; }
            println!("Press Enter to show answer, or Q then Enter to quit.");
            io::stdout().flush()?;
        }
        println!("Answer:");
        println!("{}", format_card_text(&card, true));
        println!("Press Enter or P then Enter for Pass; F then Enter for Fail; Q to quit.");
        io::stdout().flush()?;
        loop {
            prompt.clear();
            if io::stdin().read_line(&mut prompt)? == 0 { return Ok(()); }
            let action = match prompt.trim().to_ascii_lowercase().as_str() {
                "q" => return Ok(()),
                "" | "p" => ReviewStatus::Pass,
                "f" => ReviewStatus::Fail,
                _ => {
                    println!("Enter or P = Pass; F = Fail; Q = quit.");
                    io::stdout().flush()?;
                    continue;
                }
            };
            state.handle_review(action).await?;
            println!("Review saved: {}.", action.label());
            io::stdout().flush()?;
            break;
        }
    }
    println!("Study session complete.");
    Ok(())
}
'''
marker="fn validate_retention(retention: f32) -> Result<()> {"
assert s.count(marker)==1
s=s.replace(marker,new+"\n"+marker,1)
drill.write_text(s,encoding="utf-8")
print("Added accessible study mode with real FSRS persistence")
