import hashlib
import hmac
import json

import frappe
import razorpay
from frappe import _
from frappe.utils import flt, today

from zenvora.website_user_utils import get_or_create_website_user

MODE_OF_PAYMENT = "Razorpay"


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first"), frappe.AuthenticationError)


def _get_credentials():
	settings = frappe.get_single("Zenvora Settings")
	key_id = settings.razorpay_key_id
	key_secret = settings.get_password("razorpay_key_secret", raise_exception=False)
	if not key_id or not key_secret:
		frappe.throw(_("Razorpay is not configured. Set the Key ID and Key Secret in Zenvora Settings."))
	return key_id, key_secret


def _get_webhook_secret():
	return frappe.get_single("Zenvora Settings").get_password(
		"razorpay_webhook_secret", raise_exception=False
	)


def _get_client():
	key_id, key_secret = _get_credentials()
	return razorpay.Client(auth=(key_id, key_secret))


@frappe.whitelist(methods=["POST"])
def create_razorpay_order(sales_order_id):
	"""Create a Razorpay Order for an existing Draft Sales Order and log the attempt."""
	_require_login()

	so = frappe.get_doc("Sales Order", sales_order_id)

	website_user = get_or_create_website_user(frappe.session.user)
	if not website_user.customer or so.customer != website_user.customer:
		frappe.throw(_("You are not permitted to pay for this order"), frappe.PermissionError)

	if so.docstatus == 2:
		frappe.throw(_("This order has been cancelled"))
	if flt(so.per_billed) >= 100:
		frappe.throw(_("This order has already been paid"))

	key_id, _secret = _get_credentials()
	amount_in_paise = int(round(flt(so.grand_total) * 100))

	from zenvora.api.payment_methods import get_or_create_razorpay_customer_id

	razorpay_customer_id = get_or_create_razorpay_customer_id(website_user)

	try:
		razorpay_order = _get_client().order.create(
			{
				"amount": amount_in_paise,
				"currency": so.currency or "INR",
				"receipt": so.name,
				"notes": {"sales_order": so.name, "user": frappe.session.user},
			}
		)
	except Exception:
		frappe.log_error(title="Razorpay order creation failed")
		frappe.throw(_("Could not initiate payment. Please try again."))

	frappe.get_doc(
		{
			"doctype": "Razorpay Transaction",
			"razorpay_order_id": razorpay_order["id"],
			"status": "Created",
			"amount": so.grand_total,
			"website_user": website_user.name,
			"customer": so.customer,
			"sales_order": so.name,
			"raw_response": frappe.as_json(razorpay_order),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"razorpay_order_id": razorpay_order["id"],
		"amount": amount_in_paise,
		"currency": razorpay_order.get("currency", "INR"),
		"key_id": key_id,
		"customer_id": razorpay_customer_id,
	}


def _verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature, key_secret):
	payload = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
	expected = hmac.new(key_secret.encode(), payload, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, razorpay_signature or "")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
	"""Called by the frontend right after Razorpay Checkout succeeds. Verifies
	the signature, then submits the Sales Order and generates the Sales
	Invoice + Payment Entry. Also reachable idempotently from the webhook."""
	txn_name = frappe.db.get_value("Razorpay Transaction", {"razorpay_order_id": razorpay_order_id}, "name")
	if not txn_name:
		frappe.throw(_("Unknown Razorpay order"))

	txn = frappe.get_doc("Razorpay Transaction", txn_name)

	if txn.status == "Captured":
		# Already finalized (e.g. the webhook beat the frontend to it) — idempotent no-op.
		return {
			"success": True,
			"message": _("Payment already verified"),
			"sales_order": txn.sales_order,
			"sales_invoice": txn.sales_invoice,
			"payment_entry": txn.payment_entry,
		}

	_key_id, key_secret = _get_credentials()

	if not _verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature, key_secret):
		txn.status = "Failed"
		txn.razorpay_payment_id = razorpay_payment_id
		txn.razorpay_signature = razorpay_signature
		txn.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("Payment verification failed"), frappe.ValidationError)

	txn.razorpay_signature = razorpay_signature

	try:
		payment = _get_client().payment.fetch(razorpay_payment_id)
		result = _finalize_payment(txn, razorpay_payment_id, payment)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Razorpay payment finalization failed for {razorpay_order_id}")
		txn.reload()
		txn.status = "Failed"
		txn.razorpay_payment_id = razorpay_payment_id
		txn.razorpay_signature = razorpay_signature
		txn.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("Payment received but order finalization failed. Our team has been notified."))

	return result


