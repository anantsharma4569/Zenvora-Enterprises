# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe

from zenvora.zenvora_order_sync import sync_zenvora_order


def execute():
	for name in frappe.get_all("Sales Order", filters={"company": "Zenvora"}, pluck="name"):
		sync_zenvora_order(frappe.get_doc("Sales Order", name))
