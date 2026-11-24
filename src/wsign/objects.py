"""Response objects.

Every JSON object returned by the API becomes a :class:`WsignObject`: read-only attribute access
(``sr.status``), item access (``sr["status"]``), nested objects (``event.data.object.id``) and
:meth:`WsignObject.to_dict` for the decoded JSON. Typed subclasses are chosen from the JSON
``object`` field and document their fields for editors and type checkers. Fields the API adds later
stay readable as attributes, so new API fields never break existing code.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeVar

__all__ = [
    "Account",
    "AuditEvent",
    "Balance",
    "BulkSend",
    "Certificate",
    "DeletedWebhookEndpoint",
    "Document",
    "Download",
    "Event",
    "EventRedelivery",
    "Evidence",
    "Flow",
    "IdentityVerification",
    "Money",
    "NameMatch",
    "PdfFile",
    "RateLimit",
    "Reminder",
    "ResponseInfo",
    "SavedPdf",
    "Session",
    "SessionSigner",
    "SignatureRequest",
    "Signer",
    "SigningSession",
    "Template",
    "TemplateField",
    "Usage",
    "Verification",
    "WebhookDelivery",
    "WebhookEndpoint",
    "WebhookTestResult",
    "WsignObject",
    "convert",
]

T = TypeVar("T", bound="WsignObject")


@dataclass(frozen=True)
class RateLimit:
    """The ``X-RateLimit-*`` headers of a response."""

    limit: int
    remaining: int
    reset: int
    """Unix timestamp at which the window resets."""


@dataclass(frozen=True)
class ResponseInfo:
    """HTTP metadata of the call that produced an object (``obj.last_response``)."""

    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)
    """Response headers with lower-case names."""

    @property
    def request_id(self) -> str | None:
        """The ``Wsign-Request-Id`` header (``req_…``). Quote it to support."""
        return self.headers.get("wsign-request-id")

    @property
    def api_version(self) -> str | None:
        """The ``Wsign-Version`` header."""
        return self.headers.get("wsign-version")

    @property
    def idempotent_replayed(self) -> bool:
        """``True`` when the API replayed a stored response for the same ``Idempotency-Key``."""
        return self.headers.get("idempotent-replayed", "").strip().lower() == "true"

    @property
    def rate_limit(self) -> RateLimit | None:
        """The rate-limit window, when the headers are present."""
        values = [
            self.headers.get(f"x-ratelimit-{name}", "").strip()
            for name in ("limit", "remaining", "reset")
        ]
        if not all(value.isascii() and value.isdigit() for value in values):
            return None
        return RateLimit(int(values[0]), int(values[1]), int(values[2]))

    def get_header(self, name: str) -> str | None:
        """Returns a header (case-insensitive) or ``None``."""
        return self.headers.get(name.lower())


_REGISTRY: dict[str, type[WsignObject]] = {}
_FIELDS: dict[type[WsignObject], frozenset[str]] = {}


def _declared_fields(cls: type[WsignObject]) -> frozenset[str]:
    cached = _FIELDS.get(cls)
    if cached is not None:
        return cached
    names: set[str] = set()
    for klass in cls.__mro__:
        if klass is WsignObject or not issubclass(klass, WsignObject):
            continue
        for name, annotation in inspect.get_annotations(klass).items():
            if not name.startswith("_") and "ClassVar" not in str(annotation):
                names.add(name)
    result = frozenset(names)
    _FIELDS[cls] = result
    return result


def _register(name: str) -> Any:
    def decorator(cls: type[T]) -> type[T]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def convert(value: Any, cls: type[WsignObject] | None = None) -> Any:
    """Converts decoded JSON into response objects (dicts become objects, lists stay lists)."""
    if isinstance(value, list):
        return [convert(item, cls) for item in value]
    if isinstance(value, dict):
        target = cls
        if target is None:
            name = value.get("object")
            target = _REGISTRY.get(name, WsignObject) if isinstance(name, str) else WsignObject
        return target(value)
    return value


def _to_plain(value: Any) -> Any:
    if isinstance(value, WsignObject):
        return value.to_dict()
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


def _restore(cls: type[WsignObject], values: dict[str, Any]) -> WsignObject:
    return cls(values)


def _mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (f"{item[:6]}…" if key == "secret" and isinstance(item, str) else _mask(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask(item) for item in value]
    return value


class WsignObject:
    """An immutable API object with attribute and item access."""

    __slots__ = ("_last_response", "_values")

    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {}

    def __init__(
        self, values: Mapping[str, Any] | None = None, *, last_response: ResponseInfo | None = None
    ) -> None:
        nested = type(self)._nested
        converted = {
            key: convert(item, nested.get(key)) for key, item in dict(values or {}).items()
        }
        object.__setattr__(self, "_values", converted)
        object.__setattr__(self, "_last_response", last_response)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        if name in _declared_fields(type(self)):
            return None
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"{type(self).__name__} objects are read-only.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} objects are read-only.")

    def __getitem__(self, key: str) -> Any:
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        return values[key]

    def __contains__(self, key: object) -> bool:
        return key in object.__getattribute__(self, "_values")

    def get(self, key: str, default: Any = None) -> Any:
        """Returns the field ``key`` or ``default`` when it is absent."""
        return object.__getattribute__(self, "_values").get(key, default)

    def keys(self) -> Iterator[str]:
        """The field names present in the response."""
        return iter(object.__getattribute__(self, "_values"))

    def to_dict(self) -> dict[str, Any]:
        """Returns the object as plain JSON-compatible data."""
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        return {key: _to_plain(item) for key, item in values.items()}

    def to_json(self, *, indent: int | None = None) -> str:
        """Returns the object as a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @property
    def last_response(self) -> ResponseInfo | None:
        """HTTP metadata of the call that returned this object (top-level objects only)."""
        info: ResponseInfo | None = object.__getattribute__(self, "_last_response")
        return info

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WsignObject):
            return type(self) is type(other) and self.to_dict() == other.to_dict()
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(object.__getattribute__(self, "_values")))

    def __reduce__(self) -> tuple[Any, ...]:
        return (_restore, (type(self), self.to_dict()))

    def __repr__(self) -> str:
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        ident = values.get("id")
        head = (
            f"<{type(self).__name__}" + (f" id={ident!r}" if isinstance(ident, str) else "") + ">"
        )
        return f"{head} {json.dumps(_mask(self.to_dict()), ensure_ascii=False)}"

    def __str__(self) -> str:
        return json.dumps(_mask(self.to_dict()), ensure_ascii=False, indent=2)


