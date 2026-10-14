import argparse
import json
import os
from .source import CRM, DEFAULT_BASE
from .store import Store
from .service import scan


def main():
    parser = argparse.ArgumentParser(description='Bellhaven evidence-led reconciliation')
    parser.add_argument('command',choices=['scan','serve','summary'])
    parser.add_argument('--port',type=int,default=8765)
    args = parser.parse_args()
    store = Store(os.environ.get('BELLHAVEN_DATA_DIR','data'))
    if args.command == 'summary':
        from collections import Counter
        print(json.dumps({'latest':store.latest(),'counts':Counter(r['state'] for r in store.all())},indent=2))
        return
    crm = CRM(os.environ.get('CRM_API_TOKEN'),os.environ.get('CRM_BASE_URL',DEFAULT_BASE))
    if args.command == 'scan':
        result = scan(store,crm)
        print(json.dumps({k:v for k,v in result.items() if k!='matches'},indent=2))
    else:
        from .web import create_app
        create_app(store,crm).run(host='127.0.0.1',port=args.port,debug=False)


if __name__ == '__main__':
    main()
