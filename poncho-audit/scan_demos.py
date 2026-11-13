#!/usr/bin/env python3
"""Automated accessibility audit for ALL tracked Poncho HTML demos.

This is a browser / axe-core / keyboard audit, NOT an NVDA test.
Coverage and broken pages are recorded, not silently excluded.
Axe limitations: dynamic controls, screen-reader speech, semantics and
backend-dependent paths need manual/assistive-technology review.
"""
import argparse
import asyncio
import collections
import functools
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

BASE = Path(__file__).resolve().parents[1]
DEMO_ROOT = BASE / "upstream"
AXE = BASE / "node_modules" / "axe-core" / "axe.min.js"
OUT = BASE / "poncho-audit" / "results"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]

JS_PROBE = r"""() => {
  const body = document.body;
  if (!body) return {error: "missing body"};
  const controls = Array.from(document.querySelectorAll('button,a[href],input,select,textarea,[tabindex],[role="button"],[role="combobox"]'));
  const byID = {};
  for (const node of document.querySelectorAll("[id]")) {
     (byID[node.id] ||= []).push(node);
  }
  const dup = Object.entries(byID).filter(([_, a]) => a.length > 1).map(([id, a]) => ({id, count: a.length}));
  const dangling = [];
  for (const node of document.querySelectorAll('[aria-controls],[aria-labelledby],[aria-describedby],[aria-owns]')) {
     for (const attr of ['aria-controls','aria-labelledby','aria-describedby','aria-owns']) {
        for (const id of (node.getAttribute(attr) || "").trim().split(/\s+/).filter(Boolean)) {
          if (!document.getElementById(id)) dangling.push({attr,id,tag:node.tagName,element:node.outerHTML.slice(0,170)});
        }
     }
  }
  const labels = [];
  for (const node of document.querySelectorAll("input,textarea,select")) {
     if (node.type === 'hidden') continue;
     const name = node.getAttribute("aria-label") || node.labels?.[0]?.textContent?.trim() || node.getAttribute("title") || "";
     if (!name) labels.push(node.outerHTML.slice(0,180));
  }
  const dialogIssues = [];
  for (const node of document.querySelectorAll('dialog,[role="dialog"]')) {
     const style = getComputedStyle(node);
     const hasAriaModal = node.getAttribute("aria-modal") === 'true';
     if(hasAriaModal && node.tagName === 'DIALOG' && !node.open && style.display !== 'none')
         dialogIssues.push({kind:'aria-modal-but-dialog-not-open',outer:node.outerHTML.slice(0,260)});
  }
  return {
     title: document.title,
     headings: Array.from(document.querySelectorAll("h1")).map(x=>x.innerText.trim()).slice(0,10),
     interactive: controls.length,
     landmarks: document.querySelectorAll("main,header,nav,footer,aside,[role=main],[role=navigation]").length,
     duplicatedIds:dup.slice(0,75),
     missingAriaTargets:dangling.slice(0,80),
     unlabeledInputs:labels.slice(0,70),
     dialogIssues,
     bodyTextChars: body.innerText.length
  };
}"""

JS_TABS = r"""async (amount) => {
 const steps=[];
 for(let i=0;i<amount;i++){
    const el=document.activeElement;
    // Browser sends real Tab from Python, not script. This reads focus state only.
    if (el && el !== document.body && el !== document.documentElement) {
      const box=el.getBoundingClientRect();
      const s=getComputedStyle(el);
      steps.push({
         tag:el.tagName, id:el.id, text:(el.innerText||el.value||'').slice(0,65),
         offscreen:box.width>0 && (box.right<0 || box.bottom<0 || box.left>innerWidth || box.top>innerHeight),
         zeroSize:box.width===0 || box.height===0, display:s.display,
         visibility:s.visibility, hiddenAncestor:!!el.closest('[aria-hidden=true], [inert]'),
         outer:el.outerHTML.slice(0,160)
      });
    }
 }
 return steps;
}"""

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

def start_server(path):
    server = ThreadingHTTPServer(("127.0.0.1", 0),
        functools.partial(QuietHandler, directory=str(path)))
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

def simplify_violation(v):
    return dict(
        id=v.get("id"), impact=v.get("impact"), description=v.get("help"),
        helpUrl=v.get("helpUrl"), tags=v.get("tags",[]),
        nodes=[dict(target=n.get("target"), failureSummary=n.get("failureSummary"),
                    html=n.get("html","")[:340]) for n in v.get("nodes",[])[:18]],
        totalAffected=len(v.get("nodes",[]))
    )