# --- shared nested objects -------------------------------------------------------------------


class Money(WsignObject):
    """An amount of money: ``amount`` (decimal), ``amount_minor`` (piastres/cents), ``currency``."""

    __slots__ = ()
    amount: float
    amount_minor: int
    currency: str


class AccountInfo(WsignObject):
    __slots__ = ()
    id: str
    name: str
    email: str | None


class RootPlan(WsignObject):
    __slots__ = ()
    id: str
    paid: bool
    sends_left: int


class RootPricing(WsignObject):
    __slots__ = ()
    overage_per_request: float
    identity_per_signer: float
    currency: str


@_register("api_root")
class Account(WsignObject):
    """``GET /``: the account, plan and pricing of the API key."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "account": AccountInfo,
        "plan": RootPlan,
        "pricing": RootPricing,
    }
    object: str
    name: str
    version: str
    livemode: bool
    base_url: str
    account: AccountInfo
    plan: RootPlan
    pricing: RootPricing
    docs: str


class UsagePlan(WsignObject):
    __slots__ = ()
    id: str
    name: str
    paid: bool
    period_start: int | None
    period_end: int | None
    sends_quota: int
    sends_used: int
    sends_left: int
    auto_renew: bool


class UsagePricing(WsignObject):
    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "overage_per_request": Money,
        "identity_per_signer": Money,
        "min_topup": Money,
    }
    overage_per_request: Money
    identity_per_signer: Money
    min_topup: Money
    currency: str


class UsageCounts(WsignObject):
    __slots__ = ()
    total: int
    last_30_days: int
    completed: int


@_register("balance")
class Balance(WsignObject):
    """``GET /balance``: wallet balance and plan quota."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "balance": Money,
        "month_spent": Money,
        "plan": UsagePlan,
    }
    object: str
    livemode: bool
    balance: Money
    month_spent: Money
    plan: UsagePlan


