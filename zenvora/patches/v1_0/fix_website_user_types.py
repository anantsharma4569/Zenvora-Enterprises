# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""The "All" and "Website User" roles both have desk_access=1 on this
	site (pre-existing, site-wide — not something this app should change),
	which makes Frappe force user_type to "System User" on every User save
	regardless of what's set. Force-correct it back for every account known
	to be a Zenvora storefront customer (i.e. has a Website User profile),
	without touching anyone else's account or the shared role config."""
	for user in frappe.get_all("Website User", pluck="user"):
		frappe.db.set_value("User", user, "user_type", "Website User")
	frappe.db.commit()
