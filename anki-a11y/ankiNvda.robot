*** Settings ***
Documentation    Experimental real NVDA keyboard/speech smoke for Anki Windows.
Library    NvdaLib.py
Library    AnkiNvdaTests.py
Test Setup    Start NVDA    standard-dontShowWelcomeDialog.ini
Test Teardown    Close Test
Force Tags    anki    nvda

*** Keywords ***
Close Test
    Run Keyword And Ignore Error    Stop Anki For Testing
    Run Keyword And Ignore Error    Dump Speech To Log
    Quit NVDA

*** Test Cases ***
Keyboard journey and live NVDA speech
    Start Anki For Testing
    Inspect Keyboard Journey