@_register("usage")
class Usage(Balance):
    """``GET /usage``: balance, plan quota, pricing and request counts."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        **Balance._nested,
        "pricing": UsagePricing,
        "signature_requests": UsageCounts,
    }
    pricing: UsagePricing
    signature_requests: UsageCounts


# --- templates -------------------------------------------------------------------------------


class TemplateField(WsignObject):
    """A placeholder field of a template."""

    __slots__ = ()
    key: str
    label: str
    type: str
    required: bool
    type_declared: bool | None
    vtype: str | None


@_register("template")
class Template(WsignObject):
    """A contract template."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {"fields": TemplateField}
    id: str
    object: str
    name: str
    category: str | None
    languages: list[str]
    fields: list[TemplateField]
    created_at: int
    content: str | None
    """Only with ``include="content"`` on your own templates."""


# --- signature requests ----------------------------------------------------------------------


class NameMatch(WsignObject):
    """The signer name in the request compared with the name on the identity document.

    ``state`` is ``not_compared``, ``auto_ok`` (same or near-identical name), ``awaiting``
    (different name, signing held until you decide with ``signers.decide_identity_match()``),
    ``recorded`` (different name, logged without a hold), ``approved``, ``rejected`` or
    ``expired``. ``verdict`` is ``match``, ``minor`` (one part differs), ``major`` or ``na``
    (not comparable).
    """

    __slots__ = ()
    state: str
    verdict: str
    expected_name: str
    """The signer name sent in the request."""
    document_name: str
    """The name read from the identity document."""
    document_type: str
    country: str
    """Issuing country of the document."""
    id_last4: str
    """Last four characters of the document number."""
    decided_by: str
    """Who decided (empty until a decision), e.g. ``API``."""
    decided_at: int | None
    deadline: int
    """Unix time after which an undecided hold expires."""

    @property
    def is_awaiting_decision(self) -> bool:
        """``True`` while signing is held for a decision."""
        return self.state == "awaiting"


class SignerIdentity(WsignObject):
    """Identity verification state of a signer."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {"name_match": NameMatch}
    status: str
    provider: str
    level: str
    verification_id: str | None
    reason_code: str | None
    updated_at: int | None
    resubmit_steps: list[str] | None
    name_match: NameMatch | None
    """The name-match result, or ``None`` when no comparison was recorded."""


@_register("signer")
class Signer(WsignObject):
    """A signer of a signature request."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "identity": SignerIdentity,
        "identity_match": NameMatch,
    }
    id: str
    object: str
    name: str
    email: str | None
    phone: str | None
    type: str
    method: str
    require_identity: bool
    order: int
    status: str
    signing_url: str | None
    viewed_at: int | None
    signed_at: int | None
    fields: WsignObject
    identity: SignerIdentity | None
    signature_request: str | None
    """Only inside ``signer.*`` webhook payloads."""
    workflow_id: str | None
    workflow_version: int | None
    vendor_data: str | None
    identity_match: NameMatch | None
    """Only inside ``signer.identity_match_hold`` and ``signer.identity_match_decided`` payloads."""


class Source(WsignObject):
    __slots__ = ()
    type: str
    template_id: str | None
    document_id: str | None


class Reminders(WsignObject):
    __slots__ = ()
    enabled: bool
    interval_hours: int | None
    max: int | None


class CcRecipient(WsignObject):
    __slots__ = ()
    name: str
    email: str


