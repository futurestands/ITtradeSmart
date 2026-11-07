# Connect the research APK on your Android phone

This Preview provides cloud authentication and research status. It does not
execute trades or provide a trained market prediction. No broker password,
database URL, administrator token or Vercel bypass secret belongs in Android.

## Install

Open the [research APK release](https://github.com/futurestands/ITtradeSmart/releases/tag/smarthub-cloud-preview-20261107-a89bc31)
on your phone, expand Assets and download
`ITTraderSmartHub-Cloud-Preview-a89bc31.apk`.

Install **ITTrader NAS100 Research**. Android may ask you to allow installation from
the browser you used; make that choice yourself for this trusted download.
The research package is `com.ittrader.smarthub.research`; it is separate from
the primary `com.ittrader.smarthub` app. Do not uninstall the primary app or
clear its data. If an update reports a signing conflict, stop and report it.

APK SHA-256:
`2ad6c2432887026dd467e8e702f7fcb3d9c3f6ce973812d12be3564b3142f7a3`

The existing debug signing key was reused. Java 21 build, lint and 40 Android
unit tests passed. This is a research/debug prerelease, not a Play Store release.

## Select the cloud connection

1. Open the app and scroll to its connection/device-pairing section.
2. Enable **Cloud HTTPS mode (separate device enrollment)**.
3. In **HTTPS Gateway URL**, enter this root URL exactly, with no extra path:

       https://ittrader-smarthub-phase3-phone-preview-futurestands.vercel.app

4. Enter the privately delivered, single-use `shc_enroll_…` code into
   **One-Time Pairing Code** and tap **Pair Device**. Codes expire in ten minutes.
5. After pairing succeeds, refresh AI/research status. The expected result is
   a fresh authenticated cloud response with **MODEL_NOT_READY / NO_TRADE**.

Cloud mode works over mobile data or Wi-Fi once the hostname is reachable and
pairing is complete. Your phone must not use `127.0.0.1` for this cloud flow.
The cloud URL is independent of the Windows gateway's local port 5000.

## Current activation gate

The schema and restricted private runtime login are active only on the approved
Neon child and Vercel Preview/Development environments. Production is unchanged.
The owner-approved exception is active only on the named Preview hostname.
Public HTTPS health returns 200; protected AI status without a device token
returns 401 CLOUD_DEVICE_AUTH_REQUIRED. No Vercel bypass secret is used.
One ten-minute enrollment code was issued and displayed privately on the local
computer. Phone installation and successful enrollment remain unverified.

## Troubleshooting

- **Vercel login/403:** hostname exception not active; do not paste a Vercel token.
- **Code expired/used:** request a fresh pairing code; do not reuse an old one.
- **401 after a previously working session:** try refresh; re-pair if revoked.
- **429:** stop retrying and wait for the rate window to expire.
- **503:** authentication storage/runtime unavailable; retain NO_TRADE.
- **Signing conflict:** stop; do not uninstall or delete app data.
- **MODEL_NOT_READY:** expected research state, not a connectivity failure.

ADB is optional for this download-and-pair flow. The latest ADB inventory showed
zero devices. If USB installation is preferred later, connect the phone, allow
its debugging prompt yourself, and verify a single authorized device before
using an update install that preserves data. No phone installation has yet been
observed or claimed.
