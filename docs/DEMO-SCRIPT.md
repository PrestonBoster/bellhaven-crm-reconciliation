# Three-minute demo script

Use this as a voiceover for the silent screen recording, or as a guide for a live walkthrough. Aim for roughly 125–140 words per minute and pause where the video waits for an action. The recording shows actual sandbox actions; a later walkthrough should use the saved decision history rather than undoing the changes.

## 0:00–0:20 — Start at the review dashboard

**Screen:** Community coverage, CRM count, pending decisions and approved changes.

“This is my Bellhaven ownership review workspace. I used AI to build the implementation, then checked the matching rules and safeguards against the assessment data. The goal is a corrected CRM with an explanation for every change. Scanning prepares proposals; only an explicit review action can write to the CRM.”

## 0:20–0:40 — Open Marietta and show its evidence

**Screen:** Official address on the left; existing Cedar Trail parent and proposed Bellhaven account on the right.

“The scraper found all thirty-five communities, including Findlay, which is linked from the homepage but missing from the directory. Here, Marietta matches by normalized address, state and name. Its current CRM parent is Cedar Trail, while the official website lists it as a Bellhaven community.”

## 0:40–1:10 — Scroll to billing and approve

**Screen:** $51,250 lifetime revenue, $3,800 unpaid AR; approve at approximately 1:05.

“This is the critical billing safeguard. Marietta has both revenue history and outstanding receivables, so changing the old account’s parent would violate the SOP. Approval creates a successor under Bellhaven and adds only the CHOW pointer to the old record. Its parent, balances, status and notes stay preserved. I’ll approve that now.”

## 1:10–1:35 — Open the updated CRM record

**Screen:** The real CRM browser, showing the new Marietta account under Bellhaven.

“The app reads the result back before marking the operation complete. This is the actual CRM browser, showing the new current account under Bellhaven. The account has been created through the API. The local audit history records the approval, source evidence and resulting account ID.”

## 1:35–2:00 — Show the old Marietta account

**Screen:** Original Cedar Trail account, original balances, populated CHOW current account.

“The original account is still under Cedar Trail, with the same revenue and outstanding AR. Its CHOW field now points to the successor. If a connection fails between those steps, the app remembers the created account and recovers the link without blindly creating another copy.”

## 2:00–2:35 — Reject the Ashtabula billing-address proposal

**Screen:** PO Box 517 versus the physical website address; enter the rejection reason and reject.

“Here’s a change I won’t approve. Ashtabula matches by name, city and phone, but the website provides a physical address while the CRM uses a billing PO box. That doesn’t establish that the billing address is wrong. I’m rejecting the replacement and saving the reason. The existing account and its ownership link stay intact.”

**Rejection reason:** “The website verifies a physical location, not a billing mailing address. Preserve PO Box 517; identity is supported by exact name, city and phone.”

## 2:35–3:00 — Run the scan again

**Screen:** Fresh scan, zero pending items, zero new proposals, 28 approved and one rejected.

“The second run adds no new proposals. Approved changes and rejected decisions are remembered in the persistent ledger. Three facilities missing from the website are flagged for investigation, rather than treated as confirmed sales. The repository also includes the daily scan schedule, recovery instructions, and tests for the billing and repeat-run safeguards.”

## If asked during the live walkthrough

- **Why not fuzzy-match names alone?** Amberly Manor exists in another state, and Union Square has a misleading near-name at a different address.
- **Why not remove Sandusky from Bellhaven?** Website absence and another CRM record are clues, not independent proof of a sale. Its billing history also requires special care.
- **Why SQLite?** It makes decisions and operation checkpoints durable with minimal local setup. A scheduled process must reuse the same database.
- **Can you promise exactly-once remote writes?** No. The API lacks transactional writes and idempotency keys. The app uses creation markers, checkpoints, read-back verification and a stop-on-uncertainty rule.
- **Where would you make a small live change?** The care mapping and address aliases are explicit in `bellhaven/matching.py`; extend a relevant test before changing a matching rule.
- **What did AI do?** AI generated implementation, tests and documentation and assisted the evidence review. The recorded session is labeled as AI-assisted, not an unaided manual exercise.
