*** Settings ***
Documentation    Independent Chrome MathCAT control with real NVDA, not an Anki conformance claim.
Library    NvdaLib.py
Library    ChromeLib.py
Library    MathCATChromeControl.py
Test Setup    Start NVDA    standard-dontShowWelcomeDialog.ini
Test Teardown    Close Control
Force Tags    anki    mathcat    chrome

*** Keywords ***
Close Control
    Run Keyword And Ignore Error    Close Chrome Tab
    Run Keyword And Ignore Error    Dump Speech To Log
    Quit NVDA

*** Test Cases ***
MathCAT should recognize native MathML in Chrome
    Verify Mathcat In Chrome
