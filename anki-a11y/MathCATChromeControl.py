"""Control experiment: direct MathML in Chrome + real NVDA MathCAT.

Compare speech from the same structures with the Qt WebEngine Anki reviewer.
The browser control is not proof that Anki is accessible.
"""
import json
import os
from pathlib import Path
from robot.libraries.BuiltIn import BuiltIn
from SystemTestSpy import _getLib
from ChromeLib import ChromeLib
import NvdaLib

chrome: ChromeLib = _getLib("ChromeLib")
robot = BuiltIn()
output = Path(os.environ.get("ANKI_A11Y_OUTPUT",".")) / "chrome-mathcat-control.json"
cases = {
    "fraction": """<mrow><mfrac><mn>1</mn><mn>2</mn></mfrac><mo>+</mo>
                    <mfrac><mn>1</mn><mn>4</mn></mfrac></mrow>""",
    "power": """<mrow><msup><mi>x</mi><mn>2</mn></msup><mo>+</mo>
                 <msup><mi>y</mi><mn>3</mn></msup></mrow>""",
    "equation": """<mrow><mn>2</mn><mi>x</mi><mo>+</mo><mn>3</mn>
                    <mo>=</mo><mn>7</mn></mrow>""",
}
records = []

def verify_mathcat_in_chrome():
    for kind,body in cases.items():
        html = f"""<!doctype html><html lang="en"><head><meta charset="UTF-8">
        <title>NVDA MathCAT independent control {kind}</title></head>
        <body><h1>Math structure: {kind}</h1>
        <math xmlns="http://www.w3.org/1998/Math/MathML"
              display="block" tabindex="0" role="math">{body}</math></body></html>"""
        chrome.prepareChrome(html)
        spy = NvdaLib.getSpyLib()
        utterances = []
        for gesture in ["control+home","downArrow","downArrow","NVDA+tab"]:
            utterances.append({"gesture":gesture,"speech":NvdaLib.getSpeechAfterKey(gesture)})
        # Tab focus is sometimes more reliable in Chrome than browse-mode math.
        for gesture in ["tab","NVDA+alt+m"]:
            utterances.append({"gesture":gesture,"speech":NvdaLib.getSpeechAfterKey(gesture)})
        entry = utterances[-1]["speech"]
        if "not math" not in entry.casefold():
            for gesture in ["space","downArrow","rightArrow","space","escape"]:
                utterances.append({"gesture":gesture,"speech":NvdaLib.getSpeechAfterKey(gesture)})
        spoken = " ".join(str(v["speech"]) for v in utterances).casefold()
        # Seeing the word "math" is not success: in the first control run
        # NVDA recognized a math object but its MathCAT engine reported
        # "Error in starting navigation of math" and "Error in navigating math".
        errors = [item["speech"] for item in utterances
                  if "error in" in item["speech"].casefold() or "not math" in item["speech"].casefold()]
        after_entry = " ".join(str(item["speech"]) for item in utterances[6:]).casefold()
        mathcat = (not errors and
                   "not math" not in entry.casefold() and
                   any(token in after_entry for token in
                       ("numerator","denominator","fraction","power","squared","cubed","equal")))
        records.append({"kind":kind,"entry":entry,"mathcat_usable":mathcat,"utterances":utterances})
        output.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
        robot.log(f"Chrome MathCAT {kind}: {records[-1]}")
    if not any(x["mathcat_usable"] for x in records):
        raise AssertionError("Even direct Chrome MathML was not recognized as MathCAT in this control; see logs")
