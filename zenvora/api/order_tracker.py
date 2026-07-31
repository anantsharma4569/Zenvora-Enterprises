import frappe
from frappe import _

from zenvora.website_user_utils import get_or_create_website_user

# The 4-step tracker shown on each order card.
STEPS = ["Order Placed", "Processing", "Shipped", "Delivered"]


def _display_status(so, delivery_note):
	if so.docstatus == 2 or so.status == "Cancelled":
		return "Cancelled"
	if so.per_delivered == 100 or so.status == "Completed":
		return "Delivered"
	if (so.per_delivered and so.per_delivered > 0) or (delivery_note and delivery_note.tracking_no):
		return "Shipped"
	return "In Progress"


def _progress_step(so, display_status):
	if display_status == "Cancelled":
		return 0
	if display_status == "Delivered":
		return 4
	if display_status == "Shipped":
		return 3
	# "In Progress": still just placed (draft) vs. confirmed/being processed
	return 2 if so.docstatus == 1 else 1


def _get_items(so_name):
	return frappe.get_all(
		"Sales Order Item",
		filters={"parent": so_name},
		fields=["item_code", "item_name", "qty", "rate", "amount", "image"],
		order_by="idx asc",
	)


def _get_delivery_note(so_name):
	rows = frappe.get_all(
		"Delivery Note Item",
		filters={"against_sales_order": so_name, "docstatus": ["!=", 2]},
		fields=["parent"],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return None

	return frappe.get_value(
		"Delivery Note",
		rows[0].parent,
		["name", "tracking_no", "tracking_url", "courier_name"],
		as_dict=True,
	)


def _get_sales_invoice(so_name):
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"sales_order": so_name, "docstatus": 1},
		fields=["parent"],
		order_by="creation desc",
		limit=1,
	)
	return rows[0].parent if rows else None


@frappe.whitelist()
def get_user_orders():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to view your orders"), frappe.AuthenticationError)

	website_user = get_or_create_website_user(frappe.session.user)
	if not website_user.customer:
		return {
			"success": True,
			"orders": [],
			"summary": {"total": 0, "in_progress": 0, "shipped": 0, "delivered": 0, "cancelled": 0},
		}

	sales_orders = frappe.get_all(
		"Sales Order",
		filters={"customer": website_user.customer, "docstatus": ["in", [0, 1, 2]]},
		fields=["name", "transaction_date", "grand_total", "currency", "status", "docstatus", "per_delivered"],
		order_by="creation desc",
	)

	summary = {"total": 0, "in_progress": 0, "shipped": 0, "delivered": 0, "cancelled": 0}
	orders = []

	for so in sales_orders:
		delivery_note = _get_delivery_note(so.name)
		display_status = _display_status(so, delivery_note)

		summary["total"] += 1
		summary[display_status.lower().replace(" ", "_")] += 1

		orders.append(
			{
				"name": so.name,
				"transaction_date": so.transaction_date,
				"grand_total": so.grand_total,
				"currency": so.currency,
				"status": so.status,
				"docstatus": so.docstatus,
				"per_delivered": so.per_delivered,
				"display_status": display_status,
				"progress_step": _progress_step(so, display_status),
				"steps": STEPS,
				"items": _get_items(so.name),
				"tracking": delivery_note,
				"sales_invoice": _get_sales_invoice(so.name),
			}
		)

	return {"success": True, "orders": orders, "summary": summary}
