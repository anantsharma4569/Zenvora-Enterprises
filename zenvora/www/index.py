# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe

no_cache = True

PROMO_MESSAGES = [
	"Free Shipping on orders above ₹999",
	"Easy 14-day returns",
	"Get 10% off your first order – Use code: WELCOME10",
]


def get_context(context):
	context.app_name = frappe.get_website_settings("app_name") or "Zenvora"
	context.promo_messages = PROMO_MESSAGES

	settings = frappe.get_cached_doc("Zenvora Settings")
	context.hero_image = settings.home_hero_image
	context.hero_image_alt_text = settings.home_hero_image_alt_text or context.app_name

	context.categories = frappe.get_all(
		"Product Category",
		fields=["name", "category_name", "image"],
		order_by="category_name asc",
	)

	context.products = frappe.get_all(
		"Product",
		fields=[
			"name",
			"product_name",
			"price",
			"compare_at_price",
			"on_sale",
			"image_1",
			"image_2",
			"rating",
			"review_count",
			"category",
		],
		order_by="creation desc",
	)

	context.cart_count = 0
	if frappe.session.user != "Guest":
		context.cart_count = frappe.db.count("Cart Item", {"user": frappe.session.user})

	return context
