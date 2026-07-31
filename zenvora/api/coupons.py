import frappe
from frappe import _
from frappe.utils import getdate, today


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def _is_currently_valid(coupon):
	today_date = getdate(today())
	if coupon.valid_from and getdate(coupon.valid_from) > today_date:
		return False
	if coupon.valid_upto and getdate(coupon.valid_upto) < today_date:
		return False
	if coupon.maximum_use and coupon.used >= coupon.maximum_use:
		return False
	return True


@frappe.whitelist()
def list_active_coupons():
	"""Public, general-purpose coupons only — ones targeted at a specific
	Customer (Coupon Code.customer set) aren't advertised here."""
	_require_login()

	coupons = frappe.get_all(
		"Coupon Code",
		filters={"customer": ["in", ["", None]]},
		fields=[
			"name",
			"coupon_code",
			"coupon_name",
			"description",
			"maximum_use",
			"used",
			"valid_from",
			"valid_upto",
			"pricing_rule",
		],
	)
	return [c for c in coupons if _is_currently_valid(c)]


@frappe.whitelist(methods=["POST"])
def validate_coupon(coupon_code):
	"""Check a code is usable and return its discount for display before checkout."""
	_require_login()

	name = frappe.db.exists("Coupon Code", {"coupon_code": coupon_code})
	if not name:
		frappe.throw(_("Invalid coupon code"))

	coupon = frappe.get_doc("Coupon Code", name)

	if coupon.customer:
		my_customer = frappe.db.get_value("Website User", frappe.session.user, "customer")
		if coupon.customer != my_customer:
			frappe.throw(_("Invalid coupon code"))

	if not _is_currently_valid(coupon):
		frappe.throw(_("This coupon isn't valid right now"))

	pricing_rule = frappe.get_doc("Pricing Rule", coupon.pricing_rule)
	return {
		"coupon_code": coupon.coupon_code,
		"description": coupon.description,
		"discount_percentage": pricing_rule.discount_percentage,
		"discount_amount": pricing_rule.discount_amount,
	}
