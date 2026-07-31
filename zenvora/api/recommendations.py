import frappe

PRODUCT_FIELDS = [
	"name",
	"product_name",
	"price",
	"compare_at_price",
	"image_1",
	"image_2",
	"rating",
	"review_count",
]


@frappe.whitelist(allow_guest=True)
def get_recommendations(exclude_product=None, limit=8):
	"""Simple heuristic, not a real recommendation engine: same-category
	products ranked by rating, backfilled with top-rated products generally
	if the category doesn't have enough. Used for both "Recommended for
	you" (dashboard) and "You may also like" (order detail)."""
	limit = int(limit)
	filters = {}
	if exclude_product:
		category = frappe.db.get_value("Product", exclude_product, "category")
		if category:
			filters["category"] = category
		filters["name"] = ["!=", exclude_product]

	products = frappe.get_all(
		"Product", filters=filters, fields=PRODUCT_FIELDS, order_by="rating desc, review_count desc", limit_page_length=limit
	)

	if len(products) < limit:
		seen = [p.name for p in products] + ([exclude_product] if exclude_product else [])
		products += frappe.get_all(
			"Product",
			filters={"name": ["not in", seen]},
			fields=PRODUCT_FIELDS,
			order_by="rating desc, review_count desc",
			limit_page_length=limit - len(products),
		)

	return products
