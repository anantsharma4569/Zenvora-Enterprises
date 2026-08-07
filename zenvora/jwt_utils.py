import secrets
import time

import jwt

import frappe
from frappe.utils import cint

ACCESS_TOKEN_EXPIRY_SECONDS = 60 * 60  # 1 hour
REFRESH_TOKEN_EXPIRY_SECONDS = 60 * 60 * 24 * 7  # 7 days
ALGORITHM = "HS256"


def _get_secret():
	secret = frappe.conf.get("jwt_secret")
	if not secret:
		frappe.throw(
			f"JWT secret is not configured. Run: bench --site {frappe.local.site} "
			"set-config jwt_secret <random-value>"
		)
	return secret


def _access_expiry():
	return cint(frappe.conf.get("jwt_access_expiry_seconds")) or ACCESS_TOKEN_EXPIRY_SECONDS


def _refresh_expiry():
	return cint(frappe.conf.get("jwt_refresh_expiry_seconds")) or REFRESH_TOKEN_EXPIRY_SECONDS


def issue_tokens(user):
	secret = _get_secret()
	# frappe.utils.now_datetime() returns a naive datetime in the SITE timezone;
	# .timestamp() on that misreads it as UTC, offsetting iat/exp by the site's
	# UTC offset. time.time() is unambiguous.
	now_ts = int(time.time())
	access_exp = _access_expiry()
	refresh_exp = _refresh_expiry()

	access_payload = {
		"sub": user,
		"type": "access",
		"jti": secrets.token_urlsafe(16),
		"iat": now_ts,
		"exp": now_ts + access_exp,
	}
	refresh_payload = {
		"sub": user,
		"type": "refresh",
		"jti": secrets.token_urlsafe(16),
		"iat": now_ts,
		"exp": now_ts + refresh_exp,
	}

	# Tracked so a logout call that can't/doesn't hand back this exact refresh
	# token (lost/omitted by a buggy or malicious client) can still be revoked
	# via revoke_all_refresh_tokens() below, instead of staying valid for the
	# full 7-day lifetime after the user thinks they've logged out.
	frappe.cache().sadd(_active_refresh_key(user), refresh_payload["jti"])
	frappe.cache().expire_key(_active_refresh_key(user), refresh_exp)

	return {
		"access_token": jwt.encode(access_payload, secret, algorithm=ALGORITHM),
		"refresh_token": jwt.encode(refresh_payload, secret, algorithm=ALGORITHM),
		"expires_in": access_exp,
	}


def decode_token(token, expected_type):
	secret = _get_secret()
	try:
		payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
	except jwt.ExpiredSignatureError:
		frappe.throw("Token has expired", frappe.AuthenticationError)
	except jwt.InvalidTokenError:
		frappe.throw("Invalid token", frappe.AuthenticationError)

	if payload.get("type") != expected_type:
		frappe.throw("Invalid token type", frappe.AuthenticationError)

	if is_revoked(payload["jti"]):
		frappe.throw("Token has been revoked", frappe.AuthenticationError)

	return payload


def revoke(jti, ttl_seconds):
	if ttl_seconds and ttl_seconds > 0:
		frappe.cache().set_value(f"zenvora_jwt_revoked:{jti}", "1", expires_in_sec=ttl_seconds)


def is_revoked(jti):
	return bool(frappe.cache().exists(f"zenvora_jwt_revoked:{jti}"))


def _active_refresh_key(user):
	return f"zenvora_jwt_active_refresh:{user}"


def revoke_all_refresh_tokens(user):
	"""Best-effort logout-everywhere: revoke every refresh token issued to
	this user that we still have a record of, not just the one (if any) the
	client hands back on logout."""
	jtis = frappe.cache().smembers(_active_refresh_key(user)) or set()
	for jti in jtis:
		jti = jti.decode() if isinstance(jti, bytes) else jti
		revoke(jti, REFRESH_TOKEN_EXPIRY_SECONDS)
	frappe.cache().delete_key(_active_refresh_key(user))
