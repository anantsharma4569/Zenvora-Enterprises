import frappe
from frappe.model.document import Document

from zenvora.website_user_utils import get_or_create_website_user


class WishlistItem(Document):
	def before_insert(self):
		if not self.user:
			self.user = frappe.session.user
		if not self.website_user:
			self.website_user = get_or_create_website_user(self.user).name
