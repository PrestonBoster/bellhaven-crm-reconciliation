"""Approval is the only entry point for writes; checkpoint every non-atomic step."""
import fcntl
from contextlib import contextmanager
from .matching import build, protected, candidate
from .source import now, scrape


@contextmanager
def exclusive(store):
    with (store.directory / 'review.lock').open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another scan or decision is in progress. Try again shortly.')
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def scan(store, crm, snapshot=None):
    with exclusive(store):
        snapshot = snapshot or scrape(crm.base)
        accounts = crm.accounts()
        return store.save_run(snapshot, accounts, build(snapshot, accounts))


def unchanged(current, before, allowed=()):
    # updated_at and parent_name are server-generated metadata.
    ignored = {'updated_at','parent_name'} | set(allowed)
    changed = [k for k,v in before.items() if k not in ignored and current.get(k) != v]
    if changed:
        raise ValueError('CRM changed after review was prepared: ' + ', '.join(changed) + '. Rescan before approving.')


def verify(actual, expected):
    if not all(actual.get(k) == v for k,v in expected.items()):
        raise ValueError('CRM read-back does not match the approved change. Inspect the audit log.')


def note_fields(proposal):
    fields = dict(proposal['fields'])
    before = proposal['before'] or {}
    addition = fields.pop('note', '')
    evidence = proposal.get('location')
    if evidence:
        addition = (addition + '\n' if addition else '') + 'Verified website: ' + evidence['url']
    marker = '[bellhaven-review:' + proposal['id'] + ']'
    fields['note'] = '\n'.join(x for x in [before.get('note',''), addition, marker] if x)
    return fields


def ensure_created(store, crm, row, fields):
    p = row['payload']
    marker = '[bellhaven-review:' + p['id'] + ']'
    if row.get('created_id'):
        created = crm.get(row['created_id'])
        verify(created, fields)
        return created
    matches = [a for a in crm.accounts() if marker in a.get('note','')]
    if len(matches) > 1:
        raise ValueError('Multiple accounts contain the write marker; manual recovery required.')
    if matches:
        created = matches[0]
        verify(created, fields)
    else:
        if row.get('phase') == 'create_intent':
            raise ValueError('Previous POST outcome is uncertain and no matching marker was found. '
                             'Do not retry creation until the server outcome is confirmed.')
        store.update(p['id'], phase='create_intent')
        created = crm.create(fields)
        created = crm.get(created['account_id'])
        verify(created, fields)
    store.update(p['id'], phase='created', created_id=created['account_id'])
    store.event(p['id'],'account_created_verified',{'account_id':created['account_id']})
    return created


def approve(store, crm, proposal_id, actor):
    if not actor.strip():
        raise ValueError('A reviewer name is required.')
    with exclusive(store):
        row = store.get(proposal_id)
        if not row:
            raise ValueError('Unknown proposal.')
        if row['state'] == 'approved':
            return row['result']
        if row['state'] not in ('pending','failed','applying'):
            raise ValueError('This proposal cannot be approved in its current state.')
        p, before = row['payload'], row['payload']['before']
        store.update(proposal_id, state='applying', actor=actor, decided_at=now(), error=None)
        store.event(proposal_id,'approval_recorded',{'actor':actor,'kind':p['kind']})
        try:
            fields = note_fields(p)
            current = crm.get(before['account_id']) if before else None
            if p['kind'] == 'chow':
                # Successful link from a prior interrupted attempt is safe to resume.
                if row.get('created_id') and current.get('chow_current_account') == row['created_id']:
                    unchanged(current,before,allowed={'chow_current_account'})
                    created = crm.get(row['created_id'])
                    verify(created,fields)
                else:
                    unchanged(current,before)
                    if not protected(current):
                        raise ValueError('Billing conditions changed; rescan to choose the correct ownership workflow.')
                    created = ensure_created(store,crm,row,fields)
                    # Recheck old record after POST, before making the sole permitted patch.
                    unchanged(crm.get(before['account_id']),before)
                    crm.patch(before['account_id'], {'chow_current_account':created['account_id']})
                    old = crm.get(before['account_id'])
                    unchanged(old,before,allowed={'chow_current_account'})
                    verify(old,{'chow_current_account':created['account_id']})
                result = {'account_id':created['account_id'],'old_account_id':before['account_id'],
                          'action':'Created successor; preserved old account and linked CHOW'}
            elif p['kind'] == 'create':
                if not row.get('phase'):
                    for a in crm.accounts():
                        if not a.get('duplicate_of_account') and not a.get('chow_current_account') and candidate(p['location'],a)[0] >= 90:
                            raise ValueError('A matching account now exists. Rescan instead of creating a duplicate.')
                created = ensure_created(store,crm,row,fields)
                result = {'account_id':created['account_id'],'action':'Created and verified account'}
            else:
                if row.get('phase') == 'patch_intent' and all(current.get(k)==v for k,v in fields.items()):
                    unchanged(current,before,allowed=set(fields))
                else:
                    unchanged(current,before)
                    if 'parent_id' in fields and fields['parent_id'] != current.get('parent_id') and protected(current):
                        raise ValueError('Billing protection now applies. Rescan for a CHOW proposal.')
                    if p.get('survivor'):
                        survivor = crm.get(p['survivor_id'])
                        if survivor.get('duplicate_of_account') or survivor.get('chow_current_account') or survivor.get('status') != 'Active':
                            raise ValueError('Duplicate survivor is no longer an active current account.')
                        if candidate(p['location'],survivor)[0] < 90:
                            raise ValueError('Duplicate survivor identity changed. Rescan.')
                        if survivor.get('parent_id') != p['survivor_parent_id']:
                            raise ValueError('Approve the survivor ownership correction first, then retry this duplicate decision.')
                    store.update(proposal_id,phase='patch_intent')
                    crm.patch(before['account_id'],fields)
                updated = crm.get(before['account_id'])
                verify(updated,fields)
                unchanged(updated,before,allowed=set(fields))
                result = {'account_id':before['account_id'],'action':'Updated and verified account'}
            store.update(proposal_id,state='approved',result=result,error=None,phase='complete')
            store.event(proposal_id,'write_verified',result)
            return result
        except Exception as exc:
            # Do not expose requests exceptions that may carry sensitive URLs.
            error = str(exc) if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__ + ': operation interrupted; safe recovery required.'
            store.update(proposal_id,state='failed',error=error)
            store.event(proposal_id,'write_failed',{'error':error})
            raise ValueError(error) from None


def reject(store, proposal_id, actor, reason):
    if not actor.strip() or not reason.strip():
        raise ValueError('Reviewer name and rejection reason are required.')
    with exclusive(store):
        row = store.get(proposal_id)
        if not row or row['state'] != 'pending':
            raise ValueError('Only pending proposals can be rejected.')
        store.update(proposal_id,state='rejected',actor=actor,reason=reason,decided_at=now())
        store.event(proposal_id,'rejected',{'actor':actor,'reason':reason})
