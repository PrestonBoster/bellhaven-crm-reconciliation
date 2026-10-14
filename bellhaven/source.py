"""Read-only clients. Authentication is never sent to public website pages."""
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_BASE = 'https://analyst-assessment-production.up.railway.app'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def session():
    s = requests.Session()
    # Never retry a POST/PATCH automatically: the server has no idempotency keys.
    s.mount('https://', HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=.5, status_forcelist=[429, 502, 503, 504],
        allowed_methods=['GET'], respect_retry_after_header=True)))
    return s


class CRM:
    def __init__(self, token, base=DEFAULT_BASE):
        if not token:
            raise ValueError('Set CRM_API_TOKEN before connecting to the CRM.')
        self.base = base.rstrip('/')
        if urlparse(self.base).scheme != 'https':
            raise ValueError('The CRM requires HTTPS.')
        self.session = session()
        self.session.headers['Authorization'] = 'Bearer ' + token

    def request(self, method, path, **kwargs):
        r = self.session.request(method, self.base + '/api/v1' + path,
                                 timeout=(10, 30), allow_redirects=False, **kwargs)
        if r.status_code >= 300:
            # Avoid including credentials, payloads, or response bodies in errors.
            raise RuntimeError(f'CRM {method} returned HTTP {r.status_code}.')
        return r.json()

    def accounts(self):
        result, seen, total = [], set(), None
        for page in range(1, 1001):
            data = self.request('GET', '/accounts', params={'page': page, 'page_size': 100})
            rows = data.get('accounts', data.get('items', data.get('data')))
            if not isinstance(rows, list) or not isinstance(data.get('total'), int):
                raise ValueError('Unexpected account pagination schema; stopped safely.')
            if total is not None and total != data['total']:
                raise ValueError('CRM changed during pagination. Rerun the scan.')
            total = data['total']
            for row in rows:
                if row['account_id'] in seen:
                    raise ValueError('Repeated account across CRM pages.')
                seen.add(row['account_id'])
                result.append(row)
            if len(result) == total:
                return result
            if not rows or len(result) > total:
                raise ValueError('Incomplete CRM snapshot; stopped safely.')
        raise ValueError('CRM pagination exceeded safety limit.')

    def get(self, account_id):
        return self.request('GET', '/accounts/' + account_id)

    def patch(self, account_id, fields):
        return self.request('PATCH', '/accounts/' + account_id, json=fields)

    def create(self, fields):
        return self.request('POST', '/accounts', json=fields)


def parse_location(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    detail = soup.select_one('dl.detail')
    if not detail or not soup.h1:
        raise ValueError(f'Missing community detail: {url}')
    fields = {dt.get_text(' ', strip=True): dt.find_next_sibling('dd')
              for dt in detail.select('dt')}
    address = list(fields['Address'].stripped_strings)
    cityline = re.fullmatch(r'(.+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', address[-1])
    if len(address) != 2 or not cityline:
        raise ValueError(f'Unexpected address structure: {url}')
    care = [b.get_text(' ', strip=True) for b in fields['Care Offerings'].select('.badge')]
    if not care:
        raise ValueError(f'No care offerings: {url}')
    loc = dict(name=soup.h1.get_text(' ', strip=True), street=address[0],
               city=cityline[1], state=cityline[2], zip=cityline[3], care=care,
               phone=fields['Phone'].get_text(' ', strip=True), url=url)
    loc['source_hash'] = digest(loc)
    return loc


def scrape(base=DEFAULT_BASE, fetch=None):
    base = base.rstrip('/')
    s = session()
    def get(url):
        if fetch:
            return fetch(url)
        r = s.get(url, timeout=(10, 30), allow_redirects=False)
        if r.status_code != 200:
            raise ValueError(f'Website returned HTTP {r.status_code}; scan aborted.')
        return r.text
    queue = [base + '/', base + '/about', base + '/communities']
    seen, directory_links, detail_links, locations, pages = set(), set(), set(), {}, []
    expected, directory_expected = None, None
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        if len(seen) >= 200:
            raise ValueError('Website crawl exceeded 200 pages.')
        seen.add(url)
        html = get(url)
        soup = BeautifulSoup(html, 'html.parser')
        path = urlparse(url).path
        text = soup.get_text(' ', strip=True)
        pages.append({'url': url, 'sha256': hashlib.sha256(html.encode()).hexdigest()})
        if path == '/':
            m = re.search(r'serve\s+(\d+)\s+communities', text)
            expected = int(m[1]) if m else None
        if path.rstrip('/') == '/communities':
            m = re.search(r'(\d+) communities listed', text)
            if m:
                if directory_expected not in (None, int(m[1])):
                    raise ValueError('Directory totals disagree.')
                directory_expected = int(m[1])
        if path.startswith('/communities/'):
            locations[url] = parse_location(html, url)
        for anchor in soup.select('a[href]'):
            link = urljoin(url, anchor['href']).split('#')[0]
            parsed = urlparse(link)
            if parsed.netloc != urlparse(base).netloc or not parsed.path.startswith('/communities'):
                continue
            if parsed.path.startswith('/communities/'):
                detail_links.add(link)
                if path.rstrip('/') == '/communities':
                    directory_links.add(link)
            if link not in seen:
                queue.append(link)
    if not locations or set(locations) != detail_links:
        raise ValueError('Incomplete community extraction; no proposals were saved.')
    if directory_expected is None or len(directory_links) != directory_expected:
        raise ValueError('Directory count check failed; no proposals were saved.')
    if expected is None or len(locations) != expected:
        raise ValueError('Homepage count check failed; investigate before proceeding.')
    return {'at': now(), 'locations': sorted(locations.values(), key=lambda x: x['name']),
            'pages': pages, 'directory_count': directory_expected,
            'homepage_count': expected, 'complete': True}
