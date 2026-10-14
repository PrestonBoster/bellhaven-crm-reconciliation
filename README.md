# Bellhaven CRM reconciliation

A local, evidence-led review app for keeping facility ownership accurate without losing billing history. It crawls the complete Bellhaven website, compares every CRM account, and prepares individual changes for review. **Scanning never writes to the CRM.** Approvals are recorded before writes, and every successful write is verified by reading the account back.

Built for the fictional Bellhaven assessment, with AI assistance and explicit review of the resulting evidence. No LLM service or paid API key is required at runtime.

## Start locally

Requires Python 3.10+ on macOS or Linux (Windows: WSL). Run from the repository directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Read your token without displaying it or putting it in shell history.
read -rs CRM_API_TOKEN
export CRM_API_TOKEN
export BELLHAVEN_REVIEWER='Your name'

python -m bellhaven scan
python -m bellhaven serve
```

Open **http://127.0.0.1:8765**. Review a proposal, inspect the source and before/after fields, then approve or reject it. Approval is the only path to a CRM mutation. The local server binds to loopback; it is not intended as a public deployment.

Configuration is documented in [`.env.example`](.env.example). Values must be exported; the app does not automatically load `.env`. The token, database, runtime snapshots and videos are excluded from Git. Do not paste the token or the credential-bearing CRM browser URL into public issues, screenshots or recordings.

## Submission materials

- [Design and decision rationale](docs/DECISIONS.md)
- [Three-minute narration and screen cues](docs/DEMO-SCRIPT.md)
- [Operations and recovery](docs/OPERATIONS.md)
- [Verified submission results](docs/RESULTS.md)
- [Daily cron configuration](config/daily.cron) — illustrative, not installed
- [Demo recording and downloadable materials](https://github.com/PrestonBoster/bellhaven-crm-reconciliation/releases/tag/v1.0.0)

The planned video is a browser recording of review actions against the assessment sandbox, with a matching script for the candidate's own narration. See the results document for the current execution status.

## What the system handles

| Situation | Proposal and behavior |
|---|---|
| Same facility, correct fields | Confident match; no write needed |
| Outdated name, care label or wrong parent | Minimal field correction with source evidence |
| Wrong parent; revenue > 0 **and** AR > 0 | Create successor; modify only the old account's `chow_current_account` |
| Wrong parent; either amount is zero | Re-parent the existing account after a fresh billing check |
| No strong identity match | Propose creation; show conflicting similar-name records |
| Confirmed duplicate without financial history | Mark losing copy `Inactive`; point `duplicate_of_account` at survivor |
| Potential duplicate with financial history | Flag for review; do not erase history |
| Under Bellhaven but absent from complete website | `Needs Review` and explanatory note; retain parent |
| Physical address conflicts with billing address | Separate optional proposal; do not silently replace a PO box |

## Coverage and matching

The source crawler follows all directory pages plus community links from the homepage, About page and discovered community pages. The initial website has **34 directory entries plus Findlay on the homepage = 35 communities**. The crawl checks both advertised counts and refuses to publish an incomplete scan. Account pagination is checked against the API's total (121 initially).

State and normalized address are primary identity evidence. Street and directional abbreviations are normalized, including `NW`/`Northwest` and `Pk`/`Pike`. Exact name + city + phone can identify a record whose billing address differs. Fuzzy names are context for a reviewer, never sufficient for an automatic re-parent. Confidence scores are deterministic rule labels, not statistical probabilities.

## Daily runs and repeat safety

Use the example cron entry with a persistent absolute `BELLHAVEN_DATA_DIR`. The schedule only scans. The review app and scheduled process must share the same SQLite database.

Stable proposal fingerprints remember approved and rejected decisions across restarts. Unchanged rejected proposals do not re-enter the queue. Source changes can create a new proposal for fresh review. A process lock serializes scans and approvals; source snapshots, decisions and write checkpoints are saved locally. Creation markers and recorded account IDs support recovery from interrupted multi-step CHOW operations. There is no claim of a remote transaction: the API has neither transactions nor idempotency keys. See [recovery details](docs/OPERATIONS.md).

## Validate

```sh
python -m pytest -q
python -m bellhaven scan
python -m bellhaven summary
```

The tests cover CHOW field preservation, both branches of the billing rule, stale approvals, duplicate resolution, rejected-decision persistence, partial failures, unknown POST outcomes, incomplete crawls, false name matches, and CSRF protection. After decisions are complete, another scan should add **zero** proposals for unchanged evidence.

## Project map

```text
bellhaven/source.py       Website extraction and CRM HTTP client
bellhaven/matching.py     Explainable identity rules and proposals
bellhaven/store.py        SQLite snapshots, decisions and audit events
bellhaven/service.py      Approval execution, safeguards and recovery
bellhaven/web.py          Local review routes and CSRF protection
bellhaven/templates/     Review queue and evidence screens
tests/                   Deterministic tests; no live API writes
config/daily.cron         Daily scan schedule example
```

## Boundaries

The website establishes the operator's current public roster, not legal ownership or the correct billing mailing address. Missing facilities and financially sensitive ambiguous duplicates need additional investigation. Contact synchronization is outside this submission's account-ownership scope. The app preserves existing financial values, does not merge or delete accounts, and does not infer a new parent from website absence alone.
