# Approved isolated runtime activation

7 November 2026: the owner separately approved the private Preview runtime
activation and one-time phone pairing. The earlier pending bootstrap proposal
is retained as the review record; this document records the resulting state.

Target: project winter-hat-40889380, child br-autumn-scene-bcqp4rjv,
endpoint ep-winter-cake-bcffwgio, database neondb. Only the existing
`smarthub_cloud_preview_login` was enabled for LOGIN, with a generated,
SCRAM-protected credential expiring 7 December 2026. Credential material stays
in Windows Credential Manager and encrypted Vercel Preview/Development settings.
Neither privilege role was made a login. No administrator was created.

Direct and pooled verify-full TLS succeeded. The actual private connection
passed runtime identity/role mapping and seven negative privilege checks:
administrator creation, administrator promotion, operator role access, role
policy changes, and audit SELECT/UPDATE/DELETE were denied.

The three runtime variable names are SMARTHUB_CLOUD_DATABASE_URL,
SMARTHUB_CLOUD_DATABASE_HOST and SMARTHUB_CLOUD_DATABASE_NAME. Their values are
not included here. The CLI response timed out after applying them; subsequent
metadata inspection confirmed all three exist encrypted and target only
Preview/Development. No duplicate activation or credential rotation was done.

Fresh main-branch catalog comparison matched the prior baseline. Production
deployment dpl_4aVmWQqV445GiPNZAMRGgyzuoy5S and zero Production database variables
were confirmed unchanged. The schema migration was not rerun.

The runtime was deployed to an isolated Preview. Vercel-hostname protection
still needs its own scoped exception before native Android can reach the API.
Phone pairing has not yet been observed. An optional invalid-code enrollment
POST was blocked by automatic approval review because it could write audit/rate
state; it was not executed or retried by another route.

RESEARCH_ONLY, MODEL_NOT_READY and NO_TRADE remain. Cloud health is not proof of
MT5 data, trained model availability or successful phone enrollment.
