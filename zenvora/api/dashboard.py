import frappe
from frappe import _
from frappe.utils import flt

from zenvora.website_user_utils import get_or_create_website_user


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


@frappe.whitelist()
def get_dashboard_summary():
	_require_login()

	website_user = get_or_create_website_user(frappe.session.user)

	# len() over get_list (not frappe.db.count/get_all) because this must stay
	# scoped to the caller's own orders via the User Permission engine.
	total_orders = len(frappe.get_list("Sales Order", pluck="name"))
	wishlist_count = frappe.db.count("Wishlist Item", {"user": frappe.session.user})
	address_count = len(
		frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": "Customer", "link_name": website_user.customer, "parenttype": "Address"},
		)
	) if website_user.customer else 0
	return_count = frappe.db.count("Return Request", {"website_user": website_user.name})

	from zenvora.api.coupons import list_active_coupons

	coupons = list_active_coupons()

	recent_orders = frappe.get_list(
		"Sales Order",
		fields=["name", "transaction_date", "grand_total", "currency", "status"],
		order_by="creation desc",
		limit_page_length=5,
	)

	return {
		"full_name": frappe.db.get_value("User", frappe.session.user, "full_name"),
		"total_orders": total_orders,
		"wishlist_count": wishlist_count,
		"address_count": address_count,
		"return_count": return_count,
		"coupon_count": len(coupons),
		"wallet_balance": flt(website_user.wallet_balance),
		"recent_orders": recent_orders,
	}
