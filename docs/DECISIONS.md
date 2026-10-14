# Decision rationale

## Discovery before matching

The directory advertises 34 entries over three pages, while the homepage advertises 35 communities and links to Findlay. Crawling just the directory would incorrectly treat Findlay as absent. The scanner follows links from both sources and verifies all 35 detail records before replacing the queue. Source URLs, SHA-256 content hashes and fetch timestamps are retained with each run.

All CRM pages are retrieved across all parents. Searching only for “Bellhaven” would miss acquired facilities still using names such as Riverbend Manor, Sunny Acres, Chesterton Senior Commons and Cedar Trail of Zanesville.

## Identity, normalization and care offerings

Identity relies on street + state + city or ZIP, with the name and phone as supporting signals. Normalization changes comparison values, not existing CRM formatting. Harmless address spelling differences such as “Lane”/“Ln” do not generate noisy updates.

- **Amberly Manor:** the website facility is in Hudson, Ohio. The existing same-name CRM record is in Colorado Springs, Colorado. The latter is left untouched; a separate Hudson account is proposed.
- **Union Square:** the website address is 118 Union Square Dr. A similarly named CRM facility is at 240 Market St. The similar name is displayed as conflicting context, not accepted as identity.
- **Kettering:** three legacy names describe the same address, including the abbreviation “Wilmington Pk.” One stable record survives; the other two are linked as duplicates. No record is deleted.
- **Owosso:** both records normalize to the same address; the survivor also has the website's phone number. This is stronger evidence than alphabetical record order.
- **Ashtabula:** exact name, city and phone support identity, even though the CRM has PO Box 517. A physical website address does not prove the billing PO box is wrong. The optional replacement proposal is rejected.

Care offerings are preserved in source evidence. “Short-Term Rehabilitation & Nursing” maps to CRM “Skilled Nursing”; “Memory Support” maps to “Memory Care.” Multiple offerings are stored as a sorted semicolon-separated value in the free-text `care_type` field. Unknown labels fail closed instead of being silently discarded. Findlay and Erie require both Assisted Living and Memory Care.

## Ownership and billing

The billing rule is evaluated from decimal monetary values and checked again immediately before a write. Missing, negative or invalid amounts block the operation rather than being assumed to be zero.

- **Tiffin:** original revenue $84,000; outstanding AR $12,400. Create a Bellhaven successor, leave the old Cedar Trail account intact, and set only its `chow_current_account` pointer.
- **Marietta:** original revenue $51,250; outstanding AR $3,800. Apply the same CHOW procedure.
- **Lima and Findlay:** revenue exists but outstanding AR is zero. Direct re-parenting is allowed.
- **Kettering and Zanesville:** no revenue history and no unpaid AR. Correct the existing account's parent and name directly.

For protected old accounts, no name, parent, status, note, phone, address or balance is changed. The API updates its own `updated_at` timestamp when the CHOW pointer is patched. That server-managed timestamp is the only expected incidental difference.

## Duplicates and departures

For a non-financial losing duplicate, set `status=Inactive` and `duplicate_of_account=<survivor id>`, preserving its original parent and other fields. The note records source evidence and a decision reference. Survivor preference is: already at Bellhaven, then revenue history, exact name, matching phone, and a stable account ID. Reviewers can inspect the entire proposed relationship. In Kettering's complete tie, the stable ID determines the survivor; no business significance is assigned to the ID.

Alliance, Coldwater and Sandusky are absent from the complete roster. They are flagged `Needs Review`, with ownership and billing retained. Sandusky has another same-address CRM record under Millstone, but that is internal CRM evidence, not an independently verified sale. Moving Sandusky based on that clue alone would overstate the evidence and risk its $5,200 outstanding AR. Further ownership confirmation is a follow-up task.

## Scope and tradeoffs

- The reviewer has final authority; rule labels do not bypass approval.
- The UI shows factual evidence, current values, proposed values, balances and conflicting candidates.
- Account name and ownership corrections are in scope. Existing phone numbers are matching evidence and are not broadly overwritten; new accounts use the website phone.
- A complete roster plus no strong CRM match supports a proposed new account, not an automatic write.
- The API has no merge/delete or transaction facility. The design keeps an audit trail and durable checkpoints rather than pretending two HTTP writes are atomic.
- On real multi-tenant infrastructure, add authenticated reviewer accounts, a shared durable database, a task queue, access controls and server-side conditional writes. The assessment app is intentionally local and single-workspace.
