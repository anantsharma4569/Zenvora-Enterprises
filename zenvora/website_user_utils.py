import frappe

ZENVORA_COMPANY = "Zenvora"


def get_or_create_website_user(user):
	"""Return this user's Website User profile doc, creating it if missing
	(e.g. for accounts registered before this doctype existed)."""
	name = frappe.db.exists("Website User", {"user": user})
	if name:
		return frappe.get_doc("Website User", name)

	doc = frappe.get_doc({"doctype": "Website User", "user": user})
	doc.insert(ignore_permissions=True)
	return doc


def get_or_create_customer_for_user(user):
	"""Return the ERPNext Customer for this account, creating one under the
	Zenvora company if this is their first order."""
	website_user = get_or_create_website_user(user)
	if website_user.customer:
		return website_user.customer

	full_name = frappe.db.get_value("User", user, "full_name") or user
	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": f"{full_name} ({user})",
			"customer_type": "Individual",
			"customer_group": "Individual",
			"territory": "All Territories",
		}
	)
	customer.insert(ignore_permissions=True)

	website_user.customer = customer.name
	website_user.save(ignore_permissions=True)

	# Scope this user down to only their own Customer's records (Sales Order,
	# Sales Invoice, Delivery Note all link to Customer) — without this, the
	# read permission granted to the Website User role would let them see
	# every customer's orders/invoices, not just their own.
	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": user,
			"allow": "Customer",
			"for_value": customer.name,
		}
	).insert(ignore_permissions=True)

	return customer.name
