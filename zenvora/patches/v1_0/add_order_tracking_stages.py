# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Sales Order": [
				{
					"fieldname": "zenvora_stage_section",
					"fieldtype": "Section Break",
					"label": "Fulfillment Timeline",
					"insert_after": "delivery_date",
					"collapsible": 1,
				},
				{
					"fieldname": "confirmed_at",
					"fieldtype": "Datetime",
					"label": "Confirmed At",
					"insert_after": "zenvora_stage_section",
					"read_only": 1,
				},
				{
					"fieldname": "packed_at",
					"fieldtype": "Datetime",
					"label": "Packed At",
					"insert_after": "confirmed_at",
				},
				{
					"fieldname": "zenvora_stage_column_break",
					"fieldtype": "Column Break",
					"insert_after": "packed_at",
				},
				{
					"fieldname": "shipped_at",
					"fieldtype": "Datetime",
					"label": "Shipped At",
					"insert_after": "zenvora_stage_column_break",
				},
				{
					"fieldname": "out_for_delivery_at",
					"fieldtype": "Datetime",
					"label": "Out For Delivery At",
					"insert_after": "shipped_at",
				},
				{
					"fieldname": "delivered_at",
					"fieldtype": "Datetime",
					"label": "Delivered At",
					"insert_after": "out_for_delivery_at",
					"read_only": 1,
				},
			]
		},
		update=True,
	)
