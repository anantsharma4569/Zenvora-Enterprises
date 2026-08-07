# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe


def execute():
	# Frappe's root path resolver (frappe.website.path_resolver.resolve_path)
	# never looks for www/index.html on its own — for an empty path it always
	# calls get_home_page(), which falls all the way back to "login" for
	# Guests when no home page is configured anywhere. Point it at our
	# storefront home page explicitly.
	website_settings = frappe.get_single("Website Settings")
	if not website_settings.home_page:
		website_settings.home_page = "index"
		website_settings.save(ignore_permissions=True)
