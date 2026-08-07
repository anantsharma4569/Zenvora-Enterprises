import json

import frappe

from zenvora.inventory_utils import SIZES, get_in_stock_map, get_stock_by_size


@frappe.whitelist(allow_guest=True)
def get_product_stock(product):
	if not frappe.db.exists("Product", product):
		frappe.throw(frappe._("Product not found"))

	stock = get_stock_by_size(product)
	return {
		"sizes": SIZES,
		"stock": stock,
		"in_stock": any(qty > 0 for qty in stock.values()),
	}


@frappe.whitelist(allow_guest=True)
def get_products_stock(products):
	"""{product_name: in_stock bool} for a batch of products — one call per
	product grid instead of one per card."""
	if isinstance(products, str):
		products = json.loads(products)
	return get_in_stock_map(products)
