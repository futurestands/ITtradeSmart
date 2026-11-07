"""On-demand official-page fingerprint. No rule auto-approval or scheduling."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import ssl
import urllib.request
import urllib.error
import certifi

URL='https://ftmo.com/en/trading-objectives/'
class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def fingerprint(approved_hash=None):
    report={'source_url':URL,'checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'execution_authorized':False,'rules_verified_for_account':False,
        'mode':'RESEARCH_ONLY','decision':'NO_TRADE'}
    try:
        opener=urllib.request.build_opener(urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=certifi.where())),NoRedirects())
        request=urllib.request.Request(URL,headers={'User-Agent':'SmartHub-ReadOnly-Rule-Review/1.0'})
        with opener.open(request,timeout=20) as response:
            if response.geturl()!=URL: raise ValueError('Unexpected endpoint')
            payload=response.read(2_000_001)
            if not payload or len(payload)>2_000_000: raise ValueError('Invalid document size')
            if 'text/html' not in response.headers.get('Content-Type','').lower(): raise ValueError('Unexpected content type')
        digest=hashlib.sha256(payload).hexdigest()
        report.update(content_sha256=digest,bytes=len(payload),tls_certificate_verification=True,
            status=('SOURCE_UNCHANGED_REVIEWED_ACCOUNT_BINDING_STILL_REQUIRED' if approved_hash==digest
                else 'SOURCE_CHANGED_REVIEW_REQUIRED' if approved_hash else 'REVIEW_REQUIRED_NO_APPROVED_BASELINE'))
    except Exception as error:
        report.update(status='SOURCE_UNAVAILABLE_NO_NEW_PLAN',error_type=type(error).__name__,
            http_status=getattr(error,'code',None),details_withheld=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-hash')
    args=parser.parse_args()
    print(json.dumps(fingerprint(args.approved_hash),indent=2))
