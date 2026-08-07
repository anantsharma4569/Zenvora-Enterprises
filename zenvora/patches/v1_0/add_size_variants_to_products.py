# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe

from zenvora.inventory_utils import ensure_size_variants


def execute():
	for product in frappe.get_all("Product", fields=["name", "price"]):
		ensure_size_variants(product.name, item_group="Products", standard_rate=product.price)
