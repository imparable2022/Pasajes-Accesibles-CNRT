"""Add Anki-style four-grade FSRS reviews and per-user parameter optimization.

Applied after patch_accessible.py against pinned Repeater 0.1.10 source.
"""
from pathlib import Path

root = Path("repeater")

# 1. Database migration: durable review log + optimized parameter storage.
migration = root / "migrations" / "0002_fsrs_review_history.sql"
migration.write_text("""\
CREATE TABLE IF NOT EXISTS review_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_hash TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 4)
);

CREATE INDEX IF NOT EXISTS idx_review_log_card_time
ON review_log(card_hash, reviewed_at, id);

CREATE TABLE IF NOT EXISTS fsrs_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    parameters_json TEXT NOT NULL,
    optimized_at TEXT NOT NULL,
    review_count INTEGER NOT NULL
);
""", encoding="utf-8")

# 2. DB-side history/optimizer helpers. Dynamic sqlx queries avoid offline macro metadata.
history = root / "src" / "crud" / "fsrs_history.rs"
history.write_text(r'''use anyhow::{Context, Result, bail};
use chrono::{DateTime, Utc};
use fsrs::{ComputeParametersInput, FSRS, FSRSItem, FSRSReview};
use sqlx::Row;

use super::DB;

impl DB {
    pub async fn load_fsrs_parameters(&self) -> Result<Option<Vec<f32>>> {
        let row = sqlx::query("SELECT parameters_json FROM fsrs_settings WHERE id = 1")
            .fetch_optional(&self.pool)
            .await?;
        row.map(|row| {
            let json: String = row.try_get("parameters_json")?;
            serde_json::from_str(&json).context("invalid optimized FSRS parameters in database")
        })
        .transpose()
    }

    pub async fn review_history_item(&self, card_hash: &str) -> Result<Option<FSRSItem>> {
        let rows = sqlx::query(
            "SELECT reviewed_at, rating FROM review_log WHERE card_hash = ? ORDER BY reviewed_at, id",
        )
        .bind(card_hash)
        .fetch_all(&self.pool)
        .await?;
        if rows.is_empty() {
            return Ok(None);
        }

        let mut reviews = Vec::with_capacity(rows.len());
        let mut previous: Option<DateTime<Utc>> = None;
        for row in rows {
            let reviewed_at: String = row.try_get("reviewed_at")?;
            let reviewed_at = DateTime::parse_from_rfc3339(&reviewed_at)
                .context("invalid review_log timestamp")?
                .with_timezone(&Utc);
            let rating: i64 = row.try_get("rating")?;
            let delta_t = previous
                .map(|last| reviewed_at.signed_duration_since(last).num_days().max(0) as u32)
                .unwrap_or(0);
            reviews.push(FSRSReview {
                rating: rating as u32,
                delta_t,
            });
            previous = Some(reviewed_at);
        }
        Ok(Some(FSRSItem { reviews }))
    }

    async fn optimization_train_set(&self) -> Result<(Vec<FSRSItem>, usize)> {
        let rows = sqlx::query(
            "SELECT card_hash, reviewed_at, rating FROM review_log ORDER BY card_hash, reviewed_at, id",
        )
        .fetch_all(&self.pool)
        .await?;

        let mut train_set = Vec::new();
        let mut total_reviews = 0usize;
        let mut current_hash = String::new();
        let mut accumulated: Vec<FSRSReview> = Vec::new();
        let mut previous: Option<DateTime<Utc>> = None;

        for row in rows {
            let hash: String = row.try_get("card_hash")?;
            if hash != current_hash {
                current_hash = hash;
                accumulated.clear();
                previous = None;
            }
            let reviewed_at: String = row.try_get("reviewed_at")?;
            let reviewed_at = DateTime::parse_from_rfc3339(&reviewed_at)
                .context("invalid review_log timestamp")?
                .with_timezone(&Utc);
            let rating: i64 = row.try_get("rating")?;
            let delta_t = previous
                .map(|last| reviewed_at.signed_duration_since(last).num_days().max(0) as u32)
                .unwrap_or(0);
            accumulated.push(FSRSReview {
                rating: rating as u32,
                delta_t,
            });
            total_reviews += 1;
            // A prefix with >=2 reviews provides a prediction target.
            if accumulated.len() >= 2 {
                train_set.push(FSRSItem {
                    reviews: accumulated.clone(),
                });
            }
            previous = Some(reviewed_at);
        }

        Ok((train_set, total_reviews))
    }

    pub async fn optimize_fsrs_parameters(&self) -> Result<(usize, Vec<f32>)> {
        let (train_set, total_reviews) = self.optimization_train_set().await?;
        if train_set.is_empty() {
            bail!("Not enough review history to optimize FSRS yet. Complete at least two reviews on a card.");
        }
        let model = FSRS::new(None)?;
        let params = model.compute_parameters(ComputeParametersInput {
            train_set,
            enable_short_term: true,
            ..Default::default()
        })?;
        let json = serde_json::to_string(&params)?;
        let now = Utc::now().to_rfc3339();
        sqlx::query(
            "INSERT INTO fsrs_settings (id, parameters_json, optimized_at, review_count)
             VALUES (1, ?, ?, ?)
             ON CONFLICT(id) DO UPDATE SET
               parameters_json=excluded.parameters_json,
               optimized_at=excluded.optimized_at,
               review_count=excluded.review_count",
        )
        .bind(json)
        .bind(now)
        .bind(total_reviews as i64)
        .execute(&self.pool)
        .await?;
        Ok((total_reviews, params))
    }
}
''', encoding="utf-8")

