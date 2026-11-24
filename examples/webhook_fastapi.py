"""Receive webhooks with FastAPI.

pip install fastapi uvicorn
WSIGN_WEBHOOK_SECRET=whsec_... uvicorn examples.webhook_fastapi:app
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request

import wsign

app = FastAPI()
endpoint_secret = os.environ["WSIGN_WEBHOOK_SECRET"]


@app.post("/hooks/wsign")
async def handle(request: Request) -> dict[str, bool]:
    payload = await request.body()  # the raw body, never a re-encoded JSON document
    try:
        event = wsign.Webhook.construct_event(
            payload, request.headers.get("Wsign-Signature"), endpoint_secret
        )
    except wsign.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="invalid signature") from None
    if event.type == "signature_request.completed":
        print("completed:", event.data.object.id)
    return {"received": True}
