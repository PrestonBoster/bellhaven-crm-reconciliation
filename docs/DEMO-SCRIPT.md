# Three-minute demo script

Use this as a voiceover for the silent screen recording, or as a guide for a live walkthrough. Read only the quoted narration during the three-minute video. Aim for roughly 125–140 words per minute and pause where the video waits for an action. The recording shows actual sandbox actions from October 14, 2026; a later walkthrough should use the saved decision history rather than undoing the changes.

## Understand the results before recording — not part of the voiceover

These results were verified on October 14, 2026, by reading the saved CRM records back, comparing them with the original snapshot, and running the scan again. Automated tests separately checked the application's behavior.

| Result | What it means |
|---|---|
| **35 website communities; 35 active current matches** | Every community found on Bellhaven's website now maps to an active current account under Bellhaven. This is website coverage, not the total number of CRM records. |
| **121 → 127 total CRM accounts** | Four missing facility accounts and two ownership-change successors were created: 121 + 4 + 2 = 127. The total also includes other organizations, old billing records and inactive duplicates. |
| **28 approved proposals** | 12 field corrections + 7 duplicate inactivations + 4 missing accounts + 2 ownership-change successors + 3 investigation flags. A proposal can change several fields or require several API calls. |
| **1 rejected proposal** | Ashtabula's website showed a physical address, which did not prove that its CRM billing PO box was wrong. The PO box was preserved and the rejection was remembered. |
| **0 pending proposals** | Every proposal received a decision. This does not mean every ownership question is resolved: Alliance, Coldwater and Sandusky still need investigation. |
| **All original financial balances preserved** | Every original account retained its lifetime revenue and outstanding accounts receivable (AR, or money still owed). The Marietta and Tiffin predecessors kept their original business fields except for the required link to the new current account. |
| **97 original accounts entirely unchanged** | Of the original 121 records, 24 received an approved change; the other 97 were untouched. The six new accounts are separate from this comparison. |
| **0 new proposals on the repeat scan** | Repeating the scan with the same saved decision history did not bring back resolved items, including the rejected address change. New source data can still produce future proposals. |
| **23 automated tests passed** | The tested matching, billing and repeat-run safeguards passed. This complements the live CRM checks; it is not a guarantee against every possible failure. |

The daily schedule is included as an example and is not running. The private local decision history is excluded from the public repository, so a fresh clone does not inherit the completed review ledger.

## 0:00–0:20 — Start at the review dashboard

**Screen:** Community coverage, CRM count, pending decisions and approved changes.

“This is my AI-assisted Bellhaven review app. Twelve proposals have corrected names, ownership, or care offerings, and seven duplicates are inactive and linked to surviving records. Changes require approval. This recording shows the final two decisions and verification of the results.”

## 0:20–0:40 — Open Marietta and show its evidence

**Screen:** Official address on the left; existing Cedar Trail parent and proposed Bellhaven account on the right.

“The scraper found thirty-five communities, including Findlay, which appears on the homepage but is missing from the directory. Marietta matches by normalized address, state and name. Its existing CRM parent is Cedar Trail, while the official website lists it as a Bellhaven community.”

## 0:40–1:10 — Scroll to billing and approve

**Screen:** $51,250 lifetime revenue, $3,800 unpaid AR; approve at approximately 1:05.

“Marietta has fifty-one thousand, two hundred fifty dollars in lifetime revenue and thirty-eight hundred dollars still owed. Because it has both revenue history and unpaid receivables, the billing rule requires preserving the old account. Approval creates a new account under Bellhaven and links the old record to it. That’s CHOW: change of ownership. I’ll approve it now.”

## 1:10–1:35 — Open the updated CRM record

**Screen:** The real CRM browser, showing the new Marietta account under Bellhaven.

“This is the actual CRM browser showing Marietta’s new account under Bellhaven. The app reads the saved record back to verify the change. Across the review, four missing facilities and two ownership-change successors were created. That’s why the total CRM count rises from one hundred twenty-one to one hundred twenty-seven.”

## 1:35–2:00 — Show the old Marietta account

**Screen:** Original Cedar Trail account, original balances, populated CHOW current account.

“The old Marietta account remains under Cedar Trail, with the same balances and a link to the successor. Tiffin received the same protection. Verification compared every original account with the starting snapshot: all original financial balances were preserved, and ninety-seven original accounts were entirely unchanged.”

## 2:00–2:35 — Reject the Ashtabula billing-address proposal

**Screen:** PO Box 517 versus the physical website address; enter the rejection reason and reject.

“Here’s the one rejected proposal. Ashtabula matches by name, city and phone, but the website gives a physical address while the CRM uses a billing PO box. Those addresses serve different purposes. The website doesn’t prove the billing address is wrong, so I’m rejecting the replacement and saving the reason. The existing billing address is preserved.”

**Rejection reason:** “The website verifies a physical location, not a billing mailing address. Preserve PO Box 517; identity is supported by exact name, city and phone.”

## 2:35–3:00 — Run the scan again

**Screen:** Fresh scan, zero pending items, zero new proposals, 28 approved and one rejected.

“After rescanning, all thirty-five communities match active Bellhaven accounts. The final tally is twenty-eight approved proposals, one rejected, and none pending. No new proposals were added, so saved decisions are remembered. Three absent facilities remain flagged for investigation; their ownership is unresolved. Twenty-three automated tests also passed.”

## If asked during the live walkthrough

- **Why not fuzzy-match names alone?** Amberly Manor exists in another state, and Union Square has a misleading near-name at a different address.
- **Why not remove Sandusky from Bellhaven?** Website absence and another CRM record are clues, not independent proof of a sale. Its billing history also requires special care.
- **Why SQLite?** It makes decisions and operation checkpoints durable with minimal local setup. A scheduled process must reuse the same database.
- **Why are there 127 accounts for 35 communities?** The CRM contains other organizations, historical billing accounts and inactive duplicates. Only 35 are the current website communities being matched.
- **How do 97 untouched accounts reconcile with 28 approvals?** 24 original records changed: 12 field corrections, 7 duplicate inactivations, 2 predecessor links and 3 investigation flags. Four missing-account approvals create only new records, while each CHOW approval creates a successor and links its predecessor. Thus 121 − 24 = 97 untouched original accounts, and 121 + 6 = 127 total accounts.
- **Does zero pending mean everything is known?** No. All proposals were decided, but the three absent facilities remain flagged for ownership investigation. Website absence alone does not establish a sale or closure.
- **Is the daily job running?** No. The schedule configuration is provided, as requested, but has not been activated.
- **Can you promise exactly-once remote writes?** No. The API lacks transactional writes and idempotency keys. The app uses creation markers, checkpoints, read-back verification and a stop-on-uncertainty rule.
- **Where would you make a small live change?** The care mapping and address aliases are explicit in `bellhaven/matching.py`; extend a relevant test before changing a matching rule.
- **What did AI do?** AI generated implementation, tests and documentation and assisted the evidence review. The recorded session is labeled as AI-assisted, not an unaided manual exercise.
