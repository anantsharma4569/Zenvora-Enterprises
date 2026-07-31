import frappe
from frappe.utils import now_datetime


def expire_stale_otps():
	"""Mark Pending OTPs past their expiry as Expired. Runs hourly."""
	stale = frappe.get_all(
		"OTP Verification",
		filters={"status": "Pending", "expires_at": ["<", now_datetime()]},
		pluck="name",
	)
	for name in stale:
		frappe.db.set_value("OTP Verification", name, "status", "Expired")

	if stale:
		frappe.db.commit()
