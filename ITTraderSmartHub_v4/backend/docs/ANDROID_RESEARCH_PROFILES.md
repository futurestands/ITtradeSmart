# Local Android research account profiles

The Accounts page now contains a separate local research-profile card above
the existing Gateway broker-alias editor. Users can save/select up to 20
profiles with label, firm, exact programme, stage, currency, original advertised
size and purchase/applicable-terms reference. Profiles may be edited and switched
without rebuilding the APK. No broker account number/password fields are added.

Profiles are app-private metadata in a new preference file, independently of
the existing cloud/local enrollment stores. Backup and device-transfer rules
exclude the new file. Saving commits synchronously and reports persistence
failure; unreadable stored profiles disable editing without wiping old data.
Existing signing key, package IDs, enrollment, API routes and risk engine are
unchanged. No migration or synchronization with a backend database occurs.

The official-rules button opens a fixed HTTPS URL for the chosen firm using
the user's browser. It sends no profile fields, account IDs or search query.
Browser access is separate from authenticated SmartHub API access. Opening or
saving never marks rules reviewed/approved and never enables orders. Every
profile remains UNVERIFIED. The profile does not switch an MT5 session or change
the active risk-engine account. This is research setup metadata only.

The backend multi-firm research gate remains a local tool. Authenticated
programme-specific extraction, saved source reviews, scheduling/change alerts
and binding reviewed policies into the risk engine are still separate work.
Do not claim the APK automatically searches, approves or enforces firm rules.

Six added Android unit tests cover serialization, context separation, rejected
sizes/unknown firms, duplicate IDs, unapproved-field rejection and public links.
The complete Android unit suite passed 55 tests with zero failures/errors/skips.
Debug APK assembly and lint passed; lint reports zero errors and 205 warnings.
Six new autofill warnings were corrected by excluding these metadata fields
from autofill. The debug certificate matches the existing c833028 research APK:
SHA-256 d53968a7fe93c8f54189aad21725f8d67f55039e5154d6c01e993da99c748f29.
The final rebuilt APK must still pass certificate/hash checks before copying.
No phone installation is implied by a successful build. Functional UI interaction
on a real device/emulator still requires explicit verification.
