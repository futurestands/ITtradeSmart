# NAS100 AI Lab to SmartHub APK: Research Dashboard Phase 2

Branch: feature/nas100-apk-research-dashboard (based on fix/v5-trustworthy-backtest-phase1).
Integration status: source changes committed; Gateway tests, Android build and physical phone connection still need verification.

## Our two-project architecture

- NAS100 Lab: synthetic candidate detection, walk-forward models, causal confluence, next-open hypothetical fills, synthetic cost/path stress. Real-data training is NOT authorized.
- SmartHub Windows Gateway: existing device-authenticated HTTPS-facing interface; existing AI companion remains MODEL_NOT_READY.
- Android APK: existing AI connection card and NEW separate read-only NAS100 research card.

## Gateway endpoint and source

GET /api/v5/ai/research-progress is authenticated using the existing monitoring-device token.
The Gateway reads only one fixed local Lab file: reports/synthetic_confluence_stress.json under the server-only SMARTHUB_NAS100_LAB_ROOT directory.
Neither the phone nor any client request supplies a file path. The server rejects symlinks, oversized files, malformed/duplicate/nonfinite JSON, unapproved model claims and unsafe per-run flags.
Gateway response is a small allowlisted summary: number of synthetic paths, hypothetical cost scenarios, experiments and per-setup/model positive Brier-score counts.
Source is labeled LOCAL_UNATTESTED_SYNTHETIC_REPORT. This is NOT a real broker feed, trained model, win probability or trading signal.

## APK display

The existing Check AI Lab connection button remains unchanged.
A new Refresh NAS100 Research Progress button displays the synthetic report and explicitly states MODEL_NOT_READY, REAL MARKET INFERENCE DISABLED and TRADE EXECUTION DISABLED.
No order sizing, bot-mode, risk guardian, token storage or execution APIs were changed.

## One-time safe Windows setup

Use a NEW SmartHub folder to avoid overwriting existing local APK work:
PowerShell: git clone --branch feature/nas100-apk-research-dashboard --single-branch https://github.com/futurestands/ITtradeSmart.git "$env:USERPROFILE\Documents\ITtradeSmart-NAS100-Integration"

The existing local NAS100 Lab is at C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B.
Pull its current feature branch and run its tests. Re-generate reports/synthetic_confluence_stress.json with the latest per-run synthetic-only flags because the previous stress report was created before the bug fix. The previously reported 424 passed / 1 failed run does not verify the fix.

Set SMARTHUB_NAS100_LAB_ROOT=C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B in the Windows Gateway PROCESS environment before starting the Gateway.
The backend directory inside the new checkout is ITTraderSmartHub_v4\backend. Reuse its approved separate Gateway environment and run python -m pytest -q tests.

Open ITTraderSmartHub_v4\android_project in Android Studio. Run testDebugUnitTest and assembleDebug. Install to the paired Android device through Android Studio after checking signature compatibility with the already-installed package. Do not uninstall and lose app data just to bypass a signing mismatch.

Phone connectivity requires the existing authenticated TLS Gateway reachable over a private approved network. Android 127.0.0.1 is the phone itself, not the Windows computer. Never expose the Flask development port or the Lab-only port to the internet.

## Verification checklist

1. Validate Lab report is regenerated with strict synthetic per-run flags.
2. Run complete SmartHub Gateway Python unit tests.
3. Run Android JVM tests and assembleDebug in Android Studio.
4. Enroll an Android monitoring device and verify the existing AI connection card.
5. Refresh NAS100 Research Progress and check real reported scenario counts.
6. Check report absent, invalid and service offline behavior; all must fail closed.
7. Confirm the APK offers no AI-enabled trade approval or execution behavior.

## Safety boundaries

No real USTECH100M predictions; no real broker clock/DST or costs have been independently approved. No model artifacts, authentic CSV, account information, broker secrets or Lab tokens are made available to Android.
All previous v1 Lab companion contracts are preserved. This feature never makes an inference request or places any live, paper or demo orders.

## Android installation signature mismatch — isolated research debug build

On the user's device, \`adb install -r app-debug.apk\` failed with:

