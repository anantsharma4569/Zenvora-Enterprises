import frappe

COMPANY = "Zenvora"


def sync_zenvora_order(doc, method=None):
	"""Mirror a Sales Order into the simpler Zenvora Order doctype for easy
	browsing. Sales Order / Sales Invoice / Payment Entry remain the real
	accounting records — this is purely a read-friendly summary, kept in
	sync via doc_events (see hooks.py) on every Sales Order save/submit/cancel."""
	if doc.company != COMPANY:
		return

	item_summary = ", ".join(f"{i.item_name} x{int(i.qty)}" for i in doc.items)

	payment_status = (
		frappe.db.get_value(
			"Razorpay Transaction", {"sales_order": doc.name}, "status", order_by="creation desc"
		)
		or "Pending"
	)

	values = {
		"website_user": frappe.db.get_value("Website User", {"customer": doc.customer}, "name"),
		"customer": doc.customer,
		"order_date": doc.transaction_date,
		"status": doc.status,
		"payment_status": payment_status,
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"item_summary": item_summary,
		"confirmed_at": doc.get("confirmed_at"),
		"packed_at": doc.get("packed_at"),
		"shipped_at": doc.get("shipped_at"),
		"out_for_delivery_at": doc.get("out_for_delivery_at"),
		"delivered_at": doc.get("delivered_at"),
	}

	existing = frappe.db.exists("Zenvora Order", doc.name)
	if existing:
		zo = frappe.get_doc("Zenvora Order", existing)
		zo.update(values)
		zo.save(ignore_permissions=True)
	else:
		zo = frappe.get_doc({"doctype": "Zenvora Order", "sales_order": doc.name, **values})
		zo.insert(ignore_permissions=True)

	frappe.db.commit()
