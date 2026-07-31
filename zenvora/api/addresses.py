import frappe
from frappe import _

from zenvora.website_user_utils import get_or_create_customer_for_user

ADDRESS_FIELDS = [
	"name",
	"address_title",
	"address_line1",
	"address_line2",
	"city",
	"state",
	"pincode",
	"country",
	"phone",
	"is_primary_address",
	"is_shipping_address",
]


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def _get_customer():
	return frappe.db.get_value("Website User", frappe.session.user, "customer")


def _assert_owns_address(name):
	customer = _get_customer()
	linked = customer and frappe.db.exists(
		"Dynamic Link",
		{"parent": name, "parenttype": "Address", "link_doctype": "Customer", "link_name": customer},
	)
	if not linked:
		frappe.throw(_("Address not found"), frappe.PermissionError)


@frappe.whitelist()
def get_addresses():
	"""Website Users have no direct permission on the core Address doctype
	(it's shared across every company/customer on this site) — reads and
	writes go exclusively through this module, scoped to the caller's own
	Customer via the Dynamic Link child table."""
	_require_login()

	customer = _get_customer()
	if not customer:
		return []

	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		address_names = frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
			pluck="parent",
		)
		addresses = (
			frappe.get_all(
				"Address",
				filters={"name": ["in", address_names]},
				fields=ADDRESS_FIELDS,
				order_by="modified desc",
			)
			if address_names
			else []
		)
	finally:
		frappe.set_user(current_user)

	return addresses


@frappe.whitelist(methods=["POST"])
def create_address(
	address_title,
	address_line1,
	city,
	state,
	pincode,
	phone=None,
	address_line2=None,
	country="India",
	is_shipping_address=1,
):
	_require_login()
	customer = get_or_create_customer_for_user(frappe.session.user)
	is_first_address = not get_addresses()

	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": address_title,
				"address_type": "Shipping",
				"address_line1": address_line1,
				"address_line2": address_line2,
				"city": city,
				"state": state,
				"pincode": pincode,
				"country": country,
				"phone": phone,
				"is_shipping_address": 1 if int(is_shipping_address) else 0,
				# first address a customer saves becomes their default automatically
				"is_primary_address": 1 if is_first_address else 0,
				"links": [{"link_doctype": "Customer", "link_name": customer}],
			}
		).insert()
	finally:
		frappe.set_user(current_user)

	frappe.db.commit()
	return get_addresses()


@frappe.whitelist(methods=["POST"])
def delete_address(name):
	_require_login()
	_assert_owns_address(name)

	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		frappe.delete_doc("Address", name)
	finally:
		frappe.set_user(current_user)

	frappe.db.commit()
	return get_addresses()


@frappe.whitelist(methods=["POST"])
def set_default_address(name):
	_require_login()
	_assert_owns_address(name)

	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		doc = frappe.get_doc("Address", name)
		doc.is_primary_address = 1
		doc.save()
	finally:
		frappe.set_user(current_user)

	frappe.db.commit()
	return get_addresses()
