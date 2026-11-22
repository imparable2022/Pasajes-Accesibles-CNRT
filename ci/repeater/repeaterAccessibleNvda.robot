*** Settings ***
Documentation    Real NVDA and independent SQLite check for line-oriented Repeater study.
Library    NvdaLib.py
Library    AccessibleRepeaterNvdaTests.py
Test Setup    Start NVDA    standard-dontShowWelcomeDialog.ini
Test Teardown    Close Accessible Study
Force Tags    repeaterAccessible    nvda

*** Keywords ***
Close Accessible Study
    Run Keyword And Ignore Error    Stop Accessible Repeater
    Run Keyword And Ignore Error    Dump Speech To Log
    Quit NVDA

*** Test Cases ***
Review card via accessible console and verify persisted SQLite grade
    Start Accessible Repeater
    Reveal Accessible Answer
    Grade And Verify DB
