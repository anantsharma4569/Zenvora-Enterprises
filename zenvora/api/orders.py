import frappe
from frappe import _
from frappe.utils import add_days, flt, now_datetime, today

from zenvora.inventory_utils import (
	ZENVORA_WAREHOUSE,
	get_available_qty,
	get_variant_item_code,
	resolve_variant_to_product_size,
)
from zenvora.website_user_utils import ZENVORA_COMPANY, get_or_create_customer_for_user

ORDER_LIST_FIELDS = ["name", "transaction_date", "grand_total", "currency", "status", "per_billed"]

STATUS_BUCKETS = {
	"to_deliver": ["To Deliver", "To Deliver and Bill"],
	"delivered": ["Completed"],
	"cancelled": ["Cancelled"],
}


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def _get_gst_template():
	return frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": ZENVORA_COMPANY, "title": "GST 5%"}, "name"
	)


def _get_tax_rows(template_name):
	"""Setting Sales Order.taxes_and_charges alone does not populate the
	`taxes` child table server-side (that only happens client-side, via the
	field's on_change handler in the desk form) — it has to be fetched and
	assigned explicitly."""
	if not template_name:
		return []
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	return get_taxes_and_charges("Sales Taxes and Charges Template", template_name)


def _resolve_order_item(item):
	"""items[i].item_code is the Product name — resolve it (+ the chosen
	size) to the actual stock-carrying size variant, and fail fast with a
	clear message if there isn't enough of it, rather than letting an
	oversold Sales Order get created.

	`rate` is deliberately NOT taken from the client — this is the price a
	customer actually pays, so it's always looked up from the variant's own
	Item.standard_rate (kept in sync with Product.price by
	Product.sync_item/ensure_size_variants). Trusting a client-supplied rate
	here would let anyone submit an order at whatever price they choose."""
	product = item["item_code"]
	size = item.get("size")
	qty = item["qty"]

	variant_item_code = get_variant_item_code(product, size)
	available = get_available_qty(variant_item_code)
	if qty > available:
		if available <= 0:
			frappe.throw(_("{0} is out of stock in size {1}").format(product, size))
		frappe.throw(_("Only {0} left of {1} in size {2}").format(available, product, size))

	rate = frappe.db.get_value("Item", variant_item_code, "standard_rate")

	return {
		"item_code": variant_item_code,
		"qty": qty,
		"rate": rate,
		"warehouse": ZENVORA_WAREHOUSE,
	}


@frappe.whitelist(methods=["POST"])
def create_sales_order(items, address_name=None, coupon_code=None):
	"""Create a Draft Sales Order for the logged-in customer from their cart.
	items: [{item_code, qty, rate}, ...]
	"""
	_require_login()

	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not items:
		frappe.throw(_("Your bag is empty"))

	customer = get_or_create_customer_for_user(frappe.session.user)
	gst_template = _get_gst_template()

	so_dict = {
		"doctype": "Sales Order",
		"company": ZENVORA_COMPANY,
		"customer": customer,
		"delivery_date": add_days(today(), 7),
		"items": [_resolve_order_item(item) for item in items],
		"taxes_and_charges": gst_template,
		"taxes": _get_tax_rows(gst_template),
	}
	if coupon_code:
		from zenvora.api.coupons import validate_coupon

		validate_coupon(coupon_code)  # raises if invalid — fail before creating anything
		# Sales Order.coupon_code links to the Coupon Code doc's *name*, not
		# its human-typed `coupon_code` field — those are different values.
		so_dict["coupon_code"] = frappe.db.get_value("Coupon Code", {"coupon_code": coupon_code}, "name")
	if address_name:
		from zenvora.api.addresses import _assert_owns_address

		_assert_owns_address(address_name)
		so_dict["customer_address"] = address_name
		so_dict["shipping_address_name"] = address_name

	so = frappe.get_doc(so_dict)

	# See the identical note in _finalize_payment: ERPNext's pricing/tax
	# population loads Item/Account docs and checks their own permissions
	# directly, unreachable from any flag on this Sales Order itself.
	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		so.insert()
	finally:
		frappe.set_user(current_user)
	frappe.db.commit()

	return _order_summary(so)


def _order_summary(so):
	return {
		"name": so.name,
		"grand_total": so.grand_total,
		"currency": so.currency,
		"total": so.total,
		"total_taxes_and_charges": so.total_taxes_and_charges,
		"discount_amount": so.discount_amount,
	}


