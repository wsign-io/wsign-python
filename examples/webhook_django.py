"""Receive webhooks with Django: add the view to your urls.py.

path("hooks/wsign", webhook_django.wsign_webhook)
"""

from __future__ import annotations

import os

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import wsign

endpoint_secret = os.environ["WSIGN_WEBHOOK_SECRET"]


@csrf_exempt
@require_POST
def wsign_webhook(request: HttpRequest) -> HttpResponse:
    try:
        event = wsign.Webhook.construct_event(
            request.body, request.headers.get("Wsign-Signature"), endpoint_secret
        )
    except wsign.SignatureVerificationError:
        return HttpResponseBadRequest("invalid signature")
    if event.type == "signature_request.completed":
        print("completed:", event.data.object.id)
    return HttpResponse(status=200)
