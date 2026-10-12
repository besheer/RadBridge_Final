import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

OHIF_DOCTOR_IDENTITY_MAX_AGE = int(
    os.getenv("OHIF_DOCTOR_IDENTITY_MAX_AGE", "300")
)

def make_serializer(secret):
    return URLSafeTimedSerializer(
        secret_key=secret,
        salt="radbridge-ohif-doctor-identity-v1"
    )

def create_identity(secret, user_id, username, full_name, role, order_id):
    payload = {
        "purpose": "OHIF_REPORTING",
        "user_id": int(user_id),
        "username": str(username or ""),
        "full_name": str(full_name or username or ""),
        "role": str(role or "").upper(),
        "order_id": int(order_id),
    }
    return make_serializer(secret).dumps(payload)

def verify_identity(secret, token, order_id=None):
    if not token:
        return None, "DOCTOR_IDENTITY_REQUIRED"

    try:
        payload = make_serializer(secret).loads(
            token,
            max_age=OHIF_DOCTOR_IDENTITY_MAX_AGE
        )
    except SignatureExpired:
        return None, "DOCTOR_IDENTITY_EXPIRED"
    except BadSignature:
        return None, "DOCTOR_IDENTITY_INVALID"

    if payload.get("purpose") != "OHIF_REPORTING":
        return None, "DOCTOR_IDENTITY_INVALID"

    if order_id is not None:
        try:
            if int(payload.get("order_id")) != int(order_id):
                return None, "DOCTOR_IDENTITY_ORDER_MISMATCH"
        except Exception:
            return None, "DOCTOR_IDENTITY_INVALID"

    return payload, None
