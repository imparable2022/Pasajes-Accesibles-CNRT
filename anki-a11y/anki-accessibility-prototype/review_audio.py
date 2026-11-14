"""Optional accessible Replay Audio button for Anki reviewer's bottom toolbar.

This uses exactly the same Reviewer.replayAudio() as the built-in R/F5 keys;
there is no parallel media player, audio duplication, or interception of R.
"""
from . import HERE, OPTIONS, CI_MODE, gui_hooks
from aqt.reviewer import ReviewerBottomBar

BRIDGE = "anki-a11y-replay-current-audio"
BUTTON_ID = "anki-a11y-replay-audio"

def inject_button(web_content, context):
    if not OPTIONS.get("enable_audio_replay_button", False):
        return
    if not isinstance(context, ReviewerBottomBar):
        return
    button = (
        '<button type="button" id="' + BUTTON_ID +
        '" aria-label="Replay audio (R)" title="Replay audio (R)"'
        ' onclick="pycmd(\'' + BRIDGE + '\')" hidden>'
        'Replay audio (R)</button>'
    )
    # Use the existing edit-button cell. This retains the size of the main
    # Show Answer / grade controls, avoids creating a new floating overlay,
    # and leaves all ordinary reviewer shortcuts unchanged.
    needle = '<td align=start valign=top class=stat>'
    if needle in web_content.body:
        web_content.body = web_content.body.replace(needle, needle + button, 1)

def handle_command(handled, message, context):
    if handled[0] or message != BRIDGE:
        return handled
    if not isinstance(context, ReviewerBottomBar):
        return handled
    reviewer = context.reviewer
    if reviewer.card and reviewer.state in ("question","answer"):
        reviewer.replayAudio()
        if CI_MODE:
            HERE.joinpath("replay-button-invoked.marker").write_text(
                "replayed via accessible HTML button", encoding="utf-8")
    return (True, None)

def update_button(card, question):
    if not OPTIONS.get("enable_audio_replay_button", False):
        return
    from aqt import mw
    if not mw or not mw.reviewer or not card:
        return
    try:
        has_audio = bool(card.question_av_tags()) if question else bool(
            card.answer_av_tags() or (card.replay_question_audio_on_answer_side()
                                      and card.question_av_tags())
        )
    except Exception:
        has_audio = False
    # The toolbar has its own QWebEngine. Do not focus the button merely
    # because its visibility changed; NVDA can discover it with Tab.
    show = "false" if has_audio else "true"
    mw.reviewer.bottom.web.eval(
        "(function(){var el=document.getElementById('%s');"
        "if(el) el.hidden=%s;})();" % (BUTTON_ID,show)
    )

def register_audio_hooks():
    gui_hooks.webview_will_set_content.append(inject_button)
    gui_hooks.webview_did_receive_js_message.append(handle_command)
    gui_hooks.reviewer_did_show_question.append(
        lambda card: update_button(card, True))
    gui_hooks.reviewer_did_show_answer.append(
        lambda card: update_button(card, False))
