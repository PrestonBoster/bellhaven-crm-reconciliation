"""Deterministic identity matching; every mutation remains a review proposal."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from .source import digest

STREETS = {'street':'st','road':'rd','avenue':'ave','boulevard':'blvd',
           'drive':'dr','lane':'ln','court':'ct','north':'n','south':'s',
           'east':'e','west':'w','northwest':'nw','northeast':'ne',
           'southwest':'sw','southeast':'se','pike':'pk','parkway':'pkwy',
           'place':'pl','terrace':'ter','highway':'hwy'}
CARE = {'Short-Term Rehabilitation & Nursing':'Skilled Nursing',
        'Memory Support':'Memory Care','Assisted Living':'Assisted Living'}


def norm(value):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize(
        'NFKD', str(value or '')).lower()).split())


def street(value):
    return ' '.join(STREETS.get(word, word) for word in norm(value).split())


def phone(value):
    return re.sub(r'\D', '', value or '')[-10:]


def money(account, key):
    try:
        result = Decimal(str(account[key]))
        if not result.is_finite() or result < 0:
            raise ValueError('Invalid billing amount')
        return result
    except (KeyError, InvalidOperation, TypeError):
        raise ValueError('Missing or invalid billing fields; cannot determine CHOW safety.')


def protected(account):
    # Both fields must be present even when the first is zero.
    revenue, ar = money(account, 'lifetime_revenue'), money(account, 'outstanding_ar')
    return revenue > 0 and ar > 0


def canonical_fields(loc, parent_id):
    unknown = set(loc['care']) - set(CARE)
    if unknown:
        raise ValueError(f'Unmapped care offering: {sorted(unknown)}')
    return dict(name=loc['name'], parent_id=parent_id, billing_street=loc['street'],
                billing_city=loc['city'], billing_state=loc['state'], billing_zip=loc['zip'],
                care_type='; '.join(sorted({CARE[c] for c in loc['care']})), status='Active')


def candidate(loc, a):
    same_state = norm(loc['state']) == norm(a.get('billing_state'))
    same_city = norm(loc['city']) == norm(a.get('billing_city'))
    same_zip = loc['zip'][:5] == a.get('billing_zip', '')[:5]
    same_street = street(loc['street']) == street(a.get('billing_street'))
    same_name = norm(loc['name']) == norm(a.get('name'))
    same_phone = bool(phone(loc.get('phone'))) and phone(loc.get('phone')) == phone(a.get('phone'))
    reasons = []
    if not same_state:
        return 0, ['State differs; identity rejected']
    if same_street and (same_city or same_zip):
        reasons += ['Exact normalized street address', 'Same state and city or ZIP']
        if same_name:
            reasons += ['Exact normalized facility name']
        return (100 if same_name else 96), reasons
    if same_name and same_city and same_phone:
        return 93, ['Exact facility name, city and phone', 'Street differs; address requires separate review']
    similarity = SequenceMatcher(None, norm(loc['name']), norm(a.get('name'))).ratio()
    shared_words = set(norm(loc['name']).split()) & set(norm(a.get('name')).split()) - {'of','at','the','bellhaven'}
    if same_city and (similarity >= .55 or len(shared_words) >= 2):
        return 60, ['Similar name in the same city', 'Different address; insufficient identity evidence']
    return 0, []


def make_proposal(kind, title, account, fields, reasons, loc=None, **extra):
    evidence = {k:loc[k] for k in ('name','street','city','state','zip','care','phone','url','source_hash')} if loc else None
    stable = {'kind':kind,'account_id': account['account_id'] if account else '',
              'fields':fields,'source_hash':loc['source_hash'] if loc else None,
              'survivor_id':extra.get('survivor_id')}
    return dict(id=digest(stable)[:24], kind=kind, title=title, before=account,
                fields=fields, reasons=reasons, location=evidence, **extra)


def build(snapshot, accounts):
    if not snapshot.get('complete'):
        raise ValueError('A complete website snapshot is required.')
    parents = [a for a in accounts if norm(a['name']) == 'bellhaven senior living parent account']
    if len(parents) != 1:
        raise ValueError('Expected exactly one Bellhaven parent account.')
    parent_id = parents[0]['account_id']
    available = [a for a in accounts if a.get('billing_street') and
                 not a.get('duplicate_of_account') and not a.get('chow_current_account')]
    proposals, matches, used = [], [], set()
    for loc in snapshot['locations']:
        scored = [(a, *candidate(loc,a)) for a in available]
        strong = [(a,score,reasons) for a,score,reasons in scored if score >= 90]
        weak = [(a,score,reasons) for a,score,reasons in scored if 0 < score < 90 or
                (score == 0 and norm(a['name']) == norm(loc['name']))]
        target = canonical_fields(loc, parent_id)
        if not strong:
            # A same-city near-name candidate is visible, but never re-parented by fuzzy name.
            reasons = ['No strong identity match in the complete CRM snapshot.']
            if weak:
                reasons += ['Same or similar-name records have different addresses or states; verify before creating.']
            proposals.append(make_proposal('create', loc['name'], None,
                {**target, 'phone':loc['phone']}, reasons, loc,
                confidence='Review required' if weak else 'High',
                alternatives=[{'account':a,'score':s,'reasons':r} for a,s,r in weak]))
            matches.append({'name':loc['name'],'classification':'Missing account','account_id':None})
            continue
        # Prefer the record already at the verified parent, then billing history,
        # exact name, phone, and finally a stable ID. Never rely on API ordering.
        strong.sort(key=lambda t: (t[0]['parent_id'] == parent_id,
                    money(t[0], 'lifetime_revenue') > 0, norm(t[0]['name']) == norm(loc['name']),
                    phone(t[0].get('phone')) == phone(loc.get('phone')), t[0]['account_id']), reverse=True)
        winner, score, reasons = strong[0]
        if winner['account_id'] in used:
            raise ValueError('One CRM account matched multiple locations; review source identities.')
        used.update(a['account_id'] for a,_,_ in strong)
        # Address spelling differences are not corrections. PO boxes are billing
        # addresses and get their own optional proposal, never silently overwritten.
        fields = {k:v for k,v in target.items() if k not in
                  ('billing_street','billing_city','billing_state','billing_zip') and winner.get(k) != v}
        if winner.get('parent_id') != parent_id and protected(winner):
            proposals.append(make_proposal('chow', loc['name'], winner,
                {**target,'phone':loc['phone']}, reasons + [
                'Revenue history AND unpaid AR: preserve the old account.',
                'Create a successor under Bellhaven; change only chow_current_account on the old record.'],
                loc, confidence='High'))
        elif fields:
            proposals.append(make_proposal('update', loc['name'], winner, fields,
                reasons + (['Billing check permits direct re-parenting.'] if 'parent_id' in fields else []),
                loc, confidence='High'))
        if street(winner['billing_street']) != street(loc['street']) and not ('parent_id' in fields and protected(winner)):
            proposals.append(make_proposal('address_review', loc['name'] + ' · billing address', winner,
                {'billing_street':loc['street'],'billing_city':loc['city'],
                 'billing_state':loc['state'],'billing_zip':loc['zip']},
                reasons + ['Website gives a physical address; CRM may intentionally use a billing PO box.',
                           'Reject unless you can verify the billing address should change.'],
                loc, confidence='Manual review'))
        for loser,_,duplicate_reasons in strong[1:]:
            if protected(loser) or money(loser,'lifetime_revenue') > 0 or money(loser,'outstanding_ar') > 0:
                fields_dup = {'status':'Needs Review', 'note':f'Potential duplicate of {winner["account_id"]}; preserve billing history pending investigation.'}
                kind = 'duplicate_review'
            else:
                fields_dup = {'status':'Inactive','duplicate_of_account':winner['account_id']}
                kind = 'duplicate'
            proposals.append(make_proposal(kind, loser['name'], loser, fields_dup,
                duplicate_reasons + [f'Survivor: {winner["name"]} ({winner["account_id"]}); already under the verified parent or strongest billing-backed record.',
                'No merge or delete; preserve the losing account and its parent.'], loc,
                confidence='High' if kind == 'duplicate' else 'Manual review',
                survivor_id=winner['account_id'], survivor=winner, survivor_parent_id=parent_id))
        matches.append({'name':loc['name'],'account_id':winner['account_id'],
                        'classification':'Needs correction' if fields else 'Confident match', 'score':score})
    for a in available:
        if a['parent_id'] != parent_id or a['account_id'] in used:
            continue
        peers = [b for b in available if b['account_id'] != a['account_id'] and
                 street(b['billing_street']) == street(a['billing_street']) and
                 b['billing_state'] == a['billing_state'] and b['billing_zip'] == a['billing_zip']]
        note = ('Absent from complete Bellhaven website roster. Ownership is unverified; '
                'retain parent and billing history pending manual confirmation.')
        if peers:
            note += ' Same-address CRM evidence: ' + ', '.join(b['account_id'] for b in peers) + '; CRM alone does not prove current ownership.'
        # Existing note is preserved by the execution layer; don't repeatedly append.
        if a.get('status') == 'Needs Review' and note in a.get('note',''):
            continue
        proposals.append(make_proposal('absent', a['name'], a,
            {'status':'Needs Review','note':note}, [
            f'Not found among all {len(snapshot["locations"])} verified website communities.',
            'Absence is not proof of closure or a sale. Do not change parent without evidence.'],
            confidence='Manual review', alternatives=[{'account':p} for p in peers]))
    return {'parent_id':parent_id,'proposals':proposals,'matches':matches}
