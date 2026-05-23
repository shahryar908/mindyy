import secrets
from uuid import UUID

from redis_client import redis_client


OTP_TTL_SECONDS = 10 * 60          # OTP valid for 10 min
RESEND_COOLDOWN_SECONDS = 60       # 1 min between resends
MAX_ATTEMPTS = 5


def _otp_key(user_id: UUID) -> str:
    return f"otp:{user_id}"


def _attempts_key(user_id: UUID) -> str:
    return f"otp_attempts:{user_id}"


def _cooldown_key(user_id: UUID) -> str:
    return f"otp_cooldown:{user_id}"


def generate_otp(user_id: UUID) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    pipe = redis_client.pipeline()
    pipe.set(_otp_key(user_id), code, ex=OTP_TTL_SECONDS)
    pipe.delete(_attempts_key(user_id))
    pipe.set(_cooldown_key(user_id), "1", ex=RESEND_COOLDOWN_SECONDS)
    pipe.execute()
    return code


def can_resend(user_id: UUID) -> bool:
    return not redis_client.exists(_cooldown_key(user_id))


def verify_otp(user_id: UUID, code: str) -> bool:
    attempts = redis_client.incr(_attempts_key(user_id))
    if attempts == 1:
        redis_client.expire(_attempts_key(user_id), OTP_TTL_SECONDS)
    if attempts > MAX_ATTEMPTS:
        redis_client.delete(_otp_key(user_id))
        return False

    stored = redis_client.get(_otp_key(user_id))
    if stored is None or stored != code:
        return False

    redis_client.delete(_otp_key(user_id))
    redis_client.delete(_attempts_key(user_id))
    return True
