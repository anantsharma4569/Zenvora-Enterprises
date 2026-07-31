import frappe
from frappe import _

from zenvora.website_user_utils import get_or_create_website_user


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def get_or_create_razorpay_customer_id(website_user):
	"""website_user: a loaded Website User doc. Creates the matching Razorpay
	Customer on first use — never raw card data, just an identity Razorpay
	uses to group saved-card tokens under (see the Token API)."""
	from zenvora.api.razorpay_payment import _get_client

	if website_user.razorpay_customer_id:
		return website_user.razorpay_customer_id

	user_doc = frappe.get_doc("User", website_user.user)
	try:
		customer = _get_client().customer.create(
			{
				"name": user_doc.full_name or user_doc.name,
				"email": user_doc.email,
				"contact": user_doc.phone or "",
				"fail_existing": "0",
			}
		)
	except Exception:
		frappe.log_error(title=f"Razorpay customer creation failed for {website_user.user}")
		return None

	website_user.db_set("razorpay_customer_id", customer["id"])
	return customer["id"]


@frappe.whitelist()
def get_saved_payment_methods():
	_require_login()
	website_user = get_or_create_website_user(frappe.session.user)
	return frappe.get_all(
		"Saved Payment Method",
		filters={"website_user": website_user.name},
		fields=["name", "razorpay_token_id", "card_network", "card_last4", "card_type", "card_name"],
		order_by="creation desc",
	)


@frappe.whitelist(methods=["POST"])
def sync_saved_payment_methods():
	"""Pull the latest saved-card tokens from Razorpay into our local cache —
	call this right after a checkout where the user ticked "save card"."""
	from zenvora.api.razorpay_payment import _get_client

	_require_login()
	website_user = get_or_create_website_user(frappe.session.user)
	if not website_user.razorpay_customer_id:
		return []

	tokens = _get_client().token.all(website_user.razorpay_customer_id).get("items", [])
	for token in tokens:
		if frappe.db.exists("Saved Payment Method", {"razorpay_token_id": token["id"]}):
			continue
		card = token.get("card") or {}
		frappe.get_doc(
			{
				"doctype": "Saved Payment Method",
				"website_user": website_user.name,
				"razorpay_token_id": token["id"],
				"card_network": card.get("network"),
				"card_last4": card.get("last4"),
				"card_type": card.get("type"),
				"card_name": card.get("name"),
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()

	return get_saved_payment_methods()


@frappe.whitelist(methods=["POST"])
def delete_saved_payment_method(name):
	_require_login()
	website_user = get_or_create_website_user(frappe.session.user)
	doc = frappe.get_doc("Saved Payment Method", name)
	if doc.website_user != website_user.name:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if website_user.razorpay_customer_id:
		from zenvora.api.razorpay_payment import _get_client

		try:
			_get_client().token.delete(website_user.razorpay_customer_id, doc.razorpay_token_id)
		except Exception:
			frappe.log_error(title=f"Razorpay token delete failed for {doc.razorpay_token_id}")

	frappe.delete_doc("Saved Payment Method", name, ignore_permissions=True)
	frappe.db.commit()

	return get_saved_payment_methods()
