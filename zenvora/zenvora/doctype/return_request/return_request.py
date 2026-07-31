import frappe
from frappe import _
from frappe.model.document import Document


class ReturnRequest(Document):
	def on_update(self):
		if self.status == "Approved" and not self.razorpay_refund_id:
			self.process_refund()

	def process_refund(self):
		"""Trigger a Razorpay refund for the original payment once staff approve
		the return. Runs as part of the Approved status transition — see
		on_update above. Any failure here is logged and re-raised so the
		status change itself doesn't silently succeed without a refund."""
		from zenvora.api.razorpay_payment import _get_client

		txn = frappe.get_doc("Razorpay Transaction", {"sales_order": self.sales_order, "status": "Captured"})
		if not txn.razorpay_payment_id:
			frappe.throw(_("No captured payment found for this order to refund"))

		try:
			refund = _get_client().payment.refund(
				txn.razorpay_payment_id, {"amount": int(round(txn.amount * 100))}
			)
		except Exception:
			frappe.log_error(title=f"Razorpay refund failed for {self.sales_order}")
			frappe.throw(_("Refund could not be processed. Please try again or refund manually in Razorpay."))

		self.db_set("razorpay_refund_id", refund.get("id"))
		self.db_set("refund_amount", txn.amount)
		self.db_set("status", "Refunded")

		txn.status = "Refunded"
		txn.save(ignore_permissions=True)
