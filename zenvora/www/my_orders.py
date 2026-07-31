# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe

from zenvora.api.order_tracker import get_user_orders

no_cache = True


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/my-orders"
		raise frappe.Redirect

	context.no_header = True
	context.title = "My Orders"

	data = get_user_orders()
	context.orders = data["orders"]
	context.summary = data["summary"]
	context.app_name = frappe.get_website_settings("app_name") or "Zenvora"

	return context
