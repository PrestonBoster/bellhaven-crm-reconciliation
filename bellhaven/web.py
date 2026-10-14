import os
import secrets
from collections import Counter
from urllib.parse import urlparse
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from .service import approve, reject, scan

LABELS = {'update':'Correct account','chow':'Protected ownership change','create':'Create account',
          'duplicate':'Resolve duplicate','duplicate_review':'Review duplicate',
          'address_review':'Verify billing address','absent':'Investigate absence'}


def create_app(store, crm):
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      MAX_CONTENT_LENGTH=16*1024)

    @app.before_request
    def guard():
        if request.host.split(':')[0] not in ('127.0.0.1','localhost'):
            abort(403)
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(24)
        if request.method == 'POST':
            if request.headers.get('Origin') and urlparse(request.headers['Origin']).netloc != request.host:
                abort(403)
            supplied = request.form.get('csrf') or request.headers.get('X-CSRF-Token','')
            if not secrets.compare_digest(supplied,session['csrf']):
                abort(403)

    def context():
        rows = store.all()
        return dict(rows=rows, counts=Counter(r['state'] for r in rows), latest=store.latest(),
                    labels=LABELS, reviewer=os.environ.get('BELLHAVEN_REVIEWER','Local reviewer'))

    @app.get('/')
    def index():
        ctx = context()
        selected = request.args.get('state','pending')
        ctx['selected'] = selected
        ctx['visible'] = [r for r in ctx['rows'] if r['state']==selected] if selected != 'all' else ctx['rows']
        return render_template('index.html',**ctx)

    @app.get('/proposal/<proposal_id>')
    def proposal(proposal_id):
        row = store.get(proposal_id)
        if not row:
            abort(404)
        return render_template('proposal.html', row=row, p=row['payload'], **context())

    @app.post('/proposal/<proposal_id>/<action>')
    def decision(proposal_id,action):
        actor = request.form.get('actor','').strip()
        try:
            if action == 'approve':
                approve(store,crm,proposal_id,actor)
            elif action == 'reject':
                reject(store,proposal_id,actor,request.form.get('reason',''))
            else:
                abort(404)
        except ValueError as exc:
            return render_template('error.html',message=str(exc),proposal_id=proposal_id,**context()),409
        return redirect(url_for('proposal',proposal_id=proposal_id))

    @app.post('/scan')
    def rescan():
        try:
            scan(store,crm)
        except Exception as exc:
            message = str(exc) if isinstance(exc,(ValueError,RuntimeError)) else 'Scan failed; the previous queue is unchanged.'
            return render_template('error.html',message=message,proposal_id=None,**context()),409
        return redirect(url_for('index'))

    @app.get('/api/summary')
    def summary():
        return jsonify(latest=store.latest(), counts=Counter(r['state'] for r in store.all()))

    @app.get('/crm/<account_id>')
    def crm_link(account_id):
        # Token appears only in the external CRM browser URL, never in rendered HTML.
        if not any(account_id == a for row in store.all() for a in [
            (row['payload']['before'] or {}).get('account_id'),
            (row['result'] or {}).get('account_id')]):
            abort(404)
        token = crm.session.headers['Authorization'].removeprefix('Bearer ')
        return redirect(crm.base + '/crm/' + token + '/accounts/' + account_id)

    return app
