# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Sales Order/Invoice line items need an Item record (item_code) — Product
# has no accounting meaning of its own, so every Product is mirrored to a
# matching non-stock Item of the same name.
ITEM_GROUP = "Products"


class Product(Document):
	def on_update(self):
		self.sync_item()

	def sync_item(self):
		if frappe.db.exists("Item", self.name):
			item = frappe.get_doc("Item", self.name)
			item.item_name = self.product_name
			item.standard_rate = self.price
			item.image = self.image_1
			item.save(ignore_permissions=True)
		else:
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self.name,
					"item_name": self.product_name,
					"item_group": ITEM_GROUP,
					"is_stock_item": 0,
					"standard_rate": self.price,
					"image": self.image_1,
				}
			).insert(ignore_permissions=True)
