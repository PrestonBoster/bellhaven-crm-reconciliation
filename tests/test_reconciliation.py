import copy
import pytest
from bellhaven.matching import build, candidate, canonical_fields, protected, street
from bellhaven.service import approve, reject
from bellhaven.source import parse_location, scrape
from bellhaven.store import Store
from bellhaven.web import create_app


PARENT = dict(account_id='parent',name='Bellhaven Senior Living (Parent Account)',
              parent_id='',parent_name='',billing_street='',lifetime_revenue=0,outstanding_ar=0)
LOC = dict(name='Bellhaven of Sample', street='12 Northwest Maple Street', city='Sample',
           state='OH',zip='44000',care=['Assisted Living'],phone='555-222-3333',
           url='https://example.test/communities/sample',source_hash='test-source')


def account(**overrides):
    return dict(dict(account_id='old',name=LOC['name'],parent_id='other',parent_name='Other Parent',
                billing_street='12 NW Maple St',billing_city='Sample',billing_state='OH',
                billing_zip='44000',care_type='Assisted Living',phone=LOC['phone'],status='Active',
                lifetime_revenue=1000,outstanding_ar=100,note='Original billing note.',
                duplicate_of_account='',chow_current_account='',updated_at='before'),**overrides)


def snapshot(locs=None):
    return dict(complete=True,at='2026-01-01',locations=locs if locs is not None else [LOC],
                directory_count=1,pages=[{'url':'https://example.test'}])


class FakeCRM:
    def __init__(self, rows):
        self.rows={a['account_id']:copy.deepcopy(a) for a in rows}
        self.writes=[]
        self.fail_after_create=False
        self.fail_before_create=False
        self.fail_link=False
    def accounts(self):
        return copy.deepcopy(list(self.rows.values()))
    def get(self, aid):
        return copy.deepcopy(self.rows[aid])
    def patch(self, aid, fields):
        if self.fail_link:
            self.fail_link=False
            raise ConnectionError('simulated link failure')
        self.writes.append(('patch',aid,copy.deepcopy(fields)))
        self.rows[aid].update(fields)
        self.rows[aid]['updated_at']='after'
        return self.get(aid)
    def create(self, fields):
        if self.fail_before_create:
            raise ConnectionError('unknown POST outcome')
        aid='new'+str(len(self.rows))
        self.writes.append(('create',aid,copy.deepcopy(fields)))
        self.rows[aid]=account(**{**fields,'account_id':aid,'lifetime_revenue':0,'outstanding_ar':0})
        if self.fail_after_create:
            self.fail_after_create=False
            raise ConnectionError('response lost after creation')
        return self.get(aid)


def prepare(tmp_path, rows, locs=None):
    crm=FakeCRM([PARENT,*rows]); store=Store(tmp_path)
    result=build(snapshot(locs),crm.accounts())
    store.save_run(snapshot(locs),crm.accounts(),result)
    return store,crm,result


def test_normalized_address_not_global_name_match():
    assert street('12 Northwest Maple Street')==street('12 NW Maple St')
    assert street('3313 Wilmington Pike')==street('3313 Wilmington Pk')
    assert candidate(LOC,account(billing_state='CO'))[0]==0
    assert candidate(LOC,account(billing_street='999 Other Rd',phone='555-000-0000'))[0]<90


@pytest.mark.parametrize('revenue,ar,expected',[(100,1,True),(100,0,False),(0,100,False),(0,0,False)])
def test_sop_both_balances_required(revenue,ar,expected):
    assert protected(account(lifetime_revenue=revenue,outstanding_ar=ar))==expected


def test_invalid_billing_fails_closed():
    with pytest.raises(ValueError): protected(account(outstanding_ar=None))
    with pytest.raises(ValueError): protected(account(outstanding_ar='NaN'))


