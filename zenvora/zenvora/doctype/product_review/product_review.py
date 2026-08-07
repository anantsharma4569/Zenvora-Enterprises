# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from zenvora.inventory_utils import get_variant_item_codes
from zenvora.website_user_utils import get_or_create_website_user


class ProductReview(Document):
	def validate(self):
		if not (1 <= self.rating <= 5):
			frappe.throw(frappe._("Rating must be between 1 and 5"))

	def before_insert(self):
		if not self.user:
			self.user = frappe.session.user
		if not self.website_user:
			self.website_user = get_or_create_website_user(self.user).name
		self.verified_buyer = 1 if self.is_verified_purchase() else 0

	def on_update(self):
		self.update_product_rating()

	def on_trash(self):
		self.update_product_rating()

	def is_verified_purchase(self):
		website_user = get_or_create_website_user(self.user)
		if not website_user.customer:
			return False

		# Delivery Note lines carry a size-variant's item_code, never the
		# Product template code — check every variant code too, or a real
		# buyer's review always comes back unverified.
		item_codes = get_variant_item_codes(self.product) + [self.product]
		return bool(
			frappe.db.exists(
				"Delivery Note Item",
				{
					"item_code": ["in", item_codes],
					"docstatus": 1,
					"parent": [
						"in",
						frappe.get_all(
							"Delivery Note",
							filters={"customer": website_user.customer, "docstatus": 1},
							pluck="name",
						)
						or [""],
					],
				},
			)
		)

	def update_product_rating(self):
		# frappe.get_all no longer accepts raw SQL function strings in `fields`
		# (rejected by _validate_select_field) — the dict form below is the
		# supported replacement for AVG()/COUNT().
		agg = frappe.db.get_all(
			"Product Review",
			filters={"product": self.product, "published": 1},
			fields=[
				{"AVG": "rating", "as": "avg_rating"},
				{"COUNT": "name", "as": "review_count"},
			],
		)[0]

		frappe.db.set_value(
			"Product",
			self.product,
			{
				"rating": agg.avg_rating or 0,
				"review_count": agg.review_count or 0,
			},
			update_modified=False,
		)
