# SmartHub launcher icon and device/research validation

Based on verified Phase 2 commit 2d6246c1d5126b86b498e4a1102b6d64b23e577c.

## Branding implemented

- Normal, round and Android 13+ monochrome adaptive launcher icon resources.
- Navy, blue and green vector market-chart mark.
- Existing release package ID, debug .research suffix, app label, signing, Android permissions and network policy are unchanged.
- These source changes do NOT update the installed phone APK until it is rebuilt.

From ITTraderSmartHub_v4/android_project on the Windows development PC:

    .\gradlew.bat :app:testDebugUnitTest :app:lintDebug :app:assembleDebug

Do not uninstall the original SmartHub app or clear its credentials. Keep using the separate research debug package for testing.

## Phone and gateway

1. Confirm package com.ittrader.smarthub.research is present in adb shell pm list packages.
2. Check adb devices -l and adb reverse --list; use adb reverse tcp:5000 tcp:5000 if needed.
3. Phone Chrome to http://127.0.0.1:5000/health confirms forwarding but not device authorization.
4. In the previously enrolled Android research app, refresh NAS100 Research, AI Status, Risk and MT5 Accounts.
5. Record which screens respond. Never share tokens or broker credentials in screenshots.

## Read-only historical export gate diagnosis

Previous export returned TRADING_MUST_BE_DISABLED. The exporter requires:
- connected terminal
- demo account
- account trading disabled
- account expert trading disabled
- terminal trading disabled

With the expected investor-only demo MT5 terminal already running, from backend:

    .\.venv-gateway\Scripts\python.exe tools\diagnose_mt5_export_gates.py

This script prints flags and failing gate names only; it does not log in, place trades, alter permissions, export candles or bypass safety checks.

## Remaining unverified work

- Actual Android Gradle build and installation of the icon-containing APK on the phone.
- Actual phone screen integration, user enrollment and Supabase cloud connectivity.
- Gateway runtime SQLite attachment (environment variable alone is insufficient).
- Live MT5 flags, data-timebase and broker history eligibility.
- Measured real-market performance and predictive model training.

Icon XML passed static parsing locally. Nine synthetic MT5 diagnostic tests passed locally. Neither is a substitute for device/broker testing.
