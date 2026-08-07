import frappe
from frappe import _
from frappe.utils import cint

from zenvora.inventory_utils import get_available_qty, get_variant_item_code


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use your bag"), frappe.AuthenticationError)


def _assert_available(product, size, requested_qty):
	if not size:
		frappe.throw(_("Please select a size"))

	item_code = get_variant_item_code(product, size)
	# Locks the Bin row for the rest of this request — closes the window
	# where two concurrent adds/updates for the same item+size both read the
	# same stale quantity and both pass this check.
	available = cint(get_available_qty(item_code, for_update=True))
	if requested_qty > available:
		if available <= 0:
			frappe.throw(_("{0} is out of stock in size {1}").format(product, size))
		frappe.throw(_("Only {0} left of {1} in size {2}").format(available, product, size))


def _serialize(item, product_map):
	product = product_map.get(item.get("product"), {})
	return {
		"name": item.get("name"),
		"product": item.get("product"),
		"product_name": product.get("product_name"),
		"image": product.get("image_1"),
		"price": product.get("price"),
		"qty": item.get("qty"),
		"color": item.get("color"),
		"size": item.get("size"),
	}


@frappe.whitelist()
def get_cart():
	_require_login()

	items = frappe.get_all(
		"Cart Item",
		filters={"user": frappe.session.user},
		fields=["name", "product", "qty", "color", "size"],
		order_by="creation asc",
	)

	products = (
		frappe.get_all(
			"Product",
			filters={"name": ["in", [i.product for i in items]]},
			fields=["name", "product_name", "price", "image_1"],
		)
		if items
		else []
	)
	product_map = {p.name: p for p in products}

	return [_serialize(item, product_map) for item in items]


@frappe.whitelist(methods=["POST"])
def add_to_cart(product, qty=1, color=None, size=None):
	_require_login()

	if not frappe.db.exists("Product", product):
		frappe.throw(_("Product not found"))
	qty = cint(qty)
	if qty < 1:
		frappe.throw(_("Quantity must be at least 1"))

	existing_name = frappe.db.get_value(
		"Cart Item",
		{"user": frappe.session.user, "product": product, "color": color, "size": size},
		"name",
	)
	existing_qty = cint(frappe.db.get_value("Cart Item", existing_name, "qty")) if existing_name else 0
	_assert_available(product, size, existing_qty + qty)

	if existing_name:
		cart_item = frappe.get_doc("Cart Item", existing_name)
		cart_item.qty = cint(cart_item.qty) + qty
		cart_item.save()
	else:
		cart_item = frappe.get_doc(
			{
				"doctype": "Cart Item",
				"product": product,
				"qty": qty,
				"color": color,
				"size": size,
			}
		)
		cart_item.insert()

	frappe.db.commit()
	return get_cart()


@frappe.whitelist(methods=["POST"])
def update_cart_item(name, qty):
	_require_login()

	qty = cint(qty)
	cart_item = frappe.get_doc("Cart Item", name)

	if qty <= 0:
		cart_item.delete()
	else:
		_assert_available(cart_item.product, cart_item.size, qty)
		cart_item.qty = qty
		cart_item.save()

	frappe.db.commit()
	return get_cart()


@frappe.whitelist(methods=["POST"])
def remove_from_cart(name):
	_require_login()

	frappe.get_doc("Cart Item", name).delete()
	frappe.db.commit()
	return get_cart()


@frappe.whitelist(methods=["POST"])
def clear_cart():
	_require_login()

	for name in frappe.get_all("Cart Item", filters={"user": frappe.session.user}, pluck="name"):
		frappe.delete_doc("Cart Item", name)

	frappe.db.commit()
	return []