def test_chow_preserves_every_old_field_and_is_idempotent(tmp_path):
    original=account()
    store,crm,result=prepare(tmp_path,[original])
    p=next(p for p in result['proposals'] if p['kind']=='chow')
    assert crm.writes==[]
    approved=approve(store,crm,p['id'],'Reviewer')
    old=crm.get('old')
    for key,val in original.items():
        if key not in ('chow_current_account','updated_at'): assert old[key]==val
    assert old['chow_current_account']==approved['account_id']
    assert crm.get(approved['account_id'])['parent_id']=='parent'
    assert len(crm.writes)==2
    approve(store,crm,p['id'],'Reviewer')
    assert len(crm.writes)==2
    assert build(snapshot(),crm.accounts())['proposals']==[]


def test_direct_reparent_when_ar_zero(tmp_path):
    store,crm,result=prepare(tmp_path,[account(outstanding_ar=0)])
    p=result['proposals'][0]
    assert p['kind']=='update'
    approve(store,crm,p['id'],'Reviewer')
    assert crm.get('old')['parent_id']=='parent'
    assert len(crm.writes)==1
    assert crm.get('old')['note'].startswith('Original billing note.')


def test_balance_change_blocks_stale_approval(tmp_path):
    store,crm,result=prepare(tmp_path,[account(outstanding_ar=0)])
    crm.rows['old']['outstanding_ar']=500
    with pytest.raises(ValueError,match='changed'):
        approve(store,crm,result['proposals'][0]['id'],'Reviewer')
    assert crm.writes==[]


def test_preflight_failure_can_get_fresh_review(tmp_path):
    store,crm,result=prepare(tmp_path,[account(outstanding_ar=0)])
    pid=result['proposals'][0]['id']
    crm.rows['old']['phone']='555-888-9999'
    with pytest.raises(ValueError): approve(store,crm,pid,'Reviewer')
    store.save_run(snapshot(),crm.accounts(),build(snapshot(),crm.accounts()))
    assert store.get(pid)['state']=='pending'
    assert store.get(pid)['error'] is None
    approve(store,crm,pid,'Reviewer')
    assert crm.get('old')['phone']=='555-888-9999'


def test_duplicate_waits_for_survivor_correction(tmp_path):
    first=account(account_id='z',name='Legacy One',lifetime_revenue=0,outstanding_ar=0)
    second=account(account_id='a',name='Legacy Two',lifetime_revenue=0,outstanding_ar=0)
    store,crm,result=prepare(tmp_path,[first,second])
    duplicate=next(p for p in result['proposals'] if p['kind']=='duplicate')
    with pytest.raises(ValueError,match='survivor ownership'):
        approve(store,crm,duplicate['id'],'Reviewer')
    assert crm.writes==[]
    update=next(p for p in result['proposals'] if p['kind']=='update')
    approve(store,crm,update['id'],'Reviewer')
    approve(store,crm,duplicate['id'],'Reviewer')
    assert crm.get('a')['duplicate_of_account']=='z'


def test_duplicate_survivor_and_no_merge(tmp_path):
    winner=account(parent_id='parent',lifetime_revenue=0,outstanding_ar=0)
    loser=account(account_id='duplicate',name='Former Operator',lifetime_revenue=0,outstanding_ar=0)
    store,crm,result=prepare(tmp_path,[winner,loser])
    p=next(p for p in result['proposals'] if p['kind']=='duplicate')
    approve(store,crm,p['id'],'Reviewer')
    assert crm.get('duplicate')['duplicate_of_account']=='old'
    assert crm.get('duplicate')['status']=='Inactive'
    assert crm.get('duplicate')['parent_id']=='other'


def test_rejected_decision_persists_across_restart(tmp_path):
    store,crm,result=prepare(tmp_path,[account(parent_id='parent',billing_street='PO Box 10')])
    p=next(p for p in result['proposals'] if p['kind']=='address_review')
    reject(store,p['id'],'Reviewer','Physical address is not a verified billing address.')
    restarted=Store(tmp_path)
    summary=restarted.save_run(snapshot(),crm.accounts(),build(snapshot(),crm.accounts()))
    assert summary['added']==0
    assert restarted.get(p['id'])['state']=='rejected'
    assert crm.writes==[]