@_register("signature_request")
class SignatureRequest(WsignObject):
    """A signature request."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "source": Source,
        "signers": Signer,
        "cc": CcRecipient,
        "reminders": Reminders,
    }
    id: str
    object: str
    livemode: bool
    status: str
    title: str
    legal_level: str
    format: str
    source: Source
    signers: list[Signer]
    ordered: bool
    require_identity: bool
    reference: str | None
    cc: list[CcRecipient]
    reminders: Reminders
    metadata: WsignObject
    expires_at: int | None
    completed_at: int | None
    download_url: str | None
    created_at: int
    workflow_id: str | None
    workflow_version: int | None
    vendor_data: str | None
    channel: str | None
    return_url: str | None
    trial: bool | None


class BulkSendResult(WsignObject):
    __slots__ = ()
    signature_request: str
    email: str | None
    phone: str | None
    status: str


class BulkSendError(WsignObject):
    __slots__ = ()
    email: str | None
    phone: str | None
    error: str
    code: str


@_register("bulk_send")
class BulkSend(WsignObject):
    """Result of ``POST /signature_requests/bulk``."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "requests": BulkSendResult,
        "errors": BulkSendError,
    }
    object: str
    created: int
    failed: int
    requests: list[BulkSendResult]
    errors: list[BulkSendError]


@_register("reminder")
class Reminder(WsignObject):
    __slots__ = ()
    object: str
    signature_request: str
    reminders_sent: int


class AuditEvent(WsignObject):
    """An entry of ``GET /signature_requests/{id}/events``."""

    __slots__ = ()
    id: str
    object: str
    type: str
    actor: str
    ip: str | None
    signature_request: str
    created_at: int
    to: str | None
    description: str | None


class CertificateSigner(WsignObject):
    __slots__ = ()
    name: str
    email: str | None
    phone: str | None
    status: str
    signed_at: int | None


class AuditTrailEntry(WsignObject):
    __slots__ = ()
    event: str
    actor: str
    ip: str | None
    at: int


@_register("certificate")
class Certificate(WsignObject):
    """Completion certificate of a signature request."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "signers": CertificateSigner,
        "audit_trail": AuditTrailEntry,
    }
    object: str
    signature_request: str
    status: str
    reference: str | None
    legal_level: str
    format: str
    completed_at: int | None
    signers: list[CertificateSigner]
    audit_trail: list[AuditTrailEntry]
    verify_url: str | None
    test: bool | None
    legal_effect: str | None
    watermark: str | None


@_register("download")
class Download(WsignObject):
    """Metadata of the final document of a completed request."""

    __slots__ = ()
    object: str
    signature_request: str
    pdf_url: str | None
    pdf_status: str
    pdf_sha256: str | None
    pdf_bytes: int | None
    pdf_generated_at: int | None
    final_document_url: str | None
    reference: str | None
    format: str
    legal_level: str
    test: bool | None
    legal_effect: str | None
    watermark: str | None


class EvidenceSeal(WsignObject):
    __slots__ = ()
    signature_alg: str
    signature: str
    public_key: str
    key_id: str
    trust_url: str
    timestamp_token: str
    timestamp_gentime: str


@_register("evidence")
class Evidence(WsignObject):
    """Sealed evidence record (live) or unsealed test record (test mode, ``seal`` is ``None``)."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {"seal": EvidenceSeal}
    object: str
    signature_request: str
    format: str
    issued_at: str
    verify_ref: str | None
    record: WsignObject
    record_raw: str | None
    seal: EvidenceSeal | None
    platform_verification: WsignObject | None
    how_to_verify: str | None
    livemode: bool | None
    test: bool | None
    legal_effect: str | None
    watermark: str | None
    notice: str | None


# --- sessions, signers, documents ------------------------------------------------------------


class SessionSigner(WsignObject):
    __slots__ = ()
    id: str
    name: str
    email: str | None
    phone: str | None
    status: str
    sign_url: str | None


class SessionCost(WsignObject):
    __slots__ = ()
    amount: float
    currency: str
    source: str | None


