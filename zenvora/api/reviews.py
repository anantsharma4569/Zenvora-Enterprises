import frappe
from frappe import _

from zenvora.website_user_utils import get_or_create_website_user


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def _validate_purchase(product, sales_order):
	"""If a sales_order is given, make sure it belongs to this user and
	actually contains this product — reviews shouldn't be forgeable for
	orders/products the reviewer never bought."""
	website_user = get_or_create_website_user(frappe.session.user)
	so_customer = frappe.db.get_value("Sales Order", sales_order, "customer")

	if not so_customer or so_customer != website_user.customer:
		frappe.throw(_("You can only review your own orders"), frappe.PermissionError)

	has_item = frappe.db.exists(
		"Sales Order Item", {"parent": sales_order, "item_code": product}
	)
	if not has_item:
		frappe.throw(_("This product is not part of that order"))


@frappe.whitelist(methods=["POST"])
def submit_review(product, rating, review_title=None, review_text=None, review_image=None, sales_order=None):
	_require_login()

	rating = frappe.utils.cint(rating)
	if not (1 <= rating <= 5):
		frappe.throw(_("Rating must be between 1 and 5"))

	if not frappe.db.exists("Product", product):
		frappe.throw(_("Product not found"))

	if sales_order:
		_validate_purchase(product, sales_order)

	existing_name = frappe.db.get_value(
		"Product Review", {"user": frappe.session.user, "product": product}, "name"
	)
	if existing_name:
		review = frappe.get_doc("Product Review", existing_name)
		review.rating = rating
		review.review_title = review_title
		review.review_text = review_text
		review.review_image = review_image
		if sales_order:
			review.sales_order = sales_order
		review.save()
	else:
		review = frappe.get_doc(
			{
				"doctype": "Product Review",
				"product": product,
				"rating": rating,
				"review_title": review_title,
				"review_text": review_text,
				"review_image": review_image,
				"sales_order": sales_order,
			}
		)
		review.insert()

	frappe.db.commit()

	return {
		"success": True,
		"name": review.name,
		"rating": review.rating,
		"review_title": review.review_title,
		"review_text": review.review_text,
		"verified_buyer": review.verified_buyer,
	}


def _is_delivered_to_user(user, product):
	"""Same check as ProductReview.is_verified_purchase(), duplicated here
	since that's an instance method and we need this before a review exists."""
	website_user = get_or_create_website_user(user)
	if not website_user.customer:
		return False

	return bool(
		frappe.db.exists(
			"Delivery Note Item",
			{
				"item_code": product,
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


@frappe.whitelist(allow_guest=True)
def can_user_review(product):
	if frappe.session.user == "Guest":
		return {"can_review": False, "already_reviewed": False, "is_verified_buyer": False}

	already_reviewed = bool(
		frappe.db.exists("Product Review", {"user": frappe.session.user, "product": product})
	)
	is_verified_buyer = _is_delivered_to_user(frappe.session.user, product)

	return {
		"can_review": is_verified_buyer and not already_reviewed,
		"already_reviewed": already_reviewed,
		"is_verified_buyer": is_verified_buyer,
	}


@frappe.whitelist(allow_guest=True)
def get_product_reviews(product):
	reviews = frappe.get_all(
		"Product Review",
		filters={"product": product, "published": 1},
		fields=[
			"name", "rating", "review_title", "review_text", "review_image",
			"verified_buyer", "creation", "user",
		],
		order_by="creation desc",
	)

	breakdown = {str(i): 0 for i in range(1, 6)}
	for r in reviews:
		r["reviewer_name"] = frappe.db.get_value("User", r.user, "full_name") or r.user
		del r["user"]  # don't expose reviewer emails to other shoppers
		breakdown[str(r.rating)] += 1

	total = len(reviews)
	average_rating = round(sum(r.rating for r in reviews) / total, 2) if total else 0

	return {
		"reviews": reviews,
		"average_rating": average_rating,
		"total_reviews": total,
		"rating_breakdown": breakdown,
	}
