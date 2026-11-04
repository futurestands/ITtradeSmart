# SmartHub Android UX — five-screen redesign (research-only)

**Status: Source committed; awaiting actual Windows Gradle/pytest and on-device UX verification.**
The original debugging APK was built and installed at baseline commit 9c0f439; that installation is **not** evidence that this newer navigation code builds. The published main app and investor-only broker protections are untouched. This work remains in the research debug flavor (\`com.ittrader.smarthub.research\`) on branch \`feature/nas100-apk-research-dashboard\`, draft PR #2.

## Problem

The previous Activity used a single 28 KB ScrollView with sequential numbered cards: market feed, Gateway pairing, bot controls, risk calculators, drawdown shield, infrastructure logs, alerts/research, NAS100/AI read-only status, broker profiles, and a monospaced terminal console. Reaching broker settings required scrolling through unrelated sections, and status feedback from other buttons appeared only at the end.

## UX implementation

The new Activity has a persistent small research-mode header, a single visible independently scrollable page, a short status strip, and a bottom navigation bar:

| Bottom tab | Content retained |
|---|---|
| Home | Live market ticker, quick links to Accounts/AI Lab/Risk, Gateway activity console |
| Accounts | MT5 profile chooser, broker name, account type, user-confirmed FTMO US100, save/remove, refresh |
| AI Lab | Existing AI status, NAS100 synthetic report + technical-details toggle, alerts/incident research |
| Risk | Bot safety controls, Pipnex position-size/risk calculator, prop-firm drawdown check and MT5 read-only sync |
| Settings | Gateway URL, one-time device pairing/revocation, infrastructure log stress analyzer |

The page header/subtitle change with navigation. Page selection is saved/restored across Activity recreation. Android Back returns to Home from a non-Home screen. The status strip displays a compact summary from the existing terminal output; tapping it opens the full console on Home. Every original View ID is preserved, and all original views stay mounted: no new broker request or trading side effect occurs during tab changes. No new runtime dependencies are required (Material Components already installed).

## Critical safety properties

- The research-only label must remain visible on **every tab**. It must not claim live broker connections, verified real-market AI or enabled trading.
- Broker profile edits are still credentials-free. The existing explicit Windows-local opt-in and device enrollment are required for saving profiles.
- FundedNext Free Trial EA restrictions remain in force. FTMO demo execution permissions still require confirmation.
- No edits to Gateway Python app, execution controller, broker order calls, release app identity, or model readiness state were made by this navigation change.

## Verification commands on user's Windows

~~~powershell
$hub = 'C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4'
Set-Location "$hub\android_project"
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }

Set-Location "$hub\backend"
.\.venv-gateway\Scripts\python.exe -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed: do not install' }

Set-Location "$hub\android_project"
.\gradlew.bat --no-daemon testDebugUnitTest assembleDebug
if ($LASTEXITCODE -ne 0) { throw 'Android tests/build failed: do not install' }

$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
# Substitute current serial if your phone re-paired.
$device = '10.10.20.127:40397'
& $adb -s $device install -r '.\app\build\outputs\apk\debug\app-debug.apk'
~~~

If the Gateway still runs on Windows \`127.0.0.1:5001\`, maintain:

~~~powershell
& $adb -s $device reverse tcp:5000 tcp:5001
& $adb -s $device reverse --list
~~~

The phone Gateway URL stays \`http://127.0.0.1:5000\` over **ADB reverse only**. Test no network/tunnel leakage.

## Acceptance checklist

1. Home loads with no crash; 5 bottom labels fit at phone width, system feedback visible, new research-only header visible.
2. Tap Accounts: FTMO and FundedNext profiles refresh; edit FTMO to \`US100\`, Save (with local opt-in & paired device), then re-read Windows \`GET /api/v5/mt5/accounts\` to verify persistence.
3. Tap AI Lab: NAS100 research summary refreshes; technical-details toggle behaves exactly as before; real-trading readiness remains false.
4. Tap Risk: calculator and safety controls still respond, and server still refuses trade execution.
5. Tap Settings: Gateway URL and pairing fields can be edited, device pairing/revocation still works; infrastructure log stress analyzer works.
6. Tap activity strip after action on Risk/Settings: Home opens and console is visible. Android Back from another tab returns Home.
7. Rotate/recreate Activity: selected page restores, no duplicated bot actions or lost persistent device credentials.
8. Original signed app (\`com.ittrader.smarthub\`) remains untouched; update only research debug app (\`com.ittrader.smarthub.research\`).

The five-page static source-layout checks were added at \`backend/tests/test_android_navigation_layout.py\` and navigation mapping unit tests at \`android_project/app/src/test/.../DashboardTabSpecTest.kt\`. New tests still need actual Windows execution.
