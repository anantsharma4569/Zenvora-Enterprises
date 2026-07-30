import frappe

from zenvora.jwt_utils import decode_token


def validate_bearer_token():
	auth_header = frappe.get_request_header("Authorization")
	if not auth_header or not auth_header.lower().startswith("bearer "):
		return

	token = auth_header.split(" ", 1)[1].strip()
	if not token:
		return

	try:
		payload = decode_token(token, expected_type="access")
	except frappe.AuthenticationError:
		return

	user = payload.get("sub")
	if user and frappe.db.exists("User", user) and frappe.db.get_value("User", user, "enabled"):
		frappe.set_user(user)
