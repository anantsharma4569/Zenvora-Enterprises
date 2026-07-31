import secrets

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

from zenvora.website_user_utils import get_or_create_website_user

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 5

# No SMS gateway (Twilio, MSG91, etc.) is configured yet. Until one is wired
# up, SMS OTPs only "send" (log, rather than actually dispatch) for this one
# hardcoded number, so the full request/verify flow can be tested end-to-end.
TEST_SMS_NUMBER = "+911234567890"


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def _otp_logger():
	# The site's default log level can be higher than INFO (e.g. ERROR), which
	# would silently drop these mock-channel notices. Force this logger's own
	# level so they're always visible in logs/zenvora_otp.log.
	logger = frappe.logger("zenvora_otp")
	logger.setLevel("INFO")
	return logger


def _generate_code():
	return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


def _send_email_otp(recipient, code):
	try:
		frappe.sendmail(
			recipients=[recipient],
			subject=_("Your Zenvora verification code"),
			message=_("Your verification code is: <b>{0}</b>. It expires in {1} minutes.").format(
				code, OTP_EXPIRY_MINUTES
			),
			now=True,
		)
	except frappe.OutgoingEmailError:
		# No default outgoing Email Account is configured on this site yet.
		# Log instead of failing so the flow can still be tested end-to-end;
		# configure one under Tools > Email Account before going live.
		_otp_logger().info(f"[MOCK EMAIL] OTP for {recipient}: {code}")


def _send_sms_otp(recipient, code):
	# Mock channel: no gateway to call, so just log it for manual testing.
	# Caller has already checked recipient == TEST_SMS_NUMBER before any
	# OTP record was created — see request_otp.
	_otp_logger().info(f"[MOCK SMS] OTP for {recipient}: {code}")


@frappe.whitelist(methods=["POST"])
def request_otp(otp_channel, recipient):
	_require_login()

	if otp_channel not in ("SMS", "Email"):
		frappe.throw(_("Invalid OTP channel"))

	# Validate deliverability *before* creating any OTP record, so a rejected
	# recipient never leaves a stray Pending row behind.
	if otp_channel == "SMS" and recipient != TEST_SMS_NUMBER:
		frappe.throw(
			_(
				"SMS delivery isn't configured yet. Only the test number {0} works until a real gateway is connected."
			).format(TEST_SMS_NUMBER)
		)

	user = frappe.session.user

	# Only the latest requested code for a given user/channel/recipient stays valid.
	for name in frappe.get_all(
		"OTP Verification",
		filters={"user": user, "otp_channel": otp_channel, "recipient": recipient, "status": "Pending"},
		pluck="name",
	):
		frappe.db.set_value("OTP Verification", name, "status", "Expired")

	code = _generate_code()
	otp = frappe.get_doc(
		{
			"doctype": "OTP Verification",
			"user": user,
			"otp_channel": otp_channel,
			"recipient": recipient,
			"otp_code": code,
			"status": "Pending",
			"expires_at": add_to_date(now_datetime(), minutes=OTP_EXPIRY_MINUTES),
			"ip_address": frappe.local.request_ip,
		}
	)
	otp.insert(ignore_permissions=True)
	frappe.db.commit()

	if otp_channel == "Email":
		_send_email_otp(recipient, code)
	else:
		_send_sms_otp(recipient, code)

	return {"success": True, "message": _("Verification code sent"), "expires_in": OTP_EXPIRY_MINUTES * 60}


@frappe.whitelist(methods=["POST"])
def verify_otp(otp_channel, recipient, otp_code):
	_require_login()

	user = frappe.session.user
	name = frappe.db.get_value(
		"OTP Verification",
		{"user": user, "otp_channel": otp_channel, "recipient": recipient, "status": "Pending"},
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

	website_user = get_or_create_website_user(user)
	if otp_channel == "Email":
		website_user.email_verified = 1
	else:
		website_user.phone_verified = 1
	website_user.save(ignore_permissions=True)

	frappe.db.commit()
	return {"success": True, "message": _("Verified successfully")}
