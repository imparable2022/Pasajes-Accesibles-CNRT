#!/usr/bin/env python3
"""Deep interaction checks for real PonchoMapSearch and PonchoMap dialog methods.

Executed in a real Chromium browser, before and after an isolated source patch.
Does NOT replace NVDA speech validation on Windows.
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM=ROOT/"upstream"
OUT=ROOT/"poncho-audit"/"results"
phase=sys.argv[1]
assert phase in ("before","after")

def extract_method(relative,method_name):
    lines=(UPSTREAM/relative).read_text("utf-8")
    start=lines.index("    "+method_name+" = ")
    end=lines.index("\n    };",start)+len("\n    };")
    return lines[start:end]

def run_search(browser):
    p=browser.new_page()
    p.set_content('''
       <h1>Prueba de búsqueda</h1>
       <div data-scope="a"><label for="input-a">Buscar A</label><input id="input-a" class="js-poncho-map-search__input"></div>
       <div data-scope="b"><label for="input-b">Buscar B</label><input id="input-b" class="js-poncho-map-search__input"></div>
       <button id="after">Después del buscador</button>
    ''')
    p.add_script_tag(path=str(UPSTREAM/"src/js/poncho-map/src/js/poncho-map-search.js"))
    p.evaluate("""() => {
      window.slugify=s=>String(s).toLowerCase();
      window.selected=[];
      for(const scope of ["a","b"]){
        const inst={
          id:"id",title:"name",headers:{},search_fields:[],
          scope_sufix:"--"+scope,
          _setSearchInputValue:name=>selected.push(["setValue",scope,name]),
          gotoEntry:(id,zoom,slider)=>selected.push(["goto",scope,id,zoom,slider])
        };
        const search=new PonchoMapSearch(inst,{scope,combobox:true,
                 datalist:false,combobox_options:{},debounce_delay:20});
        search.cachedDataEntries=[
          {id:"1",name:"Santa Fe",results:"san"},
          {id:"2",name:"San Justo",results:"san"},
          {id:"3",name:"San Javier",results:"san"}
        ];
        search.searcher();
      }
    }""")
    p.locator("#input-a").fill("sa")
    p.locator("#input-a").press("n")
    p.wait_for_timeout(80)
    before=p.evaluate("""() => ({
      expanded:document.querySelector("#input-a").getAttribute("aria-expanded"),
      inputControls:document.querySelector("#input-a").getAttribute("aria-controls"),
      popupRole:document.querySelector('[data-scope=a] [role=listbox]')?.getAttribute('role'),
      popupId:document.querySelector('[data-scope=a] [role=listbox]')?.id,
      options:document.querySelectorAll('[data-scope=a] [role=option]').length,
      optionsHaveLinks:document.querySelectorAll('[data-scope=a] [role=option] a[href]').length,
      allIds:[...document.querySelectorAll("[id]")].map(el=>el.id),
    })""")
    keys={}
    for key in ["ArrowDown","ArrowDown","ArrowUp","ArrowUp"]:
        p.keyboard.press(key)
        keys[key+"-"+str(len(keys))]=p.evaluate("""() => ({
          id:document.activeElement.id,
          text:document.activeElement.textContent.trim().slice(0,70),
          tag:document.activeElement.tagName
        })""")
    # Escape with focus on INPUT while list open.
    p.locator("#input-a").focus()
    p.keyboard.press("Escape")
    keys["escapeFromInput"]=p.evaluate("""() => ({
       expanded:document.querySelector("#input-a").getAttribute("aria-expanded"),
       popupCount:document.querySelectorAll('[data-scope=a] [role=option]').length
    })""")
    # Escape from first option: original code implements this.
    p.locator("#input-a").press("ArrowDown")
    p.keyboard.press("Escape")
    keys["escapeFromOption"]=p.evaluate("""() => ({
       expanded:document.querySelector("#input-a").getAttribute("aria-expanded"),
       value:document.querySelector("#input-a").value,
       focusedInput:document.activeElement.id==="input-a"
    })""")
    # Reload results; Enter on native result link should work as a real click.
    p.locator("#input-a").fill("sa")
    p.locator("#input-a").press("n")
    p.wait_for_timeout(80)
    p.locator("#input-a").press("ArrowDown")
    p.keyboard.press("Enter")
    keys["enterSelection"]=p.evaluate("""() => ({
      selection:window.selected,
      value:document.querySelector("#input-a").value,
      expanded:document.querySelector("#input-a").getAttribute("aria-expanded")
    })""")
    p.close()
    return dict(dom=before,keys=keys)

def run_dialog(browser):
    p=browser.new_page()
    p.set_content('''
      <h1>Prueba de panel</h1>
      <button id="trigger">Abrir información</button>
      <div class="poncho-map" data-scope="ponchomap"></div>
      <button id="outside">Control exterior</button>
    ''')
    path="src/js/poncho-map/src/js/poncho-map.js"
    scripts={name:extract_method(path,name)
      for name in ["_renderSlider","isSliderOpen","toggleSlider"]}
    state=p.evaluate("""(scripts) => {
       const context={
         no_info:false,render_slider:true,content_outside:false,
         scope_sufix:"--ponchomap",scope_selector:'[data-scope="ponchomap"]',
         slider_selector:"pm-slider",
         _t:key=>key,addAnchorElement:opts=>{
            let a=document.createElement("a");a.href="#dummy";return a;
         }
       };
       for(const [name,text] of Object.entries(scripts)){
          const arrow=text.slice(text.indexOf("=")+1).trim().replace(/;$/,"");
          context[name]=new Function("return ("+arrow+");").call(context);
       }
       context._renderSlider();
       const el=document.querySelector("dialog");
       const initial={open:el.open,visible:getComputedStyle(el).display};
       document.getElementById("trigger").focus();
       context.toggleSlider();
       const open={open:el.open,modal:el.matches(":modal"),
           ariaModal:el.getAttribute("aria-modal"),
           visible:getComputedStyle(el).display,
           focusTag:document.activeElement.tagName,
           activeId:document.activeElement.id,
           closeButtonAccessibleName:el.querySelector("button").getAttribute("aria-label")};
       return {initial,open};
    }""",scripts)
    p.keyboard.press("Tab")
    state["tabAfterOpen"]=p.evaluate("""() => ({
      id:document.activeElement.id,tag:document.activeElement.tagName,
      text:document.activeElement.textContent.trim().slice(0,100),
      insideDialog:!!document.activeElement.closest("dialog")
    })""")
    p.keyboard.press("Escape")
    state["afterEscape"]=p.evaluate("""() => ({
       open:document.querySelector("dialog").open,
       ariaModal:document.querySelector("dialog").getAttribute("aria-modal"),
       visible:getComputedStyle(document.querySelector("dialog")).display
    })""")
    p.close()
    return state

with sync_playwright() as engine:
    browser=engine.chromium.launch(headless=True)
    data=dict(phase=phase,search=run_search(browser),dialog=run_dialog(browser))
    browser.close()

OUT.mkdir(exist_ok=True,parents=True)
output=OUT/("deep-interactions-"+phase+".json")
output.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(data,ensure_ascii=False,indent=2))
print("Results saved:",output)
