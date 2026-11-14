"use strict";
/* Browserless, deterministic DOM-policy and focus regression harness.
 * This does not replace Windows NVDA or cross-screen-reader testing.
 * Input: JSON {"cases":[{"name", "source", "text", "tags", ...}]}.
 */
const vm = require("node:vm");
const fs = require("node:fs");

function runReviewer(test) {
    const hooks = [];
    const attrs = {...(test.initialAttrs || {})};
    const dataset = {};
    let focusCount = 0;
    const ownerDocument = {
        activeElement: {id: "original-control"},
        createRange() {
            return {
                setStartAfter() {},
                setEnd() {},
                cloneContents() {
                    return {
                        textContent: test.answerText || "",
                        querySelectorAll() {return [];},
                    };
                },
            };
        },
    };
    const qa = {
        innerText: test.text || "",
        ownerDocument, childNodes: [], dataset,
        getAttribute(name) {
            return Object.hasOwn(attrs, name) ? attrs[name] : null;
        },
        hasAttribute(name) {return Object.hasOwn(attrs, name);},
        setAttribute(name, value) {attrs[name] = String(value);},
        removeAttribute(name) {delete attrs[name];},
        querySelectorAll(selector) {
            if (selector === ".cloze") {
                return (test.clozeItems || []).map(item => ({innerText: item}));
            }
            return [];
        },
        querySelector(selector) {
            if (selector === "#answer") return test.answerMarker ? {} : null;
            const tags = test.tags || [];
            for (const candidate of selector.split(",")) {
                const token = candidate.trim().toLowerCase();
                const tag = (token.match(/^[a-z0-9-]+/) || [""])[0];
                if (tags.includes(token) || (tag && tags.includes(tag))) {
                    return {tag};
                }
            }
            return null;
        },
        focus() {
            focusCount++;
            ownerDocument.activeElement = qa;
        },
    };
    const win = {__ankiA11yPreviousQuestion: test.previousQuestion || ""};
    if (test.priorPatch) {
        win.__ankiA11yReviewFocusState = {
            node: qa,
            attrs: {...(test.savedAttrs || {
                role: null, tabindex: null, "aria-label": null,
            })},
        };
    }
    const doc = {getElementById(id) {return id === "qa" ? qa : null;}};
    const context = {document: doc, window: win, onShownHook: hooks,
                     console, setTimeout: fn => fn()};
    vm.createContext(context);
    const matched = (test.source || "").match(/<script>([\s\S]*?)<\/script>/);
    if (matched) {
        vm.runInContext(matched[1], context, {timeout: 2000});
        for (const callback of hooks) callback();
    }
    return {
        focusCount, attrs, dataset,
        active: ownerDocument.activeElement === qa ? "card" : "unchanged",
        previousQuestion: win.__ankiA11yPreviousQuestion,
        scriptPresent: Boolean(matched),
    };
}

function makeElement() {
    const attributes = {};
    return {
        getAttribute(name) {
            return Object.hasOwn(attributes,name) ? attributes[name] : null;
        },
        setAttribute(name,value) {attributes[name] = String(value);},
    };
}

function runEditor(test) {
    const rich = makeElement();
    const plain = makeElement();
    const shadow = {querySelectorAll(selector) {
        return selector.includes("anki-editable") ? [rich] : [];
    }};
    const host = {shadowRoot: shadow};
    const name = {textContent: test.fieldName || "Front"};
    const container = {
        querySelector(selector) {
            return selector === ".label-name" ? name : null;
        },
        querySelectorAll(selector) {
            if (selector === ".rich-text-editable") return [host];
            if (selector === ".CodeMirror textarea") return [plain];
            return [];
        },
    };
    const body = {};
    const doc = {body,querySelectorAll(selector) {
        return selector === ".field-container[data-index]" ? [container] : [];
    }};
    const observers = [];
    class MutationObserver {
        constructor(callback) {this.callback = callback; observers.push(this);}
        observe() {}
    }
    const win = {};
    const context = {document: doc,window: win, MutationObserver, WeakSet,
       Element: class {}, requestAnimationFrame: fn => fn(), console};
    vm.createContext(context);
    vm.runInContext(test.editorScript, context, {timeout: 2000});
    const initial = {rich: rich.getAttribute("aria-label"),
                     plain: plain.getAttribute("aria-label")};
    name.textContent = test.updatedFieldName || "Custom Back";
    observers[0].callback([{type:"characterData"}]);
    const updated = {rich: rich.getAttribute("aria-label"),
                     plain: plain.getAttribute("aria-label")};
    return {initial, updated, observerCount: observers.length};
}

const payload = JSON.parse(fs.readFileSync(0,"utf8"));
process.stdout.write(JSON.stringify((payload.cases || []).map(c =>
    ({name:c.name, ...(c.editorScript?runEditor(c):runReviewer(c))})
)));
