# SamStudy StudyShield

Android companion for the SamStudy StudyShield feature.

## What it does
- Lists launchable apps on the device.
- Lets the user set a separate daily minute limit for each app.
- Uses Android Usage Access to read daily foreground usage.
- Uses an Accessibility Service to redirect an app to a StudyShield lock screen after its limit is reached.
- Resets usage naturally at the next calendar day.

## Required permissions
1. Install the app.
2. Open **Usage Access Settings** and allow SamStudy StudyShield.
3. Open **Accessibility Settings** and enable SamStudy StudyShield.
4. Set individual limits for the apps you want to control.

## Important Android limitation
A normal Android app cannot guarantee that the user cannot uninstall or force-stop it. The included implementation enforces limits while the Accessibility service remains enabled. Device-owner / enterprise kiosk management is required for stronger tamper resistance.
