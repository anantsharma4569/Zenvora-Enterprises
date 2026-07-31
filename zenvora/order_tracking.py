import frappe


def on_delivery_note_submit(doc, method=None):
	"""hooked via doc_events — stamps delivered_at on every Sales Order this
	Delivery Note fulfills."""
	sales_orders = {i.against_sales_order for i in doc.items if i.against_sales_order}
	for so_name in sales_orders:
		frappe.db.set_value("Sales Order", so_name, "delivered_at", doc.posting_date)
