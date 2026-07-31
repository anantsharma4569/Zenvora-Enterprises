import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class WalletTransaction(Document):
	def before_insert(self):
		website_user = frappe.get_doc("Website User", self.website_user)
		current = flt(website_user.wallet_balance)
		delta = flt(self.amount) if self.type == "Credit" else -flt(self.amount)
		new_balance = current + delta
		if new_balance < 0:
			frappe.throw(_("Insufficient wallet balance"))
		self.balance_after = new_balance

	def on_update(self):
		frappe.db.set_value("Website User", self.website_user, "wallet_balance", self.balance_after)
