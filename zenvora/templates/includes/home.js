// home.js — nav dropdown, search, category filter, quick add-to-bag for the storefront home page

(function () {
	var productCards = document.querySelectorAll(".zv-product-card");
	var emptyFiltered = document.getElementById("zv-empty-filtered");
	var searchInput = document.getElementById("zv-search-input");
	var categoryPills = document.querySelectorAll("#zv-categories-filter .zv-category-pill");

	var state = { category: "all", search: "" };

	function applyFilters() {
		var visibleCount = 0;
		productCards.forEach(function (card) {
			var matchesCategory = state.category === "all" || card.dataset.category === state.category;
			var matchesSearch = !state.search || card.dataset.name.indexOf(state.search) !== -1;
			var match = matchesCategory && matchesSearch;
			card.classList.toggle("hide", !match);
			if (match) visibleCount++;
		});
		if (emptyFiltered) {
			emptyFiltered.classList.toggle("hide", visibleCount !== 0 || productCards.length === 0);
		}
	}

	function selectCategory(category) {
		state.category = category;
		categoryPills.forEach(function (p) {
			p.classList.toggle("is-active", p.dataset.category === category);
		});
		applyFilters();
		document.getElementById("zv-shop").scrollIntoView({ behavior: "smooth", block: "start" });
	}

	categoryPills.forEach(function (pill) {
		pill.addEventListener("click", function () {
			selectCategory(pill.dataset.category);
		});
	});

	// Category dropdown links + category image cards both drive the same filter
	document.querySelectorAll(".zv-category-link, .zv-category-card").forEach(function (el) {
		el.addEventListener("click", function (e) {
			e.preventDefault();
			selectCategory(el.dataset.category);
		});
	});

	var saleLink = document.getElementById("zv-sale-link");
	if (saleLink) {
		saleLink.addEventListener("click", function (e) {
			e.preventDefault();
			state.category = "all";
			categoryPills.forEach(function (p) {
				p.classList.toggle("is-active", p.dataset.category === "all");
			});
			productCards.forEach(function (card) {
				var onSale = !!card.querySelector(".zv-sale-badge");
				card.classList.toggle("hide", !onSale);
			});
			if (emptyFiltered) {
				var anyVisible = document.querySelectorAll(".zv-product-card:not(.hide)").length > 0;
				emptyFiltered.classList.toggle("hide", anyVisible);
			}
			document.getElementById("zv-shop").scrollIntoView({ behavior: "smooth", block: "start" });
		});
	}

	if (searchInput) {
		searchInput.addEventListener("input", function () {
			state.search = searchInput.value.trim().toLowerCase();
			applyFilters();
		});
	}

	// --- Categories nav dropdown ---
	var dropdown = document.querySelector(".zv-nav-dropdown");
	if (dropdown) {
		var toggle = dropdown.querySelector(".zv-nav-dropdown-toggle");
		toggle.addEventListener("click", function (e) {
			e.stopPropagation();
			dropdown.classList.toggle("is-open");
		});
		document.addEventListener("click", function () {
			dropdown.classList.remove("is-open");
		});
	}

	// --- Wishlist (not yet implemented as a real feature) ---
	var wishlistBtn = document.querySelector(".zv-wishlist-btn");
	if (wishlistBtn) {
		wishlistBtn.addEventListener("click", function () {
			frappe.show_alert({ message: "{{ _("Wishlist is coming soon!") }}", indicator: "blue" });
		});
	}

	// --- Quick add to bag ---
	document.querySelectorAll(".zv-product-add").forEach(function (btn) {
		btn.addEventListener("click", function (e) {
			e.preventDefault();

			if ({{ frappe.session.user | tojson }} === "Guest") {
				window.location.href = "/login?redirect-to=" + encodeURIComponent(window.location.pathname);
				return;
			}

			btn.disabled = true;
			frappe.call({
				method: "zenvora.api.cart.add_to_cart",
				args: { product: btn.dataset.product, qty: 1 },
				callback: function (r) {
					var count = (r.message || []).reduce(function (sum, item) {
						return sum + (item.qty || 0);
					}, 0);
					var badge = document.getElementById("zv-cart-count");
					if (badge) {
						badge.textContent = count;
						badge.classList.remove("hide");
					}
					frappe.show_alert({ message: "{{ _('Added to bag') }}", indicator: "green" });
				},
				error: function () {
					frappe.show_alert({ message: "{{ _('Could not add to bag. Please try again.') }}", indicator: "red" });
				},
				always: function () {
					btn.disabled = false;
				},
			});
		});
	});

	// --- Newsletter (cosmetic only, no backend yet) ---
	var joinBtn = document.getElementById("zv-newsletter-join");
	if (joinBtn) {
		joinBtn.addEventListener("click", function () {
			var input = document.querySelector(".zv-newsletter-input");
			if (!input.value || !input.value.includes("@")) {
				frappe.show_alert({ message: "{{ _('Please enter a valid email') }}", indicator: "red" });
				return;
			}
			input.value = "";
			frappe.show_alert({ message: "{{ _("Thanks — we'll be in touch!") }}", indicator: "green" });
		});
	}
})();
