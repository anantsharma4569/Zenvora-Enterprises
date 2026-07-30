# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe


def execute():
	if not frappe.db.exists("Role", "Website User"):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": "Website User",
				"desk_access": 0,
			}
		).insert(ignore_permissions=True)

	website_users = frappe.get_all("User", filters={"user_type": "Website User"}, pluck="name")
	for user in website_users:
		if "Website User" not in frappe.get_roles(user):
			frappe.get_doc("User", user).add_roles("Website User")
