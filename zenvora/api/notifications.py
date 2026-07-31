import frappe
from frappe import _


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


@frappe.whitelist()
def get_notifications():
	_require_login()
	return frappe.get_all(
		"Zenvora Notification",
		filters={"user": frappe.session.user},
		fields=["name", "title", "message", "is_read", "reference_doctype", "reference_name", "creation"],
		order_by="creation desc",
		limit_page_length=50,
	)


@frappe.whitelist(methods=["POST"])
def mark_read(name=None):
	"""Mark one notification read, or all of them if name is omitted."""
	_require_login()
	if name:
		doc = frappe.get_doc("Zenvora Notification", name)
		if doc.user != frappe.session.user:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		doc.db_set("is_read", 1)
	else:
		for n in frappe.get_all(
			"Zenvora Notification", filters={"user": frappe.session.user, "is_read": 0}, pluck="name"
		):
			frappe.db.set_value("Zenvora Notification", n, "is_read", 1)
	frappe.db.commit()
	return get_notifications()
