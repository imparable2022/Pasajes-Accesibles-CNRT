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
    demos=sorted(p for p in (ROOT/"upstream").rglob("*.html")
                 if "/demo/" in p.relative_to(ROOT/"upstream").as_posix())
    if len(demos)<60:
        raise AssertionError(f"Missing demos: {len(demos)}")
    full_count=len(demos)
    demos=[p for i,p in enumerate(demos) if i%SHARDS==SHARD]
    print(f"NVDA shard {SHARD}/{SHARDS}: {len(demos)} of {full_count} demos",flush=True)

    report=[]
    for n,demo in enumerate(demos,1):
        relative=demo.relative_to(ROOT/"upstream").as_posix()
        print(f"[{n}/{len(demos)}] NVDA demo {relative}",flush=True)
        record=dict(path=relative,status="pending",speech=[],error=None)
        try:
            iframe_title="Demostración original de Poncho "+relative
            iframe_source=demo.as_uri()
            html = (f'<h2>Prueba de Poncho: {relative}</h2>'
                f'<iframe title="{iframe_title}" src="{iframe_source}" '
                'width="1150" height="760"></iframe>')
            # ChromeLib is taken unchanged from nvaccess/nvda. It ensures
            # the page loaded, foreground app is Chrome, and NVDA speech is ready.
            _chrome.prepareChrome(html)
            for step in range(5):
                actual=_chrome.getSpeechAfterTab()
                record["speech"].append(actual[:500])
            record["status"]="visited" if any(x.strip() for x in record["speech"]) else "no-speech"
        except Exception as error:
            record["status"]="error"
            record["error"]=str(error)[:900]
            record["traceback"]=traceback.format_exc()[-1500:]
        finally:
            try:_chrome.close_chrome_tab()
            except Exception as error:
                record["closeError"]=str(error)[:200]
        report.append(record)
        # Save incrementally so test output survives runner cancellation.
        (OUTPUT/f"all-official-demos-{PHASE}-shard{SHARD}.json").write_text(
            json.dumps(dict(demoCount=len(demos),totalInventory=full_count,shard=SHARD,shards=SHARDS,visited=sum(x["status"]=="visited" for x in report),
                 noSpeech=sum(x["status"]=="no-speech" for x in report),
                 errors=sum(x["status"]=="error" for x in report),pages=report),
                 indent=2,ensure_ascii=False),encoding="utf-8"
        )
    failures=[x for x in report if x["status"]!="visited"]
    _builtIn.log(f"Full demo audit: {len(demos)} pages; {len(failures)} failures",level="INFO")
    if failures:
        raise AssertionError(f"{len(failures)} demos without successful NVDA Tab smoke test. "
           f"See all-official-demos-{PHASE}-shard{SHARD}.json, e.g. {failures[:3]}")
