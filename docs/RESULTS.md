# Verified submission results

Verified on October 14, 2026, at 2026-10-14T18:42:17+00:00. The review actions were applied through the local review app to the isolated assessment CRM, after the account owner explicitly authorized them. The session was AI-assisted.

| Check | Verified result |
|---|---:|
| Website communities | 35 |
| Website pages fetched | 41 |
| Initial CRM accounts | 121 |
| Final CRM accounts | 127 |
| Current website facilities matched to active Bellhaven accounts | 35 |
| Approved proposals, with CRM read-back verification | 28 |
| Rejected proposals | 1 |
| Pending proposals | 0 |
| New proposals on repeated scan | 0 |
| Tests passed | 23 |

## Applied corrections

- **12 field updates:** names, ownership links and care offerings, including Findlay and Erie’s multiple care offerings.
- **7 losing duplicates:** marked Inactive and linked to surviving records; no merge or delete.
- **4 missing accounts:** Amberly Manor in Hudson, Bellhaven at Union Square, Batavia and Carlisle.
- **2 CHOW successors:** Tiffin and Marietta. Original billing records preserved; only their CHOW link and server-managed timestamp changed.
- **3 absent facilities:** Alliance, Coldwater and Sandusky marked Needs Review with explanatory notes, while retaining ownership and financial history.
- **1 rejection:** Ashtabula’s billing PO box was preserved because the website’s physical address did not establish a billing-address correction.

## Protected billing accounts

| Community | Original account | New current account |
|---|---|---|
| Bellhaven of Marietta | `001A34WFSUYHCRBLFT` | `001E1B67B248CE6822` |
| Bellhaven of Tiffin | `001U6RW32TY0WSXZZB` | `001D1F6BF6FC1161B6` |

The final verification compared every original account with the saved baseline. All original lifetime revenue and outstanding AR values were preserved. The 97 original accounts outside the approved changes were entirely unchanged. Both CHOW predecessors retained every original business field except the required `chow_current_account` link.

## Repeat-run evidence

After the final approval and rejection, the pipeline fetched the website and CRM again. It added zero proposals, left zero pending, and retained the rejected PO-box decision. All 35 source communities now classify as confident matches. The sole generated optional address suggestion is suppressed by its saved rejection.

Machine-readable verification: [`verification.json`](verification.json). Full source snapshots, CRM baselines, decision events and operation checkpoints are retained in the private local SQLite ledger, excluded from this public repository.

## Demo and reproducibility

The three-minute recording shows Marietta’s live approval, the new account in the CRM browser, preservation of the old billing account, the Ashtabula rejection, and a fresh scan with no new proposals. It is silent, with a matching narration script for the candidate to follow. Download it from the [public demo release](https://github.com/PrestonBoster/bellhaven-crm-reconciliation/releases/tag/v1.0.0).

The completed ledger remains in the original local project’s ignored `data/` directory. A fresh clone intentionally does not contain private decision history. See the operations guide before recreating a review environment.

## Time and remaining work

Approximately 30 minutes elapsed in the AI-assisted build, review, verification and recording session, including time awaiting approval. Human narration and interview-preparation time are not measured here; the candidate should report their own actual time honestly.

Ownership of the three absent facilities remains an investigation item. There is insufficient external evidence to assert a closure or a new owner. The daily cron example is provided but has not been activated. Add the candidate’s own narration before using the recording as the assessment’s spoken demo.
