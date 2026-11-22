"""Patch Repeater's interactive commands for Windows legacy console.
Pinned upstream source means any drift aborts rather than silently shipping unpatched code.
"""
from pathlib import Path

ROOT = Path.cwd() / "repeater"
for rel in ("src/commands/create.rs", "src/commands/drill.rs"):
    path = ROOT / rel
    source = path.read_text(encoding="utf-8")
    setup = """    execute!(
        stdout,
        EnterAlternateScreen,
        PushKeyboardEnhancementFlags(
            KeyboardEnhancementFlags::REPORT_ALL_KEYS_AS_ESCAPE_CODES
                | KeyboardEnhancementFlags::DISAMBIGUATE_ESCAPE_CODES
        )
    )"""
    teardown = """    execute!(
        terminal.backend_mut(),
        PopKeyboardEnhancementFlags,
        LeaveAlternateScreen
    )"""
    if rel.endswith("drill.rs"):
        old_setup = setup + '\n    .context("failed to configure terminal")?;'
        new_setup = """    #[cfg(windows)]
    execute!(stdout, EnterAlternateScreen)
        .context("failed to configure terminal")?;
    #[cfg(not(windows))]
    execute!(
        stdout,
        EnterAlternateScreen,
        PushKeyboardEnhancementFlags(
            KeyboardEnhancementFlags::REPORT_ALL_KEYS_AS_ESCAPE_CODES
                | KeyboardEnhancementFlags::DISAMBIGUATE_ESCAPE_CODES
        )
    )
    .context("failed to configure terminal")?;"""
        old_teardown = teardown + '\n    .context("failed to restore terminal")?;'
        new_teardown = """    #[cfg(windows)]
    execute!(terminal.backend_mut(), LeaveAlternateScreen)
        .context("failed to restore terminal")?;
    #[cfg(not(windows))]
    execute!(
        terminal.backend_mut(),
        PopKeyboardEnhancementFlags,
        LeaveAlternateScreen
    )
    .context("failed to restore terminal")?;"""
    else:
        old_setup = setup + "?;"
        new_setup = """    #[cfg(windows)]
    execute!(stdout, EnterAlternateScreen)?;
    #[cfg(not(windows))]
    execute!(
        stdout,
        EnterAlternateScreen,
        PushKeyboardEnhancementFlags(
            KeyboardEnhancementFlags::REPORT_ALL_KEYS_AS_ESCAPE_CODES
                | KeyboardEnhancementFlags::DISAMBIGUATE_ESCAPE_CODES
        )
    )?;"""
        old_teardown = teardown + "?;"
        new_teardown = """    #[cfg(windows)]
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    #[cfg(not(windows))]
    execute!(
        terminal.backend_mut(),
        PopKeyboardEnhancementFlags,
        LeaveAlternateScreen
    )?;"""
    if source.count(old_setup) != 1 or source.count(old_teardown) != 1:
        raise SystemExit(f"Upstream changed or patch already applied: {rel}")
    source = source.replace(old_setup, new_setup).replace(old_teardown, new_teardown)
    path.write_text(source, encoding="utf-8")
    print(f"Patched and verified: {rel}")
