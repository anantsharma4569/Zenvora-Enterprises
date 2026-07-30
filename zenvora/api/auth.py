import time

import frappe
from frappe import _
from frappe.core.doctype.user.user import User

from zenvora.jwt_utils import decode_token, issue_tokens, revoke


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
	user.save(ignore_permissions=True)
	frappe.db.commit()

	return _token_response(issue_tokens(user.name), user.name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(usr, pwd):
	result = User.find_by_credentials(usr, pwd)

	if not result or not result.is_authenticated:
		frappe.local.response["http_status_code"] = 401
		return {"success": False, "message": _("Incorrect email or password")}

	if not result.enabled:
		frappe.local.response["http_status_code"] = 403
		return {"success": False, "message": _("Your account has been disabled")}

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
	auth_header = frappe.get_request_header("Authorization") or ""
	if auth_header.lower().startswith("bearer "):
		_try_revoke(auth_header.split(" ", 1)[1].strip(), "access")

	if refresh_token:
		_try_revoke(refresh_token, "refresh")

	return {"success": True, "message": _("Logged out successfully")}


@frappe.whitelist()
def me():
	return _user_payload(frappe.session.user)