@_register("session")
class Session(WsignObject):
    """A signature request created from a workflow (``POST /sessions``)."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {
        "signers": SessionSigner,
        "cost": SessionCost,
    }
    id: str
    object: str
    status: str
    workflow_id: str
    workflow_version: int | None
    vendor_data: str | None
    channel: str
    signers: list[SessionSigner]
    sign_url: str | None
    """Only when the session has exactly one signer."""
    created_at: int
    expires_at: int | None
    livemode: bool
    cost: SessionCost
    return_url: str | None
    trial: bool | None


@_register("signing_session")
class SigningSession(WsignObject):
    """A short-lived embedded or redirect signing link (valid for 30 minutes)."""

    __slots__ = ()
    object: str
    signer: str
    mode: str
    signing_url: str
    expires_at: int
    success_url: str | None
    cancel_url: str | None


@_register("document")
class Document(WsignObject):
    """An uploaded PDF document."""

    __slots__ = ()
    id: str
    object: str
    kind: str
    filename: str
    pages: int
    bytes: int
    sha256: str
    fields: list[WsignObject]
    created_at: int


@_register("identity_verification")
class IdentityVerification(WsignObject):
    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {"name_match": NameMatch}
    id: str
    object: str
    provider: str
    signer: str | None
    status: str
    level: str
    verification_url: str | None
    name_match: NameMatch | None
    """The name-match result of this verification, or ``None``."""
    created_at: int


@_register("verification")
class Verification(WsignObject):
    """Result of a reference lookup. ``found`` is ``False`` when the reference is unknown."""

    __slots__ = ()
    object: str
    reference: str
    found: bool
    status: str
    integrity: str
    structure: str | None
    document: WsignObject | None
    signed_at: int | None
    parties: list[WsignObject] | None
    events: list[WsignObject] | None
    qr: str | None
    verify_url: str | None
    signature_request: str | None
    created_at: int | None


# --- webhooks and events ---------------------------------------------------------------------


@_register("webhook_endpoint")
class WebhookEndpoint(WsignObject):
    """A webhook endpoint. ``secret`` is only present in the create response."""

    __slots__ = ()
    id: str
    object: str
    url: str
    enabled_events: list[str]
    status: str
    livemode: bool
    created_at: int
    secret: str | None


class DeletedWebhookEndpoint(WsignObject):
    __slots__ = ()
    id: str
    object: str
    deleted: bool


@_register("webhook_delivery")
class WebhookDelivery(WsignObject):
    __slots__ = ()
    object: str
    event: str
    event_type: str
    status: str
    attempts: int
    response_code: int | None
    created_at: int
    updated_at: int | None


@_register("webhook_test")
class WebhookTestResult(WsignObject):
    __slots__ = ()
    object: str
    endpoint: str
    response_code: int | None
    error: str
    ok: bool


class EventData(WsignObject):
    __slots__ = ()
    object: Any
    """The event resource: :class:`SignatureRequest`, :class:`Signer` or :class:`Verification`."""


@_register("event")
class Event(WsignObject):
    """A webhook event (also returned by ``GET /events``)."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {"data": EventData}
    id: str
    object: str
    type: str
    created_at: int
    livemode: bool
    data: EventData


class RedeliveryAttempt(WsignObject):
    __slots__ = ()
    endpoint: str
    status: str
    response_code: int | None
    error: str | None


@_register("event_redelivery")
class EventRedelivery(WsignObject):
    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WsignObject]]] = {"deliveries": RedeliveryAttempt}
    object: str
    event: str
    deliveries: list[RedeliveryAttempt]


@_register("flow")
class Flow(WsignObject):
    """An embeddable console flow (read-only)."""

    __slots__ = ()
    id: str
    object: str
    name: str
    template_id: str | None
    legal_level: str
    reminders: bool
    lock_contract: bool
    cc: list[Any]
    created_at: int


# --- downloads -------------------------------------------------------------------------------


class PdfFile(bytes):
    """The bytes of a downloaded PDF, with the HTTP details of the download."""

    sha256: str
    """SHA-256 of the bytes (checked against the ``X-File-Sha256`` header when sent)."""
    filename: str | None
    """File name from the ``Content-Disposition`` header."""
    last_response: ResponseInfo | None

    def __new__(
        cls,
        content: bytes,
        *,
        sha256: str,
        filename: str | None = None,
        last_response: ResponseInfo | None = None,
    ) -> PdfFile:
        instance = super().__new__(cls, content)
        instance.sha256 = sha256
        instance.filename = filename
        instance.last_response = last_response
        return instance

    def __reduce__(self) -> tuple[Any, ...]:
        return (bytes, (bytes(self),))


@dataclass(frozen=True)
class SavedPdf:
    """Result of ``download_pdf_to``."""

    path: str
    bytes: int
    sha256: str
