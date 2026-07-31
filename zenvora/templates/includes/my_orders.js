// my_orders.js — tab filtering + review modal for /my-orders

(function () {
	var tabs = document.querySelectorAll(".zv-tab");
	var cards = document.querySelectorAll(".zv-order-card");
	var emptyFiltered = document.getElementById("zv-empty-filtered");

	function applyFilter(filter) {
		var visibleCount = 0;
		cards.forEach(function (card) {
			var match = filter === "all" || card.dataset.status === filter;
			card.classList.toggle("hide", !match);
			if (match) visibleCount++;
		});
		if (emptyFiltered) {
			emptyFiltered.classList.toggle("hide", visibleCount !== 0 || cards.length === 0);
		}
	}

	tabs.forEach(function (tab) {
		tab.addEventListener("click", function () {
			tabs.forEach(function (t) {
				t.classList.remove("is-active");
				t.setAttribute("aria-selected", "false");
			});
			tab.classList.add("is-active");
			tab.setAttribute("aria-selected", "true");
			applyFilter(tab.dataset.filter);
		});
	});

	// --- Review modal ---
	var modal = document.getElementById("zv-review-modal");
	var starPicker = document.getElementById("zv-star-picker");
	var stars = starPicker ? starPicker.querySelectorAll(".zv-star") : [];
	var titleInput = document.getElementById("zv-review-title");
	var textInput = document.getElementById("zv-review-text");
	var errorEl = document.getElementById("zv-review-error");
	var productNameEl = document.getElementById("zv-review-product-name");
	var submitBtn = document.getElementById("zv-review-submit");

	var currentProduct = null;
	var currentOrder = null;

	function setRating(value) {
		starPicker.dataset.rating = value;
		stars.forEach(function (star) {
			star.classList.toggle("is-filled", Number(star.dataset.value) <= value);
		});
	}

	function openModal(product, order, productName) {
		currentProduct = product;
		currentOrder = order;
		productNameEl.textContent = productName || "";
		titleInput.value = "";
		textInput.value = "";
		errorEl.classList.add("hide");
		setRating(0);
		modal.classList.remove("hide");
	}

	function closeModal() {
		modal.classList.add("hide");
		currentProduct = null;
		currentOrder = null;
	}

	document.querySelectorAll(".zv-btn-review").forEach(function (btn) {
		btn.addEventListener("click", function () {
			openModal(btn.dataset.product, btn.dataset.order, btn.dataset.productName);
		});
	});

	stars.forEach(function (star) {
		star.addEventListener("click", function () {
			setRating(Number(star.dataset.value));
		});
	});

	var closeBtn = document.getElementById("zv-review-modal-close");
	var cancelBtn = document.getElementById("zv-review-cancel");
	if (closeBtn) closeBtn.addEventListener("click", closeModal);
	if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
	if (modal) {
		modal.addEventListener("click", function (e) {
			if (e.target === modal) closeModal();
		});
	}

	if (submitBtn) {
		submitBtn.addEventListener("click", function () {
			var rating = Number(starPicker.dataset.rating || 0);
			if (!rating) {
				errorEl.textContent = "{{ _('Please select a star rating') }}";
				errorEl.classList.remove("hide");
				return;
			}

			submitBtn.disabled = true;
			frappe.call({
				method: "zenvora.api.reviews.submit_review",
				args: {
					product: currentProduct,
					rating: rating,
					review_title: titleInput.value,
					review_text: textInput.value,
					sales_order: currentOrder,
				},
				callback: function () {
					closeModal();
					frappe.show_alert({ message: "{{ _('Review submitted — thank you!') }}", indicator: "green" });
				},
				error: function () {
					errorEl.textContent = "{{ _('Something went wrong. Please try again.') }}";
					errorEl.classList.remove("hide");
				},
				always: function () {
					submitBtn.disabled = false;
				},
			});
		});
	}
})();
