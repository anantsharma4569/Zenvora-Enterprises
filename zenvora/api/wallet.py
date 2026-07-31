import frappe
from frappe import _
from frappe.utils import flt

from zenvora.website_user_utils import get_or_create_website_user


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


@frappe.whitelist()
def get_wallet():
	"""Read-only for now — there's no customer-facing funding flow yet.
	Credits/debits happen server-side (see Return Request refunds) or via
	Desk (System Manager creating a Wallet Transaction directly); either way
	Wallet Transaction.before_insert keeps the balance consistent."""
	_require_login()

	website_user = get_or_create_website_user(frappe.session.user)
	transactions = frappe.get_all(
		"Wallet Transaction",
		filters={"website_user": website_user.name},
		fields=["name", "type", "amount", "balance_after", "reference", "remarks", "creation"],
		order_by="creation desc",
	)
	return {"balance": flt(website_user.wallet_balance), "transactions": transactions}
