# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe
from frappe.permissions import add_permission, update_permission_property

# Website User customers may only READ these — creation happens server-side
# (see zenvora.api.orders / ERPNext checkout), never directly by a customer.
READ_ONLY_DOCTYPES = ["Sales Order", "Sales Invoice", "Delivery Note"]


def execute():
	for doctype in READ_ONLY_DOCTYPES:
		add_permission(doctype, "Website User", 0)
		update_permission_property(doctype, "Website User", 0, "read", 1)

	# A bare role permission would let any Website User read every customer's
	# orders/invoices. Frappe's User Permission engine automatically scopes
	# any doctype with a "customer" Link field (Sales Order, Sales Invoice,
	# Delivery Note all have one) down to just the linked Customer once a
	# User Permission ties that user to that Customer — so back-fill one for
	# every account that already has a Customer.
	website_users = frappe.get_all(
		"Website User", filters={"customer": ["is", "set"]}, fields=["user", "customer"]
	)
	for wu in website_users:
		exists = frappe.db.exists(
			"User Permission", {"user": wu.user, "allow": "Customer", "for_value": wu.customer}
		)
		if not exists:
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": wu.user,
					"allow": "Customer",
					"for_value": wu.customer,
				}
			).insert(ignore_permissions=True)
