import frappe
from frappe import _


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def _serialize(item, product_map):
	product = product_map.get(item.get("product"), {})
	return {
		"name": item.get("name"),
		"product": item.get("product"),
		"product_name": product.get("product_name"),
		"image": product.get("image_1"),
		"price": product.get("price"),
		"compare_at_price": product.get("compare_at_price"),
	}


@frappe.whitelist()
def get_wishlist():
	_require_login()

	items = frappe.get_all(
		"Wishlist Item", filters={"user": frappe.session.user}, fields=["name", "product"], order_by="creation desc"
	)
	products = (
		frappe.get_all(
			"Product",
			filters={"name": ["in", [i.product for i in items]]},
			fields=["name", "product_name", "price", "compare_at_price", "image_1"],
		)
		if items
		else []
	)
	product_map = {p.name: p for p in products}
	return [_serialize(item, product_map) for item in items]


@frappe.whitelist(methods=["POST"])
def toggle_wishlist(product):
	"""Add the product if it isn't already wishlisted, remove it if it is.
	Returns {"wishlisted": bool} plus the refreshed list."""
	_require_login()

	existing = frappe.db.exists("Wishlist Item", {"user": frappe.session.user, "product": product})
	if existing:
		frappe.delete_doc("Wishlist Item", existing, ignore_permissions=True)
		wishlisted = False
	else:
		if not frappe.db.exists("Product", product):
			frappe.throw(_("Product not found"))
		frappe.get_doc({"doctype": "Wishlist Item", "product": product}).insert(ignore_permissions=True)
		wishlisted = True

	frappe.db.commit()
	return {"wishlisted": wishlisted, "items": get_wishlist()}


@frappe.whitelist(methods=["POST"])
def remove_from_wishlist(name):
	_require_login()

	owner = frappe.db.get_value("Wishlist Item", name, "user")
	if owner != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	frappe.delete_doc("Wishlist Item", name, ignore_permissions=True)
	frappe.db.commit()
	return get_wishlist()
