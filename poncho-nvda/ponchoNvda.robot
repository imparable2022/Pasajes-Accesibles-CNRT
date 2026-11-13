*** Settings ***
Documentation    Poncho: genuine NVDA speech regression tests in Chrome.
Library    NvdaLib.py
Library    ChromeLib.py
Library    PonchoNvdaTests.py
Library    ScreenCapLibrary
Test Setup    Start NVDA    standard-dontShowWelcomeDialog.ini
Test Teardown    Close NVDA Test
Force Tags    poncho    nvda    chrome

*** Keywords ***
Close NVDA Test
    Run Keyword And Ignore Error    Close Chrome Tab
    Run Keyword And Ignore Error    Dump Speech To Log
    Quit NVDA

*** Test Cases ***
SVG baseline - unnamed feature
    Verify Svg    before
SVG corrected - named feature
    Verify Svg    after
Breadcrumb baseline - hidden link in tab order
    Verify Breadcrumb    before
Breadcrumb corrected - skip hidden links
    Verify Breadcrumb    after
Panel baseline - resize resets user choice
    Verify Panel    before
Panel corrected - resize preserves user choice
    Verify Panel    after
Combobox baseline - NVDA announcement
    Verify Combobox    before
Combobox corrected - NVDA announcement
    Verify Combobox    after

Combobox baseline - three results, arrows and Escape with NVDA
    Verify Combobox Navigation    before
Combobox corrected - three results, arrows and Escape with NVDA
    Verify Combobox Navigation    after
Dialog baseline - NVDA focus and Escape
    Verify Dialog    before
Dialog corrected - NVDA focus and Escape
    Verify Dialog    after