crud_mod = root / "src" / "crud" / "mod.rs"
s = crud_mod.read_text(encoding="utf-8")
if "pub mod fsrs_history;" not in s:
    s = s.replace("pub mod db;\n", "pub mod db;\npub mod fsrs_history;\n")
crud_mod.write_text(s, encoding="utf-8")

# 3. Extend ratings and let scheduling consume optional optimized parameters.
fsrs_path = root / "src" / "fsrs.rs"
s = fsrs_path.read_text(encoding="utf-8")
old = """#[derive(Copy, Clone, PartialEq)]
pub enum ReviewStatus {
    Pass,
    Fail,
}

impl ReviewStatus {
    pub fn label(&self) -> &'static str {
        match self {
            ReviewStatus::Pass => "Pass",
            ReviewStatus::Fail => "Fail",
        }
    }
}"""
new = """#[derive(Copy, Clone, Debug, PartialEq)]
pub enum ReviewStatus {
    Again,
    Hard,
    Good,
    Easy,
    // Backwards-compatible aliases used by existing tests/callers.
    Pass,
    Fail,
}

impl ReviewStatus {
    pub fn label(&self) -> &'static str {
        match self {
            ReviewStatus::Again | ReviewStatus::Fail => "Again",
            ReviewStatus::Hard => "Hard",
            ReviewStatus::Good | ReviewStatus::Pass => "Good",
            ReviewStatus::Easy => "Easy",
        }
    }

    pub fn rating(&self) -> u32 {
        match self {
            ReviewStatus::Again | ReviewStatus::Fail => 1,
            ReviewStatus::Hard => 2,
            ReviewStatus::Good | ReviewStatus::Pass => 3,
            ReviewStatus::Easy => 4,
        }
    }
}"""
assert s.count(old) == 1
s = s.replace(old, new)

old = """    match review_status {
        ReviewStatus::Pass => next_states.good,
        ReviewStatus::Fail => next_states.again,
    }"""
new = """    match review_status {
        ReviewStatus::Again | ReviewStatus::Fail => next_states.again,
        ReviewStatus::Hard => next_states.hard,
        ReviewStatus::Good | ReviewStatus::Pass => next_states.good,
        ReviewStatus::Easy => next_states.easy,
    }"""
assert s.count(old) == 1
s = s.replace(old, new)

# Keep Repeater's learning-stage caps, but distinguish the four buttons.
start = s.index("fn early_interval_cap(")
end = s.index("\n}\n\n#[derive(Copy, Clone", start) + 2
replacement = """fn early_interval_cap(review_count: usize, review_status: ReviewStatus) -> Option<Duration> {
    match review_count {
        0 => match review_status {
            ReviewStatus::Again | ReviewStatus::Fail => Some(Duration::minutes(1)),
            ReviewStatus::Hard => Some(Duration::minutes(5)),
            ReviewStatus::Good | ReviewStatus::Pass => Some(Duration::minutes(10)),
            ReviewStatus::Easy => Some(Duration::days(1)),
        },
        1 => match review_status {
            ReviewStatus::Again | ReviewStatus::Fail => Some(Duration::minutes(1)),
            ReviewStatus::Hard => Some(Duration::minutes(10)),
            ReviewStatus::Good | ReviewStatus::Pass => Some(Duration::days(1)),
            ReviewStatus::Easy => None,
        },
        2 => match review_status {
            ReviewStatus::Again | ReviewStatus::Fail => Some(Duration::minutes(10)),
            ReviewStatus::Hard => Some(Duration::hours(12)),
            ReviewStatus::Good | ReviewStatus::Pass => Some(Duration::days(1)),
            ReviewStatus::Easy => None,
        },
        _ => None,
    }
}"""
s = s[:start] + replacement + s[end:]

