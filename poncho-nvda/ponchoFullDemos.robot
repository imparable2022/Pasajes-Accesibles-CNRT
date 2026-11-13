*** Settings ***
Documentation    Broad NVDA + Chrome smoke navigation of all Poncho HTML demo pages.
Library    NvdaLib.py
Library    ChromeLib.py
Library    PonchoFullDemos.py
Test Setup    Start NVDA    standard-dontShowWelcomeDialog.ini
Test Teardown    Quit NVDA
Force Tags    poncho-full    nvda    chrome

*** Test Cases ***
Visit Every Official HTML Demo With NVDA And Keyboard
    Check All Demo Pages With Nvda
