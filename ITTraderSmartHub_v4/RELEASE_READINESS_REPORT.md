# ITTrader SmartHub v4 — Final Release Engineering & Security Readiness Report

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v4  
**Package:** `com.ittrader.smarthub`  
**Branch:** `fix/v4-security-connectivity`  
**Release Commit Hash:** `3c9e12a`  
**Release Build Status:** ✅ BUILD SUCCESSFUL (Signed Release APK)  
**Release Signature Verification:** ✅ VERIFIED via `apksigner` (APK Signature Scheme v2)  

---

## 1. Release Engineering Corrections & Audit

| Issue Identified | Resolution | Status |
|---|---|---|
| **Release Lint Check Suppression** | Restored `checkReleaseBuilds true` and `abortOnError true` in `app/build.gradle`. Ran lint checks without suppressing findings. | ✅ RESOLVED |
| **Debug Key Signing in Release Build** | Removed `signingConfig signingConfigs.debug` from `buildTypes.release`. | ✅ RESOLVED |
| **Dedicated Keystore Configuration** | Configured `signingConfigs.release` reading from `keystore.properties` (or environment variables). Added `*.keystore`, `*.jks`, and `keystore.properties` to `.gitignore`. | ✅ RESOLVED |
| **Separate Development Artifacts** | `app-debug.apk` and `app-release.apk` are built and preserved in separate output directories. | ✅ RESOLVED |

---

## 2. Release APK Signature Verification Evidence

```cmd
$ apksigner.bat verify --verbose app-release.apk

Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
```

---

## 3. Security & Authentication Audit

1. **Master Secret Removal:** `SMARTHUB_API_TOKEN` is completely removed from mobile source code, layout UI, and Android enrollment requests.
2. **One-Time Pairing Code System:** Mobile enrolls via administrator-generated 10-minute pairing codes (`POST /api/v4/admin/pairing-code` -> `POST /api/v4/device/enroll`). Pairing codes are consumed once and invalidated.
3. **Token Hashing:** Access tokens are hashed with SHA-256 (`token_hash`) before storage in the SQLite database (`ContextStore`). Plaintext tokens are never stored on disk.
4. **RBAC Scope Isolation:** Ordinary mobile device tokens receive **HTTP 403 Forbidden** if attempting to access `/api/v4/auth/audit` or revoke other devices.
5. **Server Revocation on Logout:** Logout triggers `POST /api/v4/device/revoke` and clears local EncryptedSharedPreferences credentials.
6. **Strict TLS Enforcement:** Centralized `validateEndpointUrl()` enforces HTTPS across all requests (rejects plain HTTP except loopback `127.0.0.1`/`localhost`).

---

## 4. Test Evidence

```
================================== Pytest Suite ==================================
Command: python -m pytest -v tests
Result: 30/30 PASSED (includes security tests, Pipnex lot calculator, prop firm shield)

================================= Android Gradle =================================
Command: .\gradlew.bat test
Result: BUILD SUCCESSFUL (16 unit tests PASSED)

Command: .\gradlew.bat assembleRelease
Result: BUILD SUCCESSFUL
Output Artifact: app/build/outputs/apk/release/app-release.apk
```

---

## 5. Distinction: Build Success vs. Environment Testing

- **Release Build & Signing:** ✅ SUCCESS (`app-release.apk` generated and verified via `apksigner`).
- **Unit & Security Tests:** ✅ SUCCESS (30/30 Pytest, 16 Android unit tests).
- **Physical USB Device Test:** ⏳ PENDING (`adb devices` currently unattached).
- **Live MT5 Investor Session:** ⏳ PENDING (Requires running MetaTrader 5 terminal on Windows host with investor credentials set).