# Parameterized model helper + compatibility wrapper.
s = s.replace(
    """fn fsrs_model() -> Result<FSRS> {
    FSRS::new(Some(&DEFAULT_PARAMETERS)).context("failed to initialize FSRS model")
}""",
    """fn fsrs_model(parameters: Option<&[f32]>) -> Result<FSRS> {
    FSRS::new(Some(parameters.unwrap_or(&DEFAULT_PARAMETERS)))
        .context("failed to initialize FSRS model")
}"""
)
old_sig = """pub fn update_performance(
    perf: Performance,
    review_status: ReviewStatus,
    reviewed_at: DateTime<Utc>,
    retention: f32,
) -> Result<ReviewedPerformance> {"""
new_sig = """pub fn update_performance(
    perf: Performance,
    review_status: ReviewStatus,
    reviewed_at: DateTime<Utc>,
    retention: f32,
) -> Result<ReviewedPerformance> {
    update_performance_with_parameters(perf, review_status, reviewed_at, retention, None)
}

pub fn update_performance_with_parameters(
    perf: Performance,
    review_status: ReviewStatus,
    reviewed_at: DateTime<Utc>,
    retention: f32,
    parameters: Option<&[f32]>,
) -> Result<ReviewedPerformance> {"""
assert s.count(old_sig) == 1
s = s.replace(old_sig, new_sig)
s = s.replace("    let fsrs = fsrs_model()?;", "    let fsrs = fsrs_model(parameters)?;", 1)
fsrs_path.write_text(s, encoding="utf-8")

# 4. Persist every grade and apply optimized parameters automatically.
cards = root / "src" / "crud" / "cards.rs"
s = cards.read_text(encoding="utf-8")
s = s.replace(
    "use crate::fsrs::update_performance;\n",
    "use crate::fsrs::update_performance_with_parameters;\n"
)
old = """        let new_performance =
            update_performance(current_performance, review_status, now, retention)?;"""
new = """        let optimized_params = self.load_fsrs_parameters().await?;
        let mut scheduling_performance = current_performance;

        // When review history exists, rebuild memory state with the optimized
        // parameters so newly trained weights affect existing cards too.
        if let (Some(params), Some(item)) = (
            optimized_params.as_deref(),
            self.review_history_item(&card.card_hash).await?,
        ) {
            if let Performance::Reviewed(mut reviewed) = scheduling_performance {
                let model = fsrs::FSRS::new(Some(params))?;
                let memory = model.memory_state(item, None)?;
                reviewed.stability = memory.stability as f64;
                reviewed.difficulty = memory.difficulty as f64;
                scheduling_performance = Performance::Reviewed(reviewed);
            }
        }

        let new_performance = update_performance_with_parameters(
            scheduling_performance,
            review_status,
            now,
            retention,
            optimized_params.as_deref(),
        )?;"""
assert s.count(old) == 1
s = s.replace(old, new)

# Make state update + review log atomic.
needle = """        sqlx::query!(
            r#"
            UPDATE cards"""
assert s.count(needle) == 1
s = s.replace(needle, """        let mut tx = self.pool.begin().await?;

        sqlx::query!(
            r#"
            UPDATE cards""", 1)
s = s.replace(".execute(&self.pool)\n        .await?;\n\n        Ok(new_performance.interval_raw)", """.execute(&mut *tx)
        .await?;

        sqlx::query(
            "INSERT INTO review_log (card_hash, reviewed_at, rating) VALUES (?, ?, ?)",
        )
        .bind(&card.card_hash)
        .bind(now.to_rfc3339())
        .bind(review_status.rating() as i64)
        .execute(&mut *tx)
        .await?;

        tx.commit().await?;

        Ok(new_performance.interval_raw)""", 1)
cards.write_text(s, encoding="utf-8")

# 5. Add CLI optimization command.
main = root / "src" / "main.rs"
s = main.read_text(encoding="utf-8")
anchor = """    /// Manage LLM helper settings
    Llm {"""
assert s.count(anchor) == 1
s = s.replace(anchor, """    /// Learn personalized FSRS parameters from your review history.
    Optimize,
    /// Manage LLM helper settings
    Llm {""")
anchor = """        Command::Llm { set, clear, test } => handle_llm_command(set, clear, test).await?,"""
assert s.count(anchor) == 1
s = s.replace(anchor, """        Command::Optimize => {
            let (reviews, params) = db.optimize_fsrs_parameters().await?;
            println!(
                "Optimized FSRS from {reviews} reviews. Saved {} personalized parameters.",
                params.len()
            );
        }
""" + anchor)
main.write_text(s, encoding="utf-8")

# 6. Four choices in both the full TUI and accessible study mode.
drill = root / "src" / "commands" / "drill.rs"
s = drill.read_text(encoding="utf-8")

# Failure redo behavior should treat Again (and legacy Fail) as the relearn case.
s = s.replace(
    "if action == ReviewStatus::Fail\n",
    "if matches!(action, ReviewStatus::Again | ReviewStatus::Fail)\n"
)

