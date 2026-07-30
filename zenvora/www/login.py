# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import frappe
from frappe.www.login import get_context as get_core_login_context

no_cache = True


def get_context(context):
	context = get_core_login_context(context)

	settings = frappe.get_cached_doc("Zenvora Settings")
	context["login_page_image"] = settings.login_page_image
	context["login_page_image_alt_text"] = settings.login_page_image_alt_text or "Zenvora"

	return context
