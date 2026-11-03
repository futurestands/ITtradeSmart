# ITTrader SmartHub — multi-account MT5 roster (Phase A)

This milestone is **a credential-free account roster**, not an active broker connection or trade copier. User requested more than two accounts after opening an FTMO Free Trial. The Gateway can list up to **20 account aliases** for phone monitoring, including FTMO Trial, FundedNext Trial and additional brokers. The endpoint does not access MT5, fetch real quotes or place orders.

## Where data lives and what is exposed

- Windows-only file: \`backend/mt5_accounts.local.json\`, ignored by Git.
- Optional env override: \`SMARTHUB_MT5_ACCOUNTS_FILE\` points to a private Windows JSON file.
- Android calls authenticated \`GET /api/v5/mt5/accounts\` using its existing paired-device token and existing Gateway URL.
- Statuses always \`NOT_CONNECTED\`; \`read_only: true\`; \`execution_authorized: false\`.
- At most 20 rows; all fields allowlisted. Unknown fields, account login IDs, passwords, server addresses, terminal paths, tokens, duplicate names/ids, bad JSON, symlinks, nonfinite numbers and overlarge files are rejected as \`INVALID_CONFIG\` without echoing data to the phone.
- Endpoint is always device-authenticated, \`Cache-Control: no-store\`. Existing v5 bot admin-only routes and hard execution locks are not modified.
- FundedNext Free Trial lists \`ea_execution_permitted: false\`; FTMO/free trial bot approval remains \`null\` until checked, not inferred as permission. No live or demo trading is enabled.

## Windows setup — register two now, add more later

From PowerShell:

~~~powershell
$backend = 'C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4\backend'
Set-Location $backend
Copy-Item '.\mt5_accounts.example.json' '.\mt5_accounts.local.json' -ErrorAction Stop
notepad '.\mt5_accounts.local.json'
~~~

The example lists **FTMO Trial** and **FundedNext Trial** with placeholder \`VERIFY_IN_MT5\` symbols. After viewing **Market Watch -> Specification** on each broker's own terminal, edit the \`symbol\` fields to their actual broker symbol names. To add a third or fourth account, add another JSON object with a unique \`id\` (lowercase letters, digits, hyphen/underscore), short \`label\`, \`provider\` (\`FTMO\`, \`FUNDEDNEXT\`, \`OTHER\`), \`account_kind\` (\`FREE_TRIAL\`, \`DEMO\`, \`EVALUATION\`, \`FUNDED\`, \`LIVE\`), \`symbol\`. Do not enter account numbers, credentials or login server addresses.

**Do not restart your currently paired Gateway** merely to load the file. Each GET re-reads the ignored file. Just refresh **MT5 Multi-account Monitor** on Android. If the Gateway was started before pulling the new code, however, the running process still uses the old Python module and must be restarted **once after the new code is installed**. Unless persisted state is configured, a Gateway restart can invalidate current pairing tokens. Re-pair using a newly generated one-time code from the Gateway administrator if necessary; never reveal master token.

To verify locally with a Windows-only Gateway administrator token already available to the calling PowerShell session:

~~~powershell
$roster = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/v5/mt5/accounts' -Headers @{Authorization = "Bearer $env:SMARTHUB_API_TOKEN"}
$roster | Select-Object status, account_count, max_accounts, execution_authorized
$roster.accounts | Select-Object label, provider, account_kind, symbol, connection_status
~~~

\`REGISTRY_AVAILABLE\` means the aliases were loaded; **NOT_CONNECTED** still means no MT5 broker session was established.

## Next engineering milestone — simultaneous actual MT5 read-only monitoring

One MT5 terminal can switch between broker accounts, but it is **not safe to switch a single Python MT5 session among accounts during concurrent analysis**. The next milestone should run **one isolated MT5 terminal and Python worker per account** with isolated data dirs, server-only investor credentials, pinned terminal paths and startup checks. Each worker should:

1. Verify terminal/process identity, expected login and broker server and investor-only \`trade_allowed == false\`, \`trade_expert == false\` after every session initialization.
2. Read only trusted bid/ask, account health, instrument specifications and closed candles; never submit or modify orders.
3. Report sanitized per-account freshness/health with hard timeouts, explicit disconnected/STALE indicators, no raw credentials, paths, login IDs or balances via the API.
4. Keep FundedNext Free Trial on an explicit \`NO_EA\` policy and never circumvent firm restrictions.
5. Validate broker timestamp/timebase/DST/session anchors and true costs before feeding NAS100 Lab. The existing real USTECH100M dataset remains quarantined.
6. Ensure any broker demo execution connector is a **separate future opt-in feature**, subject to firm rules, audited risk controls and explicit authorization. No funded/live execution here.

Official references:
- FundedNext Free Trial does not permit EAs: https://help.fundednext.com/en/articles/8902893-fundednext-free-trial-rules
- FTMO algorithmic strategies are generally permitted when consistent with its rules, but confirm the exact Free Trial and any restricted copying strategy: https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/
- MetaQuotes allows specifying a terminal executable in MT5 Python \`initialize\`: https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py

## Verification not yet performed

All new Python and Kotlin tests, actual Windows Gateway restart, Gradle build, Android install and on-phone roster display are **pending user verification**. The earlier lab regression (426) and Gateway regression (237) apply to the preceding feature baseline and must not be misrepresented as results for this new code.
