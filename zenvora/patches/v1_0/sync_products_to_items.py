# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe


def execute():
	for name in frappe.get_all("Product", pluck="name"):
		frappe.get_doc("Product", name).sync_item()
	frappe.db.commit()