async def audit_one(browser, semaphore, base_url, path, viewport, axe_src):
    async with semaphore:
        result={"path":path, "viewport":viewport["name"], "status":"not-loaded",
                "jsErrors":[], "badLocalResponses":[], "badExternalResponses":[],
                "violations":[], "incompleteCount":0}
        context=None
        try:
            context=await browser.new_context(
                viewport={"width":viewport["width"],"height":viewport["height"]},
                bypass_csp=True, locale="es-AR", color_scheme="light",
                ignore_https_errors=True)
            page=await context.new_page()
            page.on("pageerror",lambda err: result["jsErrors"].append(str(err)[:350]) if len(result["jsErrors"])<12 else None)
            def on_response(response):
                if response.status >= 400:
                    k="badLocalResponses" if "127.0.0.1:" in response.url else "badExternalResponses"
                    if len(result[k]) < 14: result[k].append(str(response.status)+" "+response.url[:200])
            page.on("response",on_response)
            try:
                response=await page.goto(base_url+"/"+path,wait_until="domcontentloaded",timeout=16000)
                result["httpStatus"]=response.status if response else None
                result["status"]="loaded" if response and response.ok else "response-error"
            except Exception as e:
                result["navigationError"]=str(e)[:350]
                result["status"]="navigation-error"
                # Continue with whatever document exists, if any.
            await page.wait_for_timeout(650)
            try: result["dom"]=await page.evaluate(JS_PROBE)
            except Exception as e: result["domError"]=str(e)[:350]
            try:
                # add_script_tag injects from the local installed axe-core file.
                await page.add_script_tag(content=axe_src)
                data=await asyncio.wait_for(page.evaluate(
                    """async (tags) => {
                      const report=await axe.run(document,{
                        runOnly:{type:"tag",values:tags},
                        resultTypes:["violations","incomplete"]
                      });
                      return {violations:report.violations,incompleteCount:report.incomplete.length,
                              inapplicableCount:report.inapplicable.length};
                    }""", TAGS), timeout=35)
                result["violations"]=[simplify_violation(v) for v in data["violations"]]
                result["incompleteCount"]=data["incompleteCount"]
            except Exception as e:
                result["axeError"]=str(e)[:420]
            try:
                tabs=[]
                for _ in range(12):
                    await page.keyboard.press("Tab")
                    item=await page.evaluate("""() => {
                      let e=document.activeElement;
                      if(!e || e===document.body) return null;
                      let r=e.getBoundingClientRect(),s=getComputedStyle(e);
                      return {tag:e.tagName,txt:(e.innerText||e.value||"").slice(0,55),
                          id:e.id,offscreen:r.width>0 && (r.right<0||r.bottom<0||r.left>innerWidth||r.top>innerHeight),
                          invisible:s.visibility==="hidden"||s.display==="none",
                          name:e.getAttribute("aria-label"),outer:e.outerHTML.slice(0,170)};
                    }""")
                    if item: tabs.append(item)
                result["keyboard"]=dict(tabSteps=tabs, offscreenTabs=sum(1 for x in tabs if x["offscreen"]))
            except Exception as e: result["keyboardError"]=str(e)[:200]
        except Exception as e:
            result["fatalError"]=str(e)[:400]
        finally:
            if context:
                try:await context.close()
                except Exception:pass
        return result

def summarize(results):
    count=collections.Counter()
    violations=collections.Counter()
    counts=collections.Counter()
    for x in results:
        count[x["status"]]+=1
        counts["jsErrorPages"]+=bool(x["jsErrors"])
        counts["badExternalPages"]+=bool(x["badExternalResponses"])
        counts["badLocalPages"]+=bool(x["badLocalResponses"])
        counts["axeFailedPages"]+=bool(x.get("axeError"))
        counts["pagesWithViolations"]+=bool(x["violations"])
        counts["offscreenFocusPages"]+=bool(x.get("keyboard",{}).get("offscreenTabs"))
        counts["missingAriaReferencesPages"]+=bool(x.get("dom",{}).get("missingAriaTargets"))
        counts["duplicateIdsPages"]+=bool(x.get("dom",{}).get("duplicatedIds"))
        for v in x["violations"]:
            violations[v["id"]]+=v.get("totalAffected",0)
    return dict(pageCount=len(results), loaded=count.get("loaded",0),
       statuses=dict(count), observations=dict(counts),
       violationNodesByRule=dict(violations.most_common()))

async def main(phase, max_concurrency):
    demos=sorted(p.relative_to(DEMO_ROOT).as_posix()
         for p in DEMO_ROOT.rglob("*.html")
         if "/demo/" in p.relative_to(DEMO_ROOT).as_posix())
    assert len(demos)>=60, f"Expected all official Poncho demos, got {len(demos)}"
    assert AXE.is_file(), "axe-core not installed, use npm install axe-core"
    axe_src=AXE.read_text(encoding="utf-8")
    server=start_server(DEMO_ROOT)
    base_url="http://127.0.0.1:"+str(server.server_port)
    viewports=[
        {"name":"desktop","width":1440,"height":900},
        {"name":"mobile","width":390,"height":844}]
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            semaphore=asyncio.Semaphore(max_concurrency)
            jobs=[audit_one(browser,semaphore,base_url,path,vp,axe_src)
                    for path in demos for vp in viewports]
            results=await asyncio.gather(*jobs)
            await browser.close()
    finally: server.shutdown()
    OUT.mkdir(parents=True,exist_ok=True)
    payload={"phase":phase,"origin":"argob/poncho:master",
      "pagesPerViewport":len(demos),"viewports":viewports,
      "summary":summarize(results),"pages":results}
    filepath=OUT/("all-demos-"+phase+".json")
    filepath.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Full demo audit:",phase,"pages=",len(demos),"views=",len(results))
    print(json.dumps(payload["summary"],ensure_ascii=False,indent=2))
    print("Results saved to",filepath)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["before","after"])
    parser.add_argument("--jobs",type=int,default=6)
    args=parser.parse_args()
    asyncio.run(main(args.phase,args.jobs))
