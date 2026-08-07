import re

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

from zenvora.api.auth import _token_response
from zenvora.api.otp import (
	OTP_EXPIRY_MINUTES,
	TEST_SMS_NUMBER,
	_generate_code,
	_send_email_otp,
	_send_sms_otp,
)
from zenvora.jwt_utils import issue_tokens
from zenvora.website_user_utils import get_or_create_website_user

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Passwordless checkout for a logged-out shopper: verify a phone or email via
# OTP instead of making them register with a password first. Verifying
# successfully logs them in — same account model register() creates, just
# without the password step (they can add one later from Account settings).
# Cart/wishlist/orders need no changes at all: once this issues tokens, the
# shopper IS a normal logged-in account as far as every other endpoint cares.


def _looks_like_email(recipient):
	return bool(EMAIL_RE.match(recipient or ""))


@frappe.whitelist(allow_guest=True, methods=["POST"])
def request_checkout_otp(otp_channel, recipient):
	if otp_channel not in ("SMS", "Email"):
		frappe.throw(_("Invalid OTP channel"))

	if otp_channel == "Email" and not _looks_like_email(recipient):
		frappe.throw(_("Enter a valid email address"))
	if otp_channel == "SMS" and recipient != TEST_SMS_NUMBER:
		frappe.throw(
			_(
				"SMS delivery isn't configured yet. Only the test number {0} works until a real gateway is connected."
			).format(TEST_SMS_NUMBER)
		)

	# Nobody has an account yet at this point, so these all share the
	# built-in "Guest" User record — `recipient` (not `user`) is what
	# distinguishes one shopper's pending code from another's here.
	for name in frappe.get_all(
		"OTP Verification",
		filters={"user": "Guest", "otp_channel": otp_channel, "recipient": recipient, "status": "Pending"},
		pluck="name",
	):
		frappe.db.set_value("OTP Verification", name, "status", "Expired")

	code = _generate_code()
	frappe.get_doc(
		{
			"doctype": "OTP Verification",
			"user": "Guest",
			"otp_channel": otp_channel,
			"recipient": recipient,
			"otp_code": code,
			"status": "Pending",
			"expires_at": add_to_date(now_datetime(), minutes=OTP_EXPIRY_MINUTES),
			"ip_address": frappe.local.request_ip,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()

	if otp_channel == "Email":
		_send_email_otp(recipient, code)
	else:
		_send_sms_otp(recipient, code)

	return {"success": True, "message": _("Verification code sent"), "expires_in": OTP_EXPIRY_MINUTES * 60}


def _find_or_create_guest_user(otp_channel, recipient):
	"""Resolve the just-verified recipient to a real User, creating one on
	first checkout. Frappe's User is fundamentally email-keyed, so a
	phone-only shopper gets a synthetic, unroutable placeholder address
	purely so a User record can exist — their real, verified contact is the
	phone field, and `phone_verified` (not the placeholder email) is what
	matters."""
	if otp_channel == "Email":
		email = recipient.strip().lower()
	else:
		digits = re.sub(r"\D", "", recipient)
		email = f"phone-{digits}@guest.zenvora.local"

	if frappe.db.exists("User", email):
		return email

	user_dict = {
		"doctype": "User",
		"email": email,
		"first_name": "Guest",
		"user_type": "Website User",
		"send_welcome_email": 0,
		"enabled": 1,
	}
	if otp_channel == "SMS":
		user_dict["phone"] = recipient

	user = frappe.get_doc(user_dict)
	user.insert(ignore_permissions=True)
	# Same desk_access workaround as register() — see the comment there for why.
	frappe.db.set_value("User", user.name, "user_type", "Website User")

	frappe.get_doc({"doctype": "Website User", "user": user.name}).insert(ignore_permissions=True)
	return email


@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_checkout_otp(otp_channel, recipient, otp_code):
	name = frappe.db.get_value(
		"OTP Verification",
		{"user": "Guest", "otp_channel": otp_channel, "recipient": recipient, "status": "Pending"},
		"name",
		order_by="creation desc",
	)
	if not name:
		frappe.throw(_("No pending verification code for this recipient. Request a new one."))

	otp = frappe.get_doc("OTP Verification", name)

	if now_datetime() > otp.expires_at:
		otp.status = "Expired"
		otp.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("This code has expired. Request a new one."))

	if otp.otp_code != otp_code:
		otp.attempts = cint(otp.attempts) + 1
		if otp.attempts >= cint(otp.max_attempts):
			otp.status = "Failed"
		otp.save(ignore_permissions=True)
		frappe.db.commit()
		if otp.status == "Failed":
			frappe.throw(_("Too many incorrect attempts. Request a new code."))
		frappe.throw(_("Incorrect code"))

	otp.status = "Verified"
	otp.verified_at = now_datetime()
	otp.save(ignore_permissions=True)

	email = _find_or_create_guest_user(otp_channel, recipient)

	website_user = get_or_create_website_user(email)
	if otp_channel == "Email":
		website_user.email_verified = 1
	else:
		website_user.phone_verified = 1
	website_user.last_login_at = now_datetime()
	website_user.last_ip_address = frappe.local.request_ip
	website_user.save(ignore_permissions=True)

	frappe.db.commit()

	return _token_response(issue_tokens(email), email)
