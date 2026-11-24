"""How the library reports errors."""

from __future__ import annotations

from _client import client

import wsign

wt = client()

try:
    wt.signature_requests.create(
        source={"type": "template", "template_id": "tpl_0"},
        signers=[{"name": "Someone", "email": "not-an-email"}],
        send=False,
    )
except wsign.TooManySignersError as e:
    print("too many signers: at most", e.max_signers, "per request")
except wsign.ValidationError as e:
    print("validation:", e.code, e.param, e.field_errors, e.request_id)
except wsign.NotFoundError as e:
    print("not found:", e.code, e.request_id)
except wsign.PermissionDeniedError as e:
    if e.is_kyb_required():
        print("verify your company first:", e.verify_url)
    else:
        print("permission:", e.code, e.feature, e.upgrade_url)
except wsign.PaymentRequiredError as e:
    print("payment required:", e.code, e.upgrade_url)
except wsign.RateLimitError as e:
    print("rate limited:", e.code, e.retry_after)
except wsign.ApiConnectionError as e:
    print("network problem:", e)

result = wt.verifications.retrieve("WTQ-UNKNOWN")
print("verification found:", result.found, result.status)
