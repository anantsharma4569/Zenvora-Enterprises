import frappe

from zenvora.jwt_utils import decode_token


def validate_bearer_token():
	# A distinct header name (not `Authorization`) keeps this app's JWT out of
	# Frappe core's own OAuth2/API-key handling in frappe.auth.validate_auth,
	# which only runs against the `Authorization` header.
	token = (frappe.get_request_header("X-Zenvora-Token") or "").strip()
	if not token:
		return

	try:
		payload = decode_token(token, expected_type="access")
	except frappe.AuthenticationError:
		return

	user = payload.get("sub")
	if user and frappe.db.exists("User", user) and frappe.db.get_value("User", user, "enabled"):
		# frappe.set_user() resets frappe.local.form_dict as a side effect
		# (see frappe/__init__.py). By this point make_form_dict() has already
		# parsed the request body, so save and restore it around the user
		# switch — otherwise every authenticated POST with a body arrives at
		# the whitelisted method with an empty form_dict.
		form_dict = frappe.local.form_dict
		frappe.set_user(user)
		frappe.local.form_dict = form_dict