def test_lost_post_response_recovers_by_marker(tmp_path):
    store,crm,result=prepare(tmp_path,[account()])
    p=result['proposals'][0]; crm.fail_after_create=True
    with pytest.raises(ValueError): approve(store,crm,p['id'],'Reviewer')
    approve(store,crm,p['id'],'Reviewer')
    assert len([w for w in crm.writes if w[0]=='create'])==1
    assert crm.get('old')['chow_current_account']


def test_partial_chow_retries_only_missing_link(tmp_path):
    store,crm,result=prepare(tmp_path,[account()])
    p=result['proposals'][0]; crm.fail_link=True
    with pytest.raises(ValueError): approve(store,crm,p['id'],'Reviewer')
    approve(store,crm,p['id'],'Reviewer')
    assert len([w for w in crm.writes if w[0]=='create'])==1


def test_uncertain_create_is_never_blindly_retried(tmp_path):
    store,crm,result=prepare(tmp_path,[])
    p=result['proposals'][0]; crm.fail_before_create=True
    with pytest.raises(ValueError): approve(store,crm,p['id'],'Reviewer')
    crm.fail_before_create=False
    with pytest.raises(ValueError,match='uncertain'): approve(store,crm,p['id'],'Reviewer')
    assert crm.writes==[]


def test_absence_does_not_reparent_or_deactivate(tmp_path):
    store,crm,result=prepare(tmp_path,[account(parent_id='parent')],locs=[])
    p=result['proposals'][0]
    assert p['kind']=='absent'
    approve(store,crm,p['id'],'Reviewer')
    assert crm.get('old')['parent_id']=='parent'
    assert crm.get('old')['status']=='Needs Review'


def test_fuzzy_name_does_not_reparent_wrong_address(tmp_path):
    loc={**LOC,'phone':'555-111-1111'}
    store,crm,result=prepare(tmp_path,[account(billing_street='999 Elsewhere Rd')],locs=[loc])
    assert result['proposals'][0]['kind']=='create'
    assert result['proposals'][0]['alternatives']


def test_new_account_appearing_after_scan_blocks_create(tmp_path):
    store,crm,result=prepare(tmp_path,[])
    crm.rows['newly_added']=account(account_id='newly_added',parent_id='parent')
    with pytest.raises(ValueError,match='now exists'):
        approve(store,crm,result['proposals'][0]['id'],'Reviewer')
    assert crm.writes==[]


def test_unknown_care_label_fails_closed():
    with pytest.raises(ValueError): canonical_fields({**LOC,'care':['Unknown Specialty']},'parent')


def test_web_requires_csrf_and_get_never_writes(tmp_path):
    store,crm,result=prepare(tmp_path,[account()]); app=create_app(store,crm)
    client=app.test_client()
    assert client.get('/').status_code==200
    pid=result['proposals'][0]['id']
    assert client.get('/proposal/'+pid).status_code==200
    assert client.post('/proposal/'+pid+'/approve',data={'actor':'Reviewer'}).status_code==403
    assert crm.writes==[]


def detail(name,city='Sample'):
    return f'<h1>{name}</h1><dl class="detail"><dt>Address</dt><dd>12 Maple St<br>{city}, OH 44000</dd><dt>Care Offerings</dt><dd><span class="badge">Assisted Living</span></dd><dt>Phone</dt><dd>555-222-3333</dd></dl>'


def test_scraper_homepage_discovery_and_pagination():
    base='https://example.test'
    pages={base+'/':'We serve 3 communities <a href="/communities/new">New</a>',
      base+'/about':'About',base+'/communities':'2 communities listed <a href="/communities/a">A</a><a href="/communities?page=2">Next</a>',
      base+'/communities?page=2':'2 communities listed <a href="/communities/b">B</a>',
      base+'/communities/new':detail('New'),base+'/communities/a':detail('A'),base+'/communities/b':detail('B')}
    result=scrape(base,fetch=pages.__getitem__)
    assert len(result['locations'])==3
    pages[base+'/communities?page=2']='2 communities listed'
    with pytest.raises(ValueError,match='count check'): scrape(base,fetch=pages.__getitem__)


def test_broken_detail_is_not_silently_skipped():
    with pytest.raises(ValueError): parse_location('<h1>Error</h1>','https://example.test/a')
