import time

import frappe
from frappe import _
from frappe.core.doctype.user.user import User
from frappe.utils import now_datetime

from zenvora.jwt_utils import decode_token, issue_tokens, revoke, revoke_all_refresh_tokens
from zenvora.website_user_utils import get_or_create_website_user


def _user_payload(user):
	return {
		"email": user,
		"full_name": frappe.db.get_value("User", user, "full_name"),
		"phone": frappe.db.get_value("User", user, "phone"),
		"user_image": frappe.db.get_value("User", user, "user_image"),
	}


def _token_response(tokens, user):
	return {
		"success": True,
		"access_token": tokens["access_token"],
		"refresh_token": tokens["refresh_token"],
		"expires_in": tokens["expires_in"],
		"user": _user_payload(user),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def register(email, full_name, password, phone=None):
	email = email.strip().lower()
	if frappe.db.exists("User", email):
		frappe.local.response["http_status_code"] = 409
		return {"success": False, "message": _("An account with this email already exists")}

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": full_name,
			"phone": phone,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"enabled": 1,
		}
	)
	user.insert(ignore_permissions=True)
	user.new_password = password
	user.add_roles("Website User")

	# The "All" and "Website User" roles both have desk_access=1 on this site
	# (a pre-existing, site-wide misconfiguration outside Zenvora's own
	# control — not something to fix here). That makes Frappe's own
	# user_type auto-correction (User.set_system_user, keyed off
	# has_desk_access()) force every saved User to "System User", overriding
	# whatever was set above. Force it back directly via a raw DB write,
	# bypassing that recompute entirely, so storefront customers end up
	# correctly typed without touching the shared role config.
	frappe.db.set_value("User", user.name, "user_type", "Website User")

	frappe.get_doc({"doctype": "Website User", "user": user.name}).insert(ignore_permissions=True)
	frappe.db.commit()

	return _token_response(issue_tokens(user.name), user.name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(email=None, password=None, usr=None, pwd=None, username=None):
	email = email or usr or username
	password = password or pwd

	if not email or not password:
		frappe.local.response["http_status_code"] = 400
		return {"success": False, "message": _("Email and password are required")}

	result = User.find_by_credentials(email, password)

	if not result or not result.is_authenticated:
		frappe.local.response["http_status_code"] = 401
		return {"success": False, "message": _("Incorrect email or password")}

	if not result.enabled:
		frappe.local.response["http_status_code"] = 403
		return {"success": False, "message": _("Your account has been disabled")}

	website_user = get_or_create_website_user(result.name)
	website_user.last_login_at = now_datetime()
	website_user.last_ip_address = frappe.local.request_ip
	website_user.save(ignore_permissions=True)
	frappe.db.commit()

	return _token_response(issue_tokens(result.name), result.name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def refresh(refresh_token):
	payload = decode_token(refresh_token, expected_type="refresh")
	user = payload["sub"]

	if not frappe.db.get_value("User", user, "enabled"):
		frappe.local.response["http_status_code"] = 403
		return {"success": False, "message": _("Your account has been disabled")}

	tokens = issue_tokens(user)
	return {
		"success": True,
		"access_token": tokens["access_token"],
		"refresh_token": tokens["refresh_token"],
		"expires_in": tokens["expires_in"],
	}


def _try_revoke(token, expected_type):
	try:
		payload = decode_token(token, expected_type=expected_type)
		ttl = payload["exp"] - int(time.time())
		revoke(payload["jti"], ttl)
	except frappe.AuthenticationError:
		pass


@frappe.whitelist(allow_guest=True, methods=["POST"])
def logout(refresh_token=None):
	access_token = (frappe.get_request_header("X-Zenvora-Token") or "").strip()
	if access_token:
		_try_revoke(access_token, "access")

	if refresh_token:
		_try_revoke(refresh_token, "refresh")

	# Belt-and-suspenders: revoke every refresh token we've issued this user,
	# not just the one (if any) the client sent back — a client that
	# loses/omits it would otherwise leave a valid session for up to 7 days.
	if frappe.session.user != "Guest":
		revoke_all_refresh_tokens(frappe.session.user)

	return {"success": True, "message": _("Logged out successfully")}


@frappe.whitelist()
def me():
	return _user_payload(frappe.session.user)
