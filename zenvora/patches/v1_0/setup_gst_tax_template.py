# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe

COMPANY = "Zenvora"
GST_RATE = 5  # simple flat rate; split into CGST/SGST/IGST later if needed
TAX_ACCOUNT = "Output GST - ZEN"
TEMPLATE_NAME = "GST 5%"


def execute():
	if not frappe.db.exists("Company", COMPANY):
		return

	if not frappe.db.exists("Account", TAX_ACCOUNT):
		parent = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": "Duties and Taxes", "is_group": 1}, "name"
		)
		if not parent:
			return
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "Output GST",
				"company": COMPANY,
				"parent_account": parent,
				"account_type": "Tax",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Sales Taxes and Charges Template", {"company": COMPANY, "title": TEMPLATE_NAME}):
		frappe.get_doc(
			{
				"doctype": "Sales Taxes and Charges Template",
				"title": TEMPLATE_NAME,
				"company": COMPANY,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": TAX_ACCOUNT,
						"description": "GST",
						"rate": GST_RATE,
					}
				],
			}
		).insert(ignore_permissions=True)

	frappe.db.commit()