\`INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package com.ittrader.smarthub signatures do not match newer version\`.

This is not an APK compilation error. Android will not update an existing package using a mismatched signing certificate. **Do not uninstall the existing SmartHub package**, which may contain locally secured credentials and app settings.

The Android Gradle **debug** build now uses \`applicationIdSuffix '.research'\`, resulting in \`com.ittrader.smarthub.research\`. A debug-only manifest overlay displays the launcher label **ITTrader NAS100 Research**. The release application ID, original Kotlin/Java namespace \`com.ittrader.smarthub\`, existing signed installed package and its data are unchanged.

To use on a paired Redmi / Android device:

~~~powershell
Set-Location "C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4\android_project"
git pull --ff-only
.\gradlew.bat --no-daemon testDebugUnitTest assembleDebug
if ($LASTEXITCODE -ne 0) { throw "APK build failed" }

$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$apk = Join-Path (Get-Location) "app\build\outputs\apk\debug\app-debug.apk"
& $adb devices -l
# Choose the current connected device serial from the output; wireless ports rotate.
$device = "REPLACE_WITH_CURRENT_ADB_SERIAL"
& $adb -s $device install -r $apk
if ($LASTEXITCODE -ne 0) { throw "Research APK install failed; preserve existing SmartHub app" }
& $adb -s $device shell monkey -p com.ittrader.smarthub.research -c android.intent.category.LAUNCHER 1
~~~

The research build is a separate app, **so it has its own Android Keystore and enrollment state**. It will not inherit the existing application's login/session/device ID. Any future secure Gateway pairing must use a new authorized monitoring-device enrollment and an approved HTTPS/private-network path. Do not transfer secrets by copying the original app's storage.

Do not execute words such as \`Performing Streamed Install\` or \`Success\` as PowerShell commands; those are *sample output*, not instructions.

**Status:** debug-side-by-side code committed; the user must still verify the new Gradle build, actual device installation and launch. No install success has been claimed.


## Physical APK launch verified; local ADB-reverse test mode

The user verified **after** installation that:

- The debug research package installed successfully via wireless ADB.
- \`am start -W -n com.ittrader.smarthub.research/com.ittrader.smarthub.MainActivity\` returned \`Status: ok\` and \`LaunchState: WARM\`.
- \`pidof com.ittrader.smarthub.research\` returned a running PID (4978).
- A recent filtered log excerpt did not show an \`AndroidRuntime FATAL EXCEPTION\`. Older \`monkey\` output mentioned tombstones, but did not identify the SmartHub process as the faulting process.

**Do not claim the NAS100 card's actual rendering has been visually confirmed until the phone is inspected.**

### ADB-only temporary local research Gateway route

For a phone already paired with wireless ADB, use \`adb reverse tcp:5000 tcp:5000\` to map the phone's \`127.0.0.1:5000\` to the Windows host's \`127.0.0.1:5000\`. This does **not** require making Flask accessible via the Wi-Fi LAN, VPN, public port-forwarding or reverse proxy.

**Important:** Android target SDK 34 defaults to disallow cleartext. The separate **debug-only** APK now declares \`@xml/nas100_debug_network_security\` which allows cleartext only to the literal \`127.0.0.1\`; its base policy rejects cleartext to all other destinations. Release app manifests and release network policy were not modified. This exception is exclusively for local developer verification over the authorized ADB debugging transport, **not** a production network architecture. Android's HTTPS TLS validation remains enabled for all HTTPS targets.

Required Windows process environment for the Gateway:

~~~powershell
$env:SMARTHUB_NAS100_LAB_ROOT = 'C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B'
# Only on your host, not in the Android UI or GitHub:
$env:SMARTHUB_API_TOKEN = & .\.venv-gateway\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(48))'
~~~

From the SmartHub backend folder, launch the existing Gateway \`app.py\`, which binds to Windows \`127.0.0.1:5000\`. Do not bind to \`0.0.0.0\`. A local API admin can create a one-time pairing code with \`POST /api/v4/admin/pairing-code\`, authenticated with the host-only master token. The code is short-lived; display it only to the person holding the phone, never save it in source code or send master token to Android.

With the phone connected, run:

~~~powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$device = 'REPLACE_WITH_CURRENT_CONNECTED_SERIAL'
& $adb -s $device reverse tcp:5000 tcp:5000
& $adb -s $device reverse --list
~~~

Rebuild \`testDebugUnitTest assembleDebug\` **after** updating this debug-only network policy and reinstall only the \`com.ittrader.smarthub.research\` APK. In the app's Gateway URL input use \`http://127.0.0.1:5000\`, then pair the app as a **new** device using the one-time code; do not enter the server's master token. Press **Refresh NAS100 Research Progress**. Its local synthetic report should show 3 price paths × 2 hypothetical cost scenarios = 6 studies.

The separate **Check AI Lab connection** card is expected to show unavailable unless the independent loopback companion is separately configured. That does not prevent the new research-progress endpoint from working.

After a local session, \`adb -s $device reverse --remove tcp:5000\` removes this tunnel. Android's wireless ADB connection may rotate ports between sessions. Never direct this setup at real orders.

### Security limitation

This debug-only path provides a temporary development transport via ADB, not a production deployment. Other locally running apps on the same debugging device could potentially attempt to reach local forwarded ports, so endpoint authentication remains mandatory and master tokens must stay in the Windows host environment. Revoke temporary device enrollment after testing or let its 24-hour expiry lapse. If the debugging connection is interrupted, the forward may disappear. Do not port-forward the raw Flask development server to a LAN or the internet.