# TUI input mapping.
old = """                    KeyCode::Char(' ') | KeyCode::Enter if !ai_pending => {
                        if !state.show_answer {
                            state.reveal_answer();
                        } else {
                            state.handle_review(ReviewStatus::Pass).await?;
                        }
                    }
                    KeyCode::Char('F') | KeyCode::Char('f') if state.show_answer && !ai_pending => {
                        state.handle_review(ReviewStatus::Fail).await?;
                    }"""
new = """                    KeyCode::Char(' ') | KeyCode::Enter if !ai_pending => {
                        if !state.show_answer {
                            state.reveal_answer();
                        } else {
                            state.handle_review(ReviewStatus::Good).await?;
                        }
                    }
                    KeyCode::Char('1') | KeyCode::Char('A') | KeyCode::Char('a')
                        if state.show_answer && !ai_pending =>
                    {
                        state.handle_review(ReviewStatus::Again).await?;
                    }
                    KeyCode::Char('2') | KeyCode::Char('H') | KeyCode::Char('h')
                        if state.show_answer && !ai_pending =>
                    {
                        state.handle_review(ReviewStatus::Hard).await?;
                    }
                    KeyCode::Char('3') | KeyCode::Char('G') | KeyCode::Char('g')
                        if state.show_answer && !ai_pending =>
                    {
                        state.handle_review(ReviewStatus::Good).await?;
                    }
                    KeyCode::Char('4') | KeyCode::Char('E') | KeyCode::Char('e')
                        if state.show_answer && !ai_pending =>
                    {
                        state.handle_review(ReviewStatus::Easy).await?;
                    }
                    KeyCode::Char('F') | KeyCode::Char('f') if state.show_answer && !ai_pending => {
                        state.handle_review(ReviewStatus::Again).await?;
                    }"""
assert s.count(old) == 1
s = s.replace(old, new)

# TUI footer.
old = """        lines.push(Line::from(vec![
            Theme::key_chip("Space"),
            Theme::span(" or "),
            Theme::key_chip("Enter"),
            Span::styled(" Pass", Theme::success()),
            Theme::bullet(),
            Theme::key_chip("F"),
            Span::styled(" Fail", Theme::danger()),
            Theme::bullet(),"""
new = """        lines.push(Line::from(vec![
            Theme::key_chip("1"),
            Span::styled(" Again", Theme::danger()),
            Theme::bullet(),
            Theme::key_chip("2"),
            Theme::span(" Hard"),
            Theme::bullet(),
            Theme::key_chip("3"),
            Span::styled(" Good", Theme::success()),
            Theme::bullet(),
            Theme::key_chip("4"),
            Theme::span(" Easy"),
            Theme::bullet(),
            Theme::key_chip("Enter"),
            Theme::span(" Good"),
            Theme::bullet(),"""
assert s.count(old) == 1
s = s.replace(old, new)

# Accessible prompt and mapping. Enter remains Good.
s = s.replace(
    'println!("Press Enter or P then Enter for Pass; F then Enter for Fail; Q to quit.");',
    'println!("Rate your recall: 1 Again (forgot), 2 Hard, 3 Good, 4 Easy. Enter = Good. Q = quit.");'
)
old = """            let action = match prompt.trim().to_ascii_lowercase().as_str() {
                "q" => return Ok(()),
                "" | "p" => ReviewStatus::Pass,
                "f" => ReviewStatus::Fail,
                _ => {
                    println!("Enter or P = Pass; F = Fail; Q = quit.");
                    io::stdout().flush()?;
                    continue;
                }
            };"""
new = """            let action = match prompt.trim().to_ascii_lowercase().as_str() {
                "q" => return Ok(()),
                "1" | "a" | "again" => ReviewStatus::Again,
                "2" | "h" | "hard" => ReviewStatus::Hard,
                "" | "3" | "g" | "good" | "p" => ReviewStatus::Good,
                "4" | "e" | "easy" => ReviewStatus::Easy,
                "f" | "fail" => ReviewStatus::Again,
                _ => {
                    println!("1 Again, 2 Hard, 3 Good, 4 Easy. Enter = Good; Q = quit.");
                    io::stdout().flush()?;
                    continue;
                }
            };"""
assert s.count(old) == 1
s = s.replace(old, new)

# Theme match needs exhaustive handling with new statuses.
s = s.replace(
    """        let style = match action.action {
            ReviewStatus::Pass => Theme::success(),
            ReviewStatus::Fail => Theme::danger(),
        };""",
    """        let style = match action.action {
            ReviewStatus::Again | ReviewStatus::Fail => Theme::danger(),
            ReviewStatus::Hard => Theme::label(),
            ReviewStatus::Good | ReviewStatus::Pass | ReviewStatus::Easy => Theme::success(),
        };"""
)
drill.write_text(s, encoding="utf-8")

print("Added four FSRS ratings, durable review history, personalized optimizer, and optimized scheduling.")