def _finalize_payment(txn, razorpay_payment_id, payment):
	"""Submit the Sales Order, generate + submit the Sales Invoice, generate +
	submit the Payment Entry, and update the Razorpay Transaction log.
	`payment` is the Razorpay payment entity dict (already fetched by the caller).

	Submitting orders, raising invoices, and posting payments are privileged
	accounting operations a customer's Website User role has no business
	doing directly — the verified Razorpay signature (checked by the caller)
	is the actual authorization here, not doctype permissions. So this runs
	as Administrator, scoped tightly to just this block."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

	current_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		so = frappe.get_doc("Sales Order", txn.sales_order)
		if so.docstatus == 0:
			so.submit()
		so.db_set("confirmed_at", frappe.utils.now_datetime())

		si = make_sales_invoice(so.name)
		si.insert()
		si.submit()

		default_account = frappe.db.get_value(
			"Mode of Payment Account", {"parent": MODE_OF_PAYMENT, "company": si.company}, "default_account"
		)
		if not default_account:
			frappe.throw(
				_("Mode of Payment {0} has no default account configured for company {1}").format(
					MODE_OF_PAYMENT, si.company
				)
			)

		pe = get_payment_entry("Sales Invoice", si.name)
		pe.mode_of_payment = MODE_OF_PAYMENT
		pe.paid_to = default_account
		pe.reference_no = razorpay_payment_id
		pe.reference_date = today()
		pe.insert()
		pe.submit()

		txn.status = "Captured"
		txn.razorpay_payment_id = razorpay_payment_id
		txn.method = payment.get("method")
		txn.sales_invoice = si.name
		txn.payment_entry = pe.name
		txn.raw_response = frappe.as_json(payment)
		txn.save()

		notify_user = txn.website_user and frappe.db.get_value("Website User", txn.website_user, "user")
		if notify_user:
			frappe.get_doc(
				{
					"doctype": "Zenvora Notification",
					"user": notify_user,
					"title": _("Order confirmed"),
					"message": _("Your order {0} has been confirmed and is being prepared.").format(so.name),
					"reference_doctype": "Sales Order",
					"reference_name": so.name,
				}
			).insert()

		frappe.db.commit()
	finally:
		frappe.set_user(current_user)

	# Best-effort saved-card sync. Runs as the actual account owner (from
	# txn.website_user), not whatever `current_user` was — that's "Guest" when
	# this is reached via the webhook rather than the frontend's verify call.
	target_user = txn.website_user and frappe.db.get_value("Website User", txn.website_user, "user")
	if target_user and target_user != "Guest":
		try:
			from zenvora.api.payment_methods import sync_saved_payment_methods

			frappe.set_user(target_user)
			sync_saved_payment_methods()
		except Exception:
			frappe.log_error(title=f"Saved payment method sync failed for {txn.name}")
		finally:
			frappe.set_user(current_user)

	return {
		"success": True,
		"message": _("Payment successful"),
		"sales_order": so.name,
		"sales_invoice": si.name,
		"payment_entry": pe.name,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook_handler():
	"""Async notifications from Razorpay (payment.captured / payment.failed).
	Configure this URL under Razorpay Dashboard > Webhooks. Idempotent with
	respect to verify_razorpay_payment — whichever arrives first finalizes
	the transaction, the other is a no-op."""
	webhook_secret = _get_webhook_secret()
	if not webhook_secret:
		frappe.local.response["http_status_code"] = 500
		return {"status": "webhook secret not configured"}

	raw_body = frappe.request.get_data(as_text=True)
	received_signature = frappe.get_request_header("X-Razorpay-Signature")

	expected_signature = hmac.new(webhook_secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
	if not hmac.compare_digest(expected_signature, received_signature or ""):
		frappe.local.response["http_status_code"] = 400
		return {"status": "invalid signature"}

	payload = json.loads(raw_body)
	event = payload.get("event")

	if event == "payment.captured":
		_handle_webhook_captured(payload)
	elif event == "payment.failed":
		_handle_webhook_failed(payload)

	return {"status": "ok"}


def _handle_webhook_captured(payload):
	entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
	order_id = entity.get("order_id")
	if not order_id:
		return

	txn_name = frappe.db.get_value("Razorpay Transaction", {"razorpay_order_id": order_id}, "name")
	if not txn_name:
		frappe.log_error(title=f"Razorpay webhook: unknown order {order_id}")
		return

	txn = frappe.get_doc("Razorpay Transaction", txn_name)
	if txn.status == "Captured":
		return  # already finalized via the frontend's verify_razorpay_payment call

	try:
		_finalize_payment(txn, entity.get("id"), entity)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Razorpay webhook finalize failed for {order_id}")


def _handle_webhook_failed(payload):
	entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
	order_id = entity.get("order_id")
	if not order_id:
		return

	frappe.db.set_value(
		"Razorpay Transaction",
		{"razorpay_order_id": order_id, "status": ["!=", "Captured"]},
		{"status": "Failed", "raw_response": frappe.as_json(entity)},
	)
	frappe.db.commit()
