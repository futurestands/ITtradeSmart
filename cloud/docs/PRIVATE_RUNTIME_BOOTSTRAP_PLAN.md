# Private Preview runtime and phone enrollment activation — pending approval

The owner approved the schema migration separately and explicitly withheld
runtime credential activation. The new request authorizes publishing and an
online deployment. No bootstrap SQL is executed by a build, import or request.

Exact target: Neon project `winter-hat-40889380`, child
`br-autumn-scene-bcqp4rjv` (`phase3-auth-development`), endpoint
`ep-winter-cake-bcffwgio`, database `neondb`. Only Vercel project
`prj_WCV9dRjSufSvTeoYLJVhSf6yyKkC`, Preview and Development environments.

After separate approval, the private operator would:

1. Reverify provider project/branch/endpoint mapping and current role/catalog
   invariants, including no unexpected ownership/membership or privilege drift.
2. Activate only the existing `smarthub_cloud_preview_login` identity with a
   locally generated high-entropy credential and 30-day expiry. It remains
   NOINHERIT, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS.
   Existing membership is runtime only, SET TRUE / INHERIT FALSE / ADMIN FALSE.
   Do not activate or add credentials to either privilege role.
3. Conceptual private transaction, with values generated only in memory:

       BEGIN;
       -- Abort unless all target/role/membership checks match the reviewed state.
       ALTER ROLE smarthub_cloud_preview_login
         LOGIN PASSWORD '<privately generated; never logged>'
         VALID UNTIL '<UTC activation time plus 30 days>';
       COMMIT;

   This is a review template, not an executable SQL file or authorization.
4. Independently test direct and pooled login with verify-full TLS and required
   channel binding. Confirm runtime role switching and negative privilege tests;
   no owner/operator credentials reach Vercel, Android, responses or source.
5. Set only `SMARTHUB_CLOUD_DATABASE_URL` (private runtime pooled URL),
   `SMARTHUB_CLOUD_DATABASE_HOST` (the child pooled host), and
   `SMARTHUB_CLOUD_DATABASE_NAME=neondb` for Preview/Development. No Production
   variable is added. Existing owner aliases are never used as runtime identity.
6. Using offline operator access, issue one 10-minute, single-use enrollment
   code. Store only its hash in enrollment plus a bootstrap audit event. No
   administrator account or administrator session needs to be created for this
   initial phone pairing. Deliver the raw code through a private local display,
   not GitHub, logs, APK or a long-lived administrator token.
7. Redeploy only Preview, verify fail-closed/expiry/replay/revocation behaviour,
   then perform a real phone enrollment and fresh authenticated read.

Rollback: remove the three new Preview/Development runtime variables, disable
LOGIN on this private role, and invalidate any test enrollment/session created
by this bootstrap using scoped operator access. Preserve the installed schema,
existing records, main branch and Production. No destructive schema rollback.

Vercel edge protection must also allow the phone's selected Preview hostname
without embedding a bypass credential. Any required access-policy change must
identify that hostname and remain separate from application device auth.

This plan does not authorize trades, broker credentials, model readiness,
Production release, database-owner web access, or role-policy changes.
