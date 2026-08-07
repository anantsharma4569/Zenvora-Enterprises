import frappe

from zenvora.inventory_utils import SIZES, get_stock_by_size


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
