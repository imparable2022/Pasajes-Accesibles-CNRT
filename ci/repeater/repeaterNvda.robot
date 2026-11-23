*** Settings ***
Documentation    Real NVDA Windows console test for Repeater; record what NVDA actually speaks.
Library    NvdaLib.py
Library    RepeaterNvdaTests.py
Test Setup    Start NVDA    standard-dontShowWelcomeDialog.ini
Test Teardown    Close Repeater Test
Force Tags    repeater    nvda

*** Keywords ***
Close Repeater Test
    Run Keyword And Ignore Error    Stop Repeater
    Run Keyword And Ignore Error    Dump Speech To Log
    Quit NVDA

*** Test Cases ***
Read a question and answer using NVDA in a genuine Windows console
    Start Repeater
    Read Question With NVDA
    Reveal Answer With Keyboard
    Grade And Exit With Keyboard
