# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

import json

import frappe

COMPANY = "Zenvora"


def execute():
	_create_number_card(
		"Zenvora Orders Today",
		filters_json={"company": COMPANY},
		dynamic_filters_json={"transaction_date": 'frappe.datetime.get_today()'},
	)
	_create_number_card(
		"Zenvora Total Orders",
		filters_json={"company": COMPANY},
	)
	_create_workspace()


def _create_number_card(label, filters_json, dynamic_filters_json=None):
	if frappe.db.exists("Number Card", label):
		return
	frappe.get_doc(
		{
			"doctype": "Number Card",
			"name": label,
			"label": label,
			"document_type": "Sales Order",
			"function": "Count",
			"is_public": 1,
			"module": "Zenvora",
			"filters_json": json.dumps(filters_json),
			"dynamic_filters_json": json.dumps(dynamic_filters_json) if dynamic_filters_json else "[]",
		}
	).insert(ignore_permissions=True)


def _create_workspace():
	if frappe.db.exists("Workspace", "Zenvora"):
		return

	content = [
		{"id": "zv-header", "type": "header", "data": {"text": "<span class=\"h4\"><b>Zenvora</b></span>", "col": 12}},
		{"id": "zv-card-1", "type": "number_card", "data": {"number_card_name": "Zenvora Orders Today", "col": 4}},
		{"id": "zv-card-2", "type": "number_card", "data": {"number_card_name": "Zenvora Total Orders", "col": 4}},
		{"id": "zv-spacer", "type": "spacer", "data": {"col": 12}},
		{
			"id": "zv-shortcuts-header",
			"type": "header",
			"data": {"text": "<span class=\"h4\"><b>Shortcuts</b></span>", "col": 12},
		},
		{"id": "zv-sc-1", "type": "shortcut", "data": {"shortcut_name": "Sales Orders", "col": 3}},
		{"id": "zv-sc-2", "type": "shortcut", "data": {"shortcut_name": "Sales Invoices", "col": 3}},
		{"id": "zv-sc-3", "type": "shortcut", "data": {"shortcut_name": "Payment Entries", "col": 3}},
		{"id": "zv-sc-4", "type": "shortcut", "data": {"shortcut_name": "Razorpay Transactions", "col": 3}},
		{"id": "zv-sc-5", "type": "shortcut", "data": {"shortcut_name": "Products", "col": 3}},
		{"id": "zv-sc-6", "type": "shortcut", "data": {"shortcut_name": "Website Users", "col": 3}},
		{"id": "zv-sc-7", "type": "shortcut", "data": {"shortcut_name": "Return Requests", "col": 3}},
		{"id": "zv-sc-8", "type": "shortcut", "data": {"shortcut_name": "Coupon Codes", "col": 3}},
	]

	shortcuts = [
		{"type": "DocType", "link_to": "Sales Order", "label": "Sales Orders"},
		{"type": "DocType", "link_to": "Sales Invoice", "label": "Sales Invoices"},
		{"type": "DocType", "link_to": "Payment Entry", "label": "Payment Entries"},
		{"type": "DocType", "link_to": "Razorpay Transaction", "label": "Razorpay Transactions"},
		{"type": "DocType", "link_to": "Product", "label": "Products"},
		{"type": "DocType", "link_to": "Website User", "label": "Website Users"},
		{"type": "DocType", "link_to": "Return Request", "label": "Return Requests"},
		{"type": "DocType", "link_to": "Coupon Code", "label": "Coupon Codes"},
	]

	frappe.get_doc(
		{
			"doctype": "Workspace",
			"name": "Zenvora",
			"label": "Zenvora",
			"title": "Zenvora",
			"type": "Workspace",
			"module": "Zenvora",
			"public": 1,
			"is_hidden": 0,
			"sequence_id": 99,
			"content": json.dumps(content),
			"shortcuts": shortcuts,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
