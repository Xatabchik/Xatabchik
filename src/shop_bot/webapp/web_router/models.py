"""Pydantic-модели запросов Mini App.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


from pydantic import BaseModel


class SupportStatusRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    token: str | None = None
    init_data: str | None = None


class SupportTicketCreateRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    subject: str
    token: str | None = None
    init_data: str | None = None


class SupportMessageSendRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    ticket_id: int
    message: str
    token: str | None = None
    init_data: str | None = None


class SupportTicketRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    ticket_id: int
    token: str | None = None
    init_data: str | None = None


class PaymentMethodsRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    token: str | None = None
    init_data: str | None = None


class TokenRequest(BaseModel):
    init_data: str


class TelegramDirectAuthRequest(BaseModel):
    """Must carry signed Telegram WebApp initData — never a bare user_id."""
    init_data: str


class EmailAuthRequest(BaseModel):
    email: str
    password: str


class EmailVerifyRequest(BaseModel):
    email: str
    code: str


class EmailResendRequest(BaseModel):
    email: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetCheckRequest(BaseModel):
    email: str
    code: str


class PasswordResetVerifyRequest(BaseModel):
    email: str
    code: str
    new_password: str


class SyncTgRequest(BaseModel):
    token: str
    init_data: str


class DeviceTiersRequest(BaseModel):
    host_name: str


class CreatePaymentRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    payment_method: str
    plan_id: int
    host_name: str | None = None
    action: str
    key_id: int | None = None
    promo_code: str | None = None
    tier_device_count: int | None = None
    tier_price: float = 0
    token: str | None = None
    init_data: str | None = None


class CreateTopUpPaymentRequest(BaseModel):
    payment_method: str
    amount: float
    token: str | None = None
    user_id: int | None = None  # ignored; identity from token only
    init_data: str | None = None


class CreateLteTopUpPaymentRequest(BaseModel):
    payment_method: str
    key_id: int
    package_id: int
    token: str | None = None
    user_id: int | None = None  # ignored; identity from token only
    init_data: str | None = None


class ApplyPromoRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    promo_code: str
    plan_id: int | None = None
    price: float | None = None
    token: str | None = None
    init_data: str | None = None


class RenameKeyRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    new_name: str
    token: str | None = None


class DeleteAllDevicesRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    host_name: str | None = None
    token: str | None = None


class SearchKeysRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    query: str
    token: str | None = None


class CheckPaymentRequest(BaseModel):
    payment_id: str
    token: str | None = None
    init_data: str | None = None


class VerifyPlategaPaymentRequest(BaseModel):
    token: str | None = None
    init_data: str | None = None


class KeyActionRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    host_name: str | None = None
    token: str | None = None
    init_data: str | None = None


class DeleteDeviceRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    device_id: str
    host_name: str | None = None
    token: str | None = None
    init_data: str | None = None


class CommentRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    comment: str
    token: str | None = None
    init_data: str | None = None


class GiftActivateRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    gift_code: str
    token: str | None = None
    init_data: str | None = None


class PendingActionCompleteRequest(BaseModel):
    pending_token: str
    token: str | None = None
    init_data: str | None = None


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "SupportStatusRequest",
    "SupportTicketCreateRequest",
    "SupportMessageSendRequest",
    "SupportTicketRequest",
    "PaymentMethodsRequest",
    "TokenRequest",
    "TelegramDirectAuthRequest",
    "EmailAuthRequest",
    "EmailVerifyRequest",
    "EmailResendRequest",
    "PasswordResetRequest",
    "PasswordResetCheckRequest",
    "PasswordResetVerifyRequest",
    "SyncTgRequest",
    "DeviceTiersRequest",
    "CreatePaymentRequest",
    "CreateTopUpPaymentRequest",
    "CreateLteTopUpPaymentRequest",
    "ApplyPromoRequest",
    "RenameKeyRequest",
    "DeleteAllDevicesRequest",
    "SearchKeysRequest",
    "CheckPaymentRequest",
    "VerifyPlategaPaymentRequest",
    "KeyActionRequest",
    "DeleteDeviceRequest",
    "CommentRequest",
    "GiftActivateRequest",
    "PendingActionCompleteRequest",
]
