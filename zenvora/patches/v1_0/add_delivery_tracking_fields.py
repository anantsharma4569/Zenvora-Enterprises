# Copyright (c) 2026, Anant Sharma and contributors
# For license information, please see license.txt

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Delivery Note": [
				{
					"fieldname": "zenvora_tracking_section",
					"fieldtype": "Section Break",
					"label": "Shipment Tracking",
					"insert_after": "transporter_name",
				},
				{
					"fieldname": "courier_name",
					"fieldtype": "Data",
					"label": "Courier Name",
					"insert_after": "zenvora_tracking_section",
				},
				{
					"fieldname": "tracking_no",
					"fieldtype": "Data",
					"label": "Tracking No",
					"insert_after": "courier_name",
				},
				{
					"fieldname": "zenvora_tracking_column_break",
					"fieldtype": "Column Break",
					"insert_after": "tracking_no",
				},
				{
					"fieldname": "tracking_url",
					"fieldtype": "Data",
					"label": "Tracking URL",
					"insert_after": "zenvora_tracking_column_break",
				},
			]
		},
		update=True,
	)