@frappe.whitelist()
def fetch_orders(status=None, limit_start=0, limit_page_length=10):
	"""Website Users only ever see their own orders — Frappe's User
	Permission engine scopes this to the Customer linked to their account."""
	_require_login()

	filters = {}
	if status and status != "all":
		if status == "returned":
			so_names = frappe.get_all("Return Request", filters={"status": "Refunded"}, pluck="sales_order")
			filters["name"] = ["in", so_names or [""]]
		elif status in STATUS_BUCKETS:
			filters["status"] = ["in", STATUS_BUCKETS[status]]

	orders = frappe.get_list(
		"Sales Order",
		filters=filters,
		fields=ORDER_LIST_FIELDS,
		order_by="creation desc",
		limit_start=int(limit_start),
		limit_page_length=int(limit_page_length),
	)
	total_count = len(frappe.get_list("Sales Order", filters=filters, pluck="name"))

	return {"orders": orders, "total_count": total_count}


@frappe.whitelist()
def get_order_detail(name):
	"""Richer than a plain Sales Order doc read: bundles the linked payment
	transaction, tracking timestamps, and shipping address in one call."""
	_require_login()

	so = frappe.get_doc("Sales Order", name)
	# frappe.get_doc() alone does NOT check permissions (that's a separate
	# step frappe.client.get performs on top of it) — without this, any
	# logged-in user could read any other customer's order by name.
	so.check_permission("read")

	txn = frappe.get_all(
		"Razorpay Transaction",
		filters={"sales_order": name},
		fields=["razorpay_payment_id", "method", "status"],
		order_by="creation desc",
		limit_page_length=1,
	)
	address = None
	if so.shipping_address_name:
		address = frappe.get_doc("Address", so.shipping_address_name).as_dict()

	return_request = frappe.get_all(
		"Return Request", filters={"sales_order": name}, fields=["name", "status"], limit_page_length=1
	)

	return {
		"name": so.name,
		"status": so.status,
		"transaction_date": so.transaction_date,
		"currency": so.currency,
		"items": [
			{"item_code": i.item_code, "item_name": i.item_name, "qty": i.qty, "rate": i.rate, "amount": i.amount}
			for i in so.items
		],
		"total": so.total,
		"total_taxes_and_charges": so.total_taxes_and_charges,
		"discount_amount": so.discount_amount,
		"grand_total": so.grand_total,
		"tracking": {
			"confirmed_at": so.get("confirmed_at"),
			"packed_at": so.get("packed_at"),
			"shipped_at": so.get("shipped_at"),
			"out_for_delivery_at": so.get("out_for_delivery_at"),
			"delivered_at": so.get("delivered_at"),
		},
		"payment": txn[0] if txn else None,
		"address": address,
		"return_request": return_request[0] if return_request else None,
	}


@frappe.whitelist(methods=["POST"])
def buy_again(sales_order):
	"""Re-add a past order's items to the current cart."""
	_require_login()
	from zenvora.api.cart import add_to_cart

	so = frappe.get_doc("Sales Order", sales_order)
	so.check_permission("read")
	for item in so.items:
		product, size = resolve_variant_to_product_size(item.item_code)
		add_to_cart(product, qty=item.qty, size=size)
	return {"success": True}


@frappe.whitelist(methods=["POST"])
def request_return(sales_order, reason=None):
	_require_login()

	so = frappe.get_doc("Sales Order", sales_order)
	so.check_permission("read")
	if so.status != "Completed":
		frappe.throw(_("Only delivered orders can be returned"))
	if frappe.db.exists("Return Request", {"sales_order": sales_order}):
		frappe.throw(_("A return has already been requested for this order"))

	website_user = frappe.db.get_value("Website User", frappe.session.user, "name")
	frappe.get_doc(
		{
			"doctype": "Return Request",
			"sales_order": sales_order,
			"website_user": website_user,
			"reason": reason,
			"requested_at": now_datetime(),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def list_returns():
	_require_login()
	# frappe.get_all bypasses doctype permissions entirely (unlike get_list) —
	# Return Request has no owner-based scoping, so this filter is the only
	# thing standing between "my returns" and "everyone's returns".
	return frappe.get_all(
		"Return Request",
		filters={"website_user": frappe.session.user},
		fields=["name", "sales_order", "status", "reason", "requested_at", "refund_amount"],
		order_by="creation desc",
	)
