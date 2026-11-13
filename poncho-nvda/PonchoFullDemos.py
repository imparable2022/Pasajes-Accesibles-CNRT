"""Navigate every official Poncho HTML demonstration with actual NVDA + Chrome.

This is a broad *screen-reader smoke test*, not a claim of full manual WCAG
compliance. Each original HTML demo is loaded inside a titled iframe so
its original external and relative resources are still used. Reports include
any demo that fails to load, plus exact NVDA speech during initial Tab visits.
"""
from pathlib import Path
import json
import os
import re
import traceback

from robot.libraries.BuiltIn import BuiltIn
from SystemTestSpy import _getLib
from ChromeLib import ChromeLib
import NvdaLib

_chrome = _getLib("ChromeLib")
_builtIn=BuiltIn()
ROOT=Path.cwd().parent
OUTPUT=ROOT/"poncho-nvda"/"speech-results"
OUTPUT.mkdir(parents=True,exist_ok=True)
PHASE=os.environ.get("PONCHO_PHASE", "before")
SHARD=int(os.environ.get("PONCHO_SHARD", "0"))
SHARDS=int(os.environ.get("PONCHO_SHARDS", "1"))

def check_all_demo_pages_with_nvda():
    """Visit each demo in Chrome and record raw NVDA speech without waiting for silence.

    The upstream ChromeLib.prepareChrome() waits for all speech to finish. Full
    dynamic iframe demos continuously update their virtual buffer and can make
    this wait time out on EVERY page. Reuse ChromeLib.start_chrome() for the
    real browser launch/foreground tracking, and capture spy speech directly.
    """
    import tempfile
    from html import escape

    all_demos=sorted(p for p in (ROOT/"upstream").rglob("*.html")
                 if "/demo/" in p.relative_to(ROOT/"upstream").as_posix())
    if len(all_demos)<60:
        raise AssertionError(f"Missing demos: {len(all_demos)}")
    full_count=len(all_demos)
    demos=[p for i,p in enumerate(all_demos) if i%SHARDS==SHARD]
    print(f"NVDA shard {SHARD}/{SHARDS}: {len(demos)} of {full_count}",flush=True)

    spy=NvdaLib.getSpyLib()
    report=[]
    def press(key, delay=0.7):
        index=spy.get_next_speech_index()
        spy.emulateKeyPress(key,blockUntilProcessed=False)
        _builtIn.sleep(f"{delay} seconds")
        return spy.get_speech_at_index_until_now(index)[:700]

    for n,demo in enumerate(demos,1):
        relative=demo.relative_to(ROOT/"upstream").as_posix()
        print(f"[{n}/{len(demos)}] NVDA demo {relative}",flush=True)
        record=dict(path=relative,status="pending",speech=[],error=None)
        testcase=f"Poncho Official Demo {relative} phase={PHASE} shard={SHARD}"
        # The demo stays unmodified, in an iframe with its original relative
        # resource URLs; the wrapper only gives a predictable browser title.
        title=ChromeLib.getUniqueTestCaseTitle(testcase)
        wrapper=(f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
                 f'<title>{escape(title)}</title></head><body>'
                 f'<h1>Prueba de demostración Poncho</h1>'
                 f'<iframe title="{escape(relative)}" src="{escape(demo.as_uri())}" '
                 f'width="1150" height="760"></iframe>'
                 f'<p id="end">Fin de la demostración</p></body></html>')
        path=Path(tempfile.gettempdir())/f"poncho-{PHASE}-{SHARD}-{n}.html"
        path.write_text(wrapper,encoding="utf-8")
        try:
            _chrome.start_chrome(str(path),testcase)
            record["browserLaunched"]=True
            _builtIn.sleep("1 second")
            record["speech"].append(press("control+F6"))
            record["speech"].append(press("tab"))
            record["speech"].append(press("tab"))
            record["speech"].append(press("tab"))
            record["speech"].append(press("tab"))
            record["speech"].append(press("NVDA+tab"))
            # An empty speech trace is NOT counted as successfully checked.
            record["status"]="visited" if any(s.strip() for s in record["speech"]) else "no-speech"
        except Exception as error:
            record["status"]="error"
            record["error"]=str(error)[:500]
            record["traceback"]=traceback.format_exc()[-1300:]
        finally:
            try:
                # Don't wait for dynamic demo speech to settle; close tab with
                # a fire-and-forget NVDA keystroke, not ChromeLib.close_chrome_tab.
                spy.emulateKeyPress("control+w",blockUntilProcessed=False)
                _builtIn.sleep("0.45 seconds")
            except Exception as error:
                record["closeError"]=str(error)[:200]

        report.append(record)
        (OUTPUT/f"all-official-demos-{PHASE}-shard{SHARD}.json").write_text(
            json.dumps(dict(demoCount=len(demos),totalInventory=full_count,
                 shard=SHARD,shards=SHARDS,
                 visited=sum(x["status"]=="visited" for x in report),
                 noSpeech=sum(x["status"]=="no-speech" for x in report),
                 errors=sum(x["status"]=="error" for x in report),pages=report),
                 indent=2,ensure_ascii=False),encoding="utf-8"
        )
    failures=[x for x in report if x["status"]!="visited"]
    _builtIn.log(f"NVDA basic demo smoke: {len(demos)} pages; {len(failures)} failures",
        level="INFO")
    if failures:
        raise AssertionError(f"{len(failures)} demos without successful NVDA Chrome smoke. "
           f"First errors: {[(x['path'],x['error']) for x in failures[:3]]}")
