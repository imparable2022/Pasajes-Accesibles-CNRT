*** Settings ***
Documentation    Anki Desktop keyboard-only NVDA functional audit with independent database postconditions.
Library    NvdaLib.py
Library    AnkiNvdaTests.py
Test Setup    Start NVDA    standard-dontShowWelcomeDialog.ini
Test Teardown    Close Test
Force Tags    anki    nvda

*** Keywords ***
Close Test
    Run Keyword And Ignore Error    Stop Anki
    Run Keyword And Ignore Error    Dump Speech To Log
    Quit NVDA

*** Test Cases ***
Create deck add card study grade and browse with keyboard and NVDA
    Start Anki
    Create Deck Via Keyboard
    Add Card Via Keyboard
    Study With Keyboard
    Browser Via Keyboard
