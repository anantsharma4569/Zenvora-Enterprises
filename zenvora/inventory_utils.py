# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe
from erpnext.controllers.item_variant import create_variant

ZENVORA_WAREHOUSE = "Stores - ZEN"

# Matches the abbreviations already on the core "Size" Item Attribute
# (Small->S, Medium->M, Large->L, Extra Large->XL), so variant item codes
# come out as "<Product>-S", "-M", "-L", "-XL".
SIZES = ["Small", "Medium", "Large", "Extra Large"]


def ensure_size_variants(product_name, item_group, standard_rate=None):
	"""Make sure this Product's Item is a Size variant template with all 4
	standard size variants under it. Safe to call repeatedly — existing
	variants are left alone."""
	if not frappe.db.exists("Item", product_name):
		return

	template = frappe.get_doc("Item", product_name)

	if not template.has_variants:
		template.has_variants = 1
		template.set("attributes", [{"attribute": "Size"}])
		template.save(ignore_permissions=True)

	for size in SIZES:
		variant_item_name = f"{template.item_name} ({size})"

		existing = find_variant(product_name, size)
		if existing:
			updates = {"item_name": variant_item_name}
			if standard_rate is not None:
				updates["standard_rate"] = standard_rate
			frappe.db.set_value("Item", existing, updates)
			continue

		variant = create_variant(product_name, {"Size": size})
		# copy_attributes_to_variant() copies is_stock_item from the
		# (non-stock) template — variants are the ones that actually carry
		# stock, so this has to be set explicitly after. item_name is
		# excluded from that copy entirely, defaulting to the item_code
		# (e.g. "Product-S") unless set here too.
		variant.is_stock_item = 1
		variant.item_group = item_group
		variant.item_name = variant_item_name
		if standard_rate is not None:
			variant.standard_rate = standard_rate
		variant.insert(ignore_permissions=True)


def find_variant(template_item_code, size):
	rows = frappe.get_all(
		"Item Variant Attribute",
		filters={"parenttype": "Item", "attribute": "Size", "attribute_value": size},
		fields=["parent"],
	)
	for row in rows:
		if frappe.db.get_value("Item", row.parent, "variant_of") == template_item_code:
			return row.parent
	return None


def get_variant_item_code(product_name, size):
	"""Resolve a Product + human size name (e.g. "Small") to its variant
	Item code (e.g. "Product Name-S"). Raises if that size doesn't exist for
	this product."""
	variant = find_variant(product_name, size)
	if not variant:
		frappe.throw(frappe._("{0} is not available in size {1}").format(product_name, size))
	return variant


def get_stock_by_size(product_name):
	"""{size: available_qty} for every size variant of this product, in the
	Zenvora stores warehouse. 0 (not missing) for a size with no Bin yet —
	that just means nothing has been stocked in for it."""
	stock = {size: 0 for size in SIZES}

	variants = frappe.get_all(
		"Item Variant Attribute",
		filters={"parenttype": "Item", "attribute": "Size"},
		fields=["parent", "attribute_value"],
	)
	variant_sizes = {
		row.parent: row.attribute_value
		for row in variants
		if frappe.db.get_value("Item", row.parent, "variant_of") == product_name
	}
	if not variant_sizes:
		return stock

	bins = frappe.get_all(
		"Bin",
		filters={"item_code": ["in", list(variant_sizes.keys())], "warehouse": ZENVORA_WAREHOUSE},
		fields=["item_code", "actual_qty"],
	)
	qty_by_item = {b.item_code: b.actual_qty for b in bins}

	for item_code, size in variant_sizes.items():
		stock[size] = qty_by_item.get(item_code, 0)

	return stock


def get_available_qty(item_code):
	return frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": ZENVORA_WAREHOUSE}, "actual_qty") or 0


def resolve_variant_to_product_size(item_code):
	"""Reverse of get_variant_item_code — given a size variant's Item code
	(e.g. "Product Name-M"), return (product_name, size). Falls back to
	(item_code, None) for a non-variant item_code (e.g. orders placed before
	size variants existed)."""
	variant_of = frappe.db.get_value("Item", item_code, "variant_of")
	if not variant_of:
		return item_code, None

	size = frappe.db.get_value(
		"Item Variant Attribute", {"parent": item_code, "attribute": "Size"}, "attribute_value"
	)
	return variant_of, size
