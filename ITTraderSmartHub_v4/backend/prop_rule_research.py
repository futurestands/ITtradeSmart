"""Multi-firm official-source research and account binding; no rule approval.

Public pages are evidence candidates, never executable policy or instructions.
No account identifiers, credentials or balances are sent to the public web.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import re
import ssl
from types import MappingProxyType
import urllib.request

SOURCES = MappingProxyType({
    'ftmo_objectives': ('FTMO', 'https://ftmo.com/en/trading-objectives/'),
    'fundednext_help': ('FUNDEDNEXT', 'https://help.fundednext.com/en/'),
    'goat_rules': ('GOAT', 'https://help.goatfundedtrader.com/en/collections/11969353-rules'),
    'fundingpips_policy': ('FUNDINGPIPS', 'https://help.fundingpips.com/hc/en-us/articles/47328410434065-Responsible-Trading-Policy'),
})
FIRMS = frozenset(firm for firm, _ in SOURCES.values())


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _utc(value):
    return isinstance(value, datetime) and value.utcoffset() == timedelta(0)


def _digest(value):
    return isinstance(value, str) and bool(re.fullmatch('[0-9a-f]{64}', value))


def fingerprint_source(source_id):
    """Fetch only a server-controlled exact HTTPS URL; never a user URL.

    A hash change can be a harmless page edit. It triggers review, never an
    automatic increase in risk. Index pages do not constitute complete terms.
    """
    if source_id not in SOURCES:
        raise ValueError('Unknown official source ID')
    firm, url = SOURCES[source_id]
    report = {'source_id': source_id, 'firm': firm, 'source_url': url,
              'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'rules_verified_for_account': False, 'execution_authorized': False,
              'decision': 'NO_TRADE', 'mode': 'RESEARCH_ONLY', 'model_status': 'MODEL_NOT_READY'}
    try:
        # OS trust store with hostname verification and CERT_REQUIRED. No
        # optional package is needed and there is no insecure fallback.
        context = ssl.create_default_context()
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirects())
        request = urllib.request.Request(url, headers={'User-Agent': 'SmartHub-ReadOnly-Rule-Review/1.0'})
        with opener.open(request, timeout=20) as response:
            if response.geturl() != url:
                raise ValueError('Unexpected endpoint')
            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Unexpected content type')
            payload = response.read(2_000_001)
            if not payload or len(payload) > 2_000_000:
                raise ValueError('Invalid document size')
        report.update(status='RESEARCH_CANDIDATE_REVIEW_REQUIRED', bytes=len(payload),
                      content_sha256=hashlib.sha256(payload).hexdigest(), tls_certificate_verification=True)
    except Exception as error:
        report.update(status='SOURCE_UNAVAILABLE_NO_NEW_PLAN', error_type=type(error).__name__, details_withheld=True)
    return report


@dataclass(frozen=True)
class AccountRuleContext:
    # Opaque private local reference; never send to a search provider.
    account_ref: str
    firm: str
    programme: str
    stage: str
    currency: str
    original_size: Decimal
    # Explicit account creation/purchase/legacy-terms cohort, not guessed from server.
    terms_version: str

    def __post_init__(self):
        if (self.firm not in FIRMS or any(not isinstance(v, str) or not v.strip()
                for v in (self.account_ref, self.programme, self.stage, self.terms_version))
                or not isinstance(self.currency, str) or not re.fullmatch('[A-Z]{3}', self.currency)
                or type(self.original_size) is not Decimal or not self.original_size.is_finite()
                or self.original_size <= 0):
            raise ValueError('Complete explicit account context required')


def review_source_binding(active, reviewed, *, source_id, approved_hash, current_hash,
                          checked_at, now, max_age_seconds=86400):
    """Research gate only: an unchanged page is not verified account policy.

    Every change to the account context invalidates the earlier binding. The
    existing compliance/risk engines remain authoritative and are not modified.
    """
    if not isinstance(active, AccountRuleContext) or not isinstance(reviewed, AccountRuleContext):
        raise ValueError('Typed account contexts required')
    result = {'status': 'REVIEW_REQUIRED', 'blockers': [], 'rules_verified_for_account': False,
              'execution_authorized': False, 'decision': 'NO_TRADE', 'mode': 'RESEARCH_ONLY',
              'model_status': 'MODEL_NOT_READY'}
    reasons = result['blockers']
    if active != reviewed:
        reasons.append('ACCOUNT_CONTEXT_CHANGED_REVIEW_REQUIRED')
    if source_id not in SOURCES or SOURCES[source_id][0] != active.firm:
        reasons.append('SOURCE_FIRM_MISMATCH_OR_UNSUPPORTED')
    if not _digest(approved_hash) or not _digest(current_hash):
        reasons.append('SOURCE_EVIDENCE_MISSING')
    elif approved_hash != current_hash:
        reasons.append('SOURCE_CHANGED_REVIEW_REQUIRED')
    if (type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400
            or not _utc(now) or not _utc(checked_at)
            or not 0 <= (now - checked_at).total_seconds() <= max_age_seconds):
        reasons.append('STALE_FUTURE_OR_INVALID_SOURCE_CHECK')
    if not reasons:
        result['status'] = 'SOURCE_UNCHANGED_ACCOUNT_TERMS_REVIEW_STILL_REQUIRED'
    return result
