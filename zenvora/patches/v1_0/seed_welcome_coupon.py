# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe

COMPANY = "Zenvora"
ITEM_GROUP = "Products"


def execute():
	if not frappe.db.exists("Company", COMPANY) or frappe.db.exists("Coupon Code", {"coupon_code": "WELCOME10"}):
		return

	pr = frappe.get_doc(
		{
			"doctype": "Pricing Rule",
			"title": "Zenvora Welcome 10",
			"apply_on": "Item Group",
			"price_or_product_discount": "Price",
			"selling": 1,
			"rate_or_discount": "Discount Percentage",
			"discount_percentage": 10,
			"company": COMPANY,
			"coupon_code_based": 1,
			"item_groups": [{"item_group": ITEM_GROUP}],
		}
	)
	pr.insert(ignore_permissions=True)

	frappe.get_doc(
		{
			"doctype": "Coupon Code",
			"coupon_name": "Welcome 10",
			"coupon_code": "WELCOME10",
			"coupon_type": "Promotional",
			"pricing_rule": pr.name,
			"maximum_use": 1000,
			"description": "10% off your order",
		}
	).insert(ignore_permissions=True)

	frappe.db.commit()
