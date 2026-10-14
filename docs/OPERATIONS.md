# Operations and recovery

## Persist the decision ledger

`BELLHAVEN_DATA_DIR` contains `review.sqlite3` and `review.lock`. The database retains complete source/CRM snapshots, proposal payloads, reviewer identities, rejection reasons, approval events, write checkpoints and read-back results. It is intentionally ignored by Git.

Use the same absolute data directory for the app and daily scan. Never run a scheduled scan in an ephemeral GitHub Actions checkout without restoring durable state; that would lose rejections and write checkpoints. The supplied cron example avoids this problem by running on a persistent host. It is configuration only and has not been installed.

Back up the database while the app and scan processes are stopped, or use SQLite's backup API. Do not copy only the database file while a write-ahead log is active. Losing the ledger can re-propose previously rejected items, even when accepted CRM field changes remain in place.

## Normal operation

1. Export the token and reviewer name; use an owner-readable credential file if scheduling.
2. Run `python -m bellhaven scan`. This reads remote data and writes only the local queue.
3. Run `python -m bellhaven serve` and inspect each proposal.
4. Approve or reject individually. There is no bulk auto-approval endpoint.
5. Use “Open updated CRM account” to inspect the live external record.
6. Run another scan and check `python -m bellhaven summary` for zero newly added proposals.

The app blocks cross-origin form submissions with a session CSRF token, validates the Host header, and listens only on loopback. This is not a substitute for authentication if adapting it for a hosted service.

## Interrupted writes

Approval is saved before a write starts. The local lock serializes all scans and decisions across processes using the same data directory.

**PATCH interrupted:** a durable `patch_intent` checkpoint remains. A retry reads the account. If the approved fields already match and untouched fields are preserved, it records success. Otherwise the original baseline must still match before retrying. Changed unrelated fields stop execution rather than being overwritten.

**POST succeeded but response was lost:** the new account contains `[bellhaven-review:<proposal id>]` in its note. A retry searches the full CRM for exactly one matching marker, verifies its fields, and reuses its ID. It does not create another account.

**POST outcome unknown, marker absent:** the operation stops. There is no safe way to guarantee exactly-once creation without server idempotency keys. Investigate the CRM/server outcome before changing the checkpoint. Do not delete the ledger or clear `create_intent` merely to make the retry button work. If the server can confirm that no account was created, an operator can take a database backup, document that confirmation in the audit log, and deliberately reset the checkpoint for a fresh approval.

**CHOW successor created but linking failed:** the successor ID is already checkpointed. Retry verifies that successor, rechecks the unchanged old account, and attempts only the old account's CHOW link. If the old account drifted, stop for investigation. Do not delete or modify the old billing record to resolve the error.

**Stale proposal before any write:** a fresh scan can replace failed preflight proposals with current evidence and requires a new approval. Changed billing conditions can produce a CHOW proposal instead of a direct re-parent. Failed or interrupted operations with remote write intent retain their checkpoints and require explicit recovery.

## Known API limits

The remote API does not expose ETags/conditional PATCH, cross-record transactions, merge/delete, or idempotency keys. There is a small unavoidable race between the final GET and PATCH if an external actor changes a record simultaneously. A single local reviewer, a local process lock, preflight reads and post-write verification mitigate this; they do not create remote atomicity. The assessment sandbox is isolated, but a production system should require stronger server support.

## Local live walkthrough

Run the app with the original private `data/` directory to show the completed decision history. A fresh clone with an empty ledger reads the corrected CRM, but cannot recover a rejected address decision from Git because private review state is deliberately not published. Use the saved recording to show the original pending-to-approved and pending-to-rejected transitions. Do not undo real corrections just to recreate a demo.
