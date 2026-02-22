

(function () {
  // =========================
  // ✅ Safe template data
  // =========================
  const dataEl = document.getElementById("menuData");
  if (!dataEl) console.error((window.gettext ? window.gettext("menuData missing: URLs will be undefined.") : "menuData missing: URLs will be undefined."));

  const URLS = dataEl
    ? {
        cart_summary: dataEl.dataset.cartSummary,
        cart_update: dataEl.dataset.cartUpdate,
        cart_add: dataEl.dataset.cartAdd,
        apply_coupon: dataEl.dataset.applyCoupon,
        remove_coupon: dataEl.dataset.removeCoupon,
        calc: dataEl.dataset.calc,
        location_partial: dataEl.dataset.locationPartial,
        set_location: dataEl.dataset.setLocation,
        checkout: dataEl.dataset.checkout,
      }
    : {};

  const GOOGLE_MAPS_API_KEY = dataEl ? dataEl.dataset.gmapsKey || "" : "";

  // =========================
  // Helpers
  // =========================
  const _ = (window.gettext ? window.gettext : (s) => s);

  function csrfToken() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  function money(n) {
    return "€ " + (Number(n) || 0).toFixed(2);
  }

  function xhrHeaders(extra) {
    return Object.assign(
      { "X-Requested-With": "XMLHttpRequest" },
      extra || {}
    );
  }

    // ✅ ✅ PUT IT RIGHT HERE (after helpers)
  const AUTO_OPEN_KEY = "delivery_cart_drawer_opened_once";
  function hasAutoOpenedOnce() {
    try { return localStorage.getItem(AUTO_OPEN_KEY) === "1"; } catch (e) { return false; }
  }
  function markAutoOpenedOnce() {
    try { localStorage.setItem(AUTO_OPEN_KEY, "1"); } catch (e) {}
  }

  // =========================
  // Category rail arrows
  // =========================
  const rail = document.getElementById("catRail");
  const prev = document.getElementById("catPrev");
  const next = document.getElementById("catNext");
  if (rail && prev && next) {
    const step = () => Math.max(220, Math.floor(rail.clientWidth * 0.65));
    prev.addEventListener("click", () =>
      rail.scrollBy({ left: -step(), behavior: "smooth" })
    );
    next.addEventListener("click", () =>
      rail.scrollBy({ left: step(), behavior: "smooth" })
    );
  }

  // =========================
  // Scrollspy pills
  // =========================
  const pillMap = new Map();
  document.querySelectorAll("[data-cat-pill]").forEach((p) => {
    pillMap.set(p.getAttribute("data-cat-pill"), p);
  });

  function setActivePill(slug) {
    document
      .querySelectorAll(".cat-pill.is-active")
      .forEach((el) => el.classList.remove("is-active"));
    const pill = pillMap.get(slug);
    if (pill) pill.classList.add("is-active");
  }

  const sections = Array.from(document.querySelectorAll("[data-cat-section]"));
  if (sections.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((en) => en.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (visible.length) {
          const slug = visible[0].target.getAttribute("data-cat-section");
          if (slug) setActivePill(slug);
        } else {
          const topEl = document.getElementById("top");
          if (topEl) {
            const r = topEl.getBoundingClientRect();
            if (r.top >= 0 && r.top < 200) setActivePill("__all__");
          }
        }
      },
      {
        root: null,
        rootMargin: "-140px 0px -60% 0px",
        threshold: [0.1, 0.25, 0.4, 0.6],
      }
    );

    sections.forEach((s) => observer.observe(s));
  }

  // =========================
  // Mobile cart drawer
  // =========================
  const mobileCartRoot = document.getElementById("mobileCart");
  const mobileCartPanel = document.getElementById("mobileCartPanel");
  const mobileBackdrop = document.getElementById("mobileCartBackdrop");
  const closeMobileCart = document.getElementById("closeMobileCart");
  const openMobileCartBarBtn = document.getElementById("openMobileCartBarBtn");

  function openDrawer() {
    if (!mobileCartRoot || !mobileCartPanel) return;
    mobileCartRoot.classList.remove("hidden");
    requestAnimationFrame(() =>
      mobileCartPanel.classList.remove("translate-x-full")
    );
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    if (!mobileCartRoot || !mobileCartPanel) return;
    mobileCartPanel.classList.add("translate-x-full");
    setTimeout(() => {
      mobileCartRoot.classList.add("hidden");
      document.body.style.overflow = "";
    }, 220);
  }

  if (openMobileCartBarBtn)
    openMobileCartBarBtn.addEventListener("click", openDrawer);
  if (closeMobileCart)
    closeMobileCart.addEventListener("click", closeDrawer);
  if (mobileBackdrop) mobileBackdrop.addEventListener("click", closeDrawer);

  // =========================
  // Item modal
  // =========================
  const itemModal = document.getElementById("itemModal");
  const itemModalBackdrop = document.getElementById("itemModalBackdrop");
  const itemModalClose = document.getElementById("itemModalClose");
  const itemModalBody = document.getElementById("itemModalBody");

  function openItemModal() {
    if (!itemModal) return;
    itemModal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeItemModal() {
    if (!itemModal) return;
    itemModal.classList.add("hidden");
    document.body.style.overflow = "";
  }

  if (itemModalBackdrop)
    itemModalBackdrop.addEventListener("click", closeItemModal);
  if (itemModalClose) itemModalClose.addEventListener("click", closeItemModal);

  // =========================
  // Cart state helpers
  // =========================
  function getQtyFromLastCartSnapshot(itemId) {
    try {
      const cart = window.__LAST_CART__;
      if (!cart || !Array.isArray(cart.lines)) return 0;
      const line = cart.lines.find((l) => String(l.id) === String(itemId));
      return line ? Number(line.qty || 0) : 0;
    } catch (e) {
      return 0;
    }
  }

  function syncModalQtyUI(itemId) {
    const meta = document.getElementById("modalItemMeta");
    if (!meta) return;

    const openItemId = meta.getAttribute("data-item-id");
    if (String(openItemId) !== String(itemId)) return;

    const qty = getQtyFromLastCartSnapshot(itemId);

    const addBtn = document.getElementById("modalAddBtn");
    const controls = document.getElementById("modalQtyControls");
    const qtyEl = document.getElementById("modalQtyValue");

    if (qtyEl) qtyEl.textContent = qty;

    if (qty > 0) {
      if (controls) controls.classList.remove("hidden");
      if (addBtn) addBtn.classList.add("hidden");
    } else {
      if (controls) controls.classList.add("hidden");
      if (addBtn) addBtn.classList.remove("hidden");
    }
  }

  function applySelectedQuantities(qtyById) {
    document.querySelectorAll("[data-menu-card]").forEach((card) => {
      card.classList.remove("ring-2", "ring-[#1f6feb]/40");
      const badge = card.querySelector("[data-qty-badge]");
      if (badge) badge.classList.add("hidden");
    });

    Object.keys(qtyById).forEach((id) => {
      const card = document.querySelector(
        `[data-menu-card][data-item-id="${id}"]`
      );
      if (!card) return;

      card.classList.add("ring-2", "ring-[#1f6feb]/40");
      const badge = card.querySelector("[data-qty-badge]");
      if (badge) {
        badge.textContent = qtyById[id];
        badge.classList.remove("hidden");
      }
    });
  }

  // =========================
  // ✅ Coupon price preview
  // =========================
  let couponState = { active: false, discount_type: null, discount_value: null };

  function setCouponStateFromCart(cart) {
    if (!cart || typeof cart !== "object") return;

    // keep state safe: only update when field exists
    const hasCouponField = Object.prototype.hasOwnProperty.call(cart, "coupon");
    if (!hasCouponField) return;

    const c = cart.coupon; // could be null
    couponState.active = !!(c && c.active);
    couponState.discount_type = c ? (c.discount_type || c.type || null) : null;
    couponState.discount_value = c ? (c.discount_value || c.value || null) : null;
  }

  function applyCouponPricesToMenu() {
    const active =
      couponState.active &&
      String(couponState.discount_type || "").toLowerCase() === "percent" &&
      couponState.discount_value != null;

    const pct = active ? Number(couponState.discount_value) : 0;

    document.querySelectorAll("[data-menu-card]").forEach((card) => {
      const hasItemDiscount = card.getAttribute("data-has-item-discount") === "1";
      const basePrice = parseFloat(String(card.getAttribute("data-base-price") || "0").replace(",", ".")) || 0;

      const priceWrap = card.querySelector("[data-price-wrap]");
      if (!priceWrap) return;

      const normalEl = priceWrap.querySelector("[data-price-normal]");
      const strikeEl = priceWrap.querySelector("[data-price-strike]");
      const couponEl = priceWrap.querySelector("[data-price-coupon]");

      // reset
      if (normalEl) normalEl.classList.remove("hidden");
      if (strikeEl) strikeEl.classList.add("hidden");
      if (couponEl) couponEl.classList.add("hidden");

      // only show coupon preview if coupon active AND item has no item-level discount
      if (!active || hasItemDiscount) return;

      const discounted = basePrice * (1 - pct / 100);

      if (strikeEl && couponEl && normalEl) {
        strikeEl.textContent = money(basePrice);
        couponEl.textContent = money(discounted);

        strikeEl.classList.remove("hidden");
        couponEl.classList.remove("hidden");
        normalEl.classList.add("hidden");
      }
    });
  }

  function setEmptyHints(isEmpty) {
    const desktopHint = document.getElementById("cartEmptyHint");
    const mobileHint = document.getElementById("mobileCartEmptyHint");
    if (desktopHint) desktopHint.classList.toggle("hidden", !isEmpty);
    if (mobileHint) mobileHint.classList.toggle("hidden", !isEmpty);
  }

  function toggleClearButtons(hasItems) {
    const clearBtn = document.getElementById("clearCartBtn");
    const clearBtnMobile = document.getElementById("clearCartBtnMobile");
    if (clearBtn) clearBtn.classList.toggle("hidden", !hasItems);
    if (clearBtnMobile) clearBtnMobile.classList.toggle("hidden", !hasItems);
  }

  function setCouponUIFromCart(cart) {
  // desktop
  const couponMsg = document.getElementById("couponMessage");
  const discountRow = document.getElementById("discountRow");
  const cartDiscount = document.getElementById("cartDiscount");
  const removeBtn = document.getElementById("removeCouponBtn");

  // ✅ mobile (new)
  const mCouponMsg = document.getElementById("mobileCouponMessage");
  const mDiscountRow = document.getElementById("mobileDiscountRow");
  const mCartDiscount = document.getElementById("mobileCartDiscount");
  const mRemoveBtn = document.getElementById("mobileRemoveCouponBtn");

  const hasActiveCoupon = !!(cart && cart.coupon && cart.coupon.active);

  // toggle remove buttons (desktop + mobile)
  if (removeBtn) removeBtn.classList.toggle("hidden", !hasActiveCoupon);
  if (mRemoveBtn) mRemoveBtn.classList.toggle("hidden", !hasActiveCoupon);

  // Coupon messages (desktop + mobile)
  const msgText = (hasActiveCoupon && cart.coupon.code) ? (_("Coupon applied: ") + cart.coupon.code) : "";

  if (couponMsg) {
    if (msgText) {
      couponMsg.classList.remove("hidden");
      couponMsg.className = "text-xs mt-2 text-green-700";
      couponMsg.textContent = msgText;
    } else {
      couponMsg.classList.add("hidden");
    }
  }

  if (mCouponMsg) {
    if (msgText) {
      mCouponMsg.classList.remove("hidden");
      mCouponMsg.className = "text-xs mt-2 text-green-700";
      mCouponMsg.textContent = msgText;
    } else {
      mCouponMsg.classList.add("hidden");
    }
  }

  // Discount row (desktop + mobile) - non free_delivery
  const showDiscount =
    cart &&
    cart.coupon &&
    cart.coupon.active &&
    cart.coupon.discount_type !== "free_delivery";

  if (showDiscount) {
    if (discountRow) discountRow.classList.remove("hidden");
    if (cartDiscount) cartDiscount.textContent = "- " + money(cart.coupon_discount);

    if (mDiscountRow) mDiscountRow.classList.remove("hidden");
    if (mCartDiscount) mCartDiscount.textContent = "- " + money(cart.coupon_discount);
  } else {
    if (discountRow) discountRow.classList.add("hidden");
    if (mDiscountRow) mDiscountRow.classList.add("hidden");
  }

  // Free delivery badge (desktop only - keep your existing badge logic)
  const freeBadge = document.getElementById("freeDeliveryBadge");
  if (freeBadge) {
    const isFree = !!(
      cart &&
      cart.delivery_fee === 0 &&
      cart.coupon &&
      cart.coupon.discount_type === "free_delivery" &&
      cart.coupon.active
    );
    freeBadge.classList.toggle("hidden", !isFree);
  }
}


  function renderCartFromSnapshot(cart) {
    window.__LAST_CART__ = cart;

    setCouponStateFromCart(cart);

    const container = document.getElementById("cartItems");
    const mobile = document.getElementById("mobileCartItems");
    if (container) container.innerHTML = "";
    if (mobile) mobile.innerHTML = "";

    const qtyMap = {};
    const totalCount = (cart.lines || []).reduce(
      (acc, l) => acc + (l.qty || 0),
      0
    );

    const isEmpty = !cart.lines || cart.lines.length === 0;
    setEmptyHints(isEmpty);
    toggleClearButtons(!isEmpty);

    const countEl = document.getElementById("mobileCartCount");
    const totalBarEl = document.getElementById("mobileCartTotalBar");
    if (countEl) countEl.textContent = totalCount;
    if (totalBarEl) totalBarEl.textContent = money(cart.total);

    (cart.lines || []).forEach((line) => {
      qtyMap[String(line.id)] = line.qty;

      const row = `
        <div class="border-b border-[#3e2723]/10 pb-3" data-cart-row data-item-id="${line.id}">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="font-semibold text-[#3e2723] truncate">${line.name}</div>
              <div class="mt-2 flex items-center gap-2">
                <button type="button"
                        class="h-8 w-8 rounded-lg bg-[#f5f0e6] border border-[#3e2723]/10 text-[#3e2723] font-bold active:scale-95 transition"
                        data-qty-action="dec">−</button>

                <span class="min-w-[22px] text-center text-sm font-semibold text-[#3e2723]" data-qty-value>${line.qty}</span>

                <button type="button"
                        class="h-8 w-8 rounded-lg bg-[#f5f0e6] border border-[#3e2723]/10 text-[#3e2723] font-bold active:scale-95 transition"
                        data-qty-action="inc">+</button>

                <button type="button"
                        class="ml-2 text-xs font-semibold text-red-600 hover:underline underline-offset-4"
                        data-qty-action="remove">${_("Remove")}</button>
              </div>
            </div>
            <div class="shrink-0 text-right">
              <div class="text-[11px] uppercase tracking-wider text-[#3e2723]/50">${_("TOTAL")}</div>
              <div class="font-semibold text-[#3e2723]">${money(line.line_total)}</div>
            </div>
          </div>
        </div>
      `;

      if (container) container.insertAdjacentHTML("beforeend", row);
      if (mobile) mobile.insertAdjacentHTML("beforeend", row);
    });

    const subEl = document.getElementById("cartSubtotal");
    const delEl = document.getElementById("cartDelivery");
    const totEl = document.getElementById("cartTotal");

    // ✅ mobile breakdown elements (new)
    const mSubEl = document.getElementById("mobileCartSubtotal");
    const mDelEl = document.getElementById("mobileCartDelivery");
    const mTotEl = document.getElementById("mobileCartTotal");

    if (subEl) subEl.textContent = money(cart.subtotal);
    if (delEl) delEl.textContent = money(cart.delivery_fee);
    if (totEl) totEl.textContent = money(cart.total);

    // ✅ update mobile too
    if (mSubEl) mSubEl.textContent = money(cart.subtotal);
    if (mDelEl) mDelEl.textContent = money(cart.delivery_fee);
    if (mTotEl) mTotEl.textContent = money(cart.total);


    // ✅ coupon UI + remove button toggling
    setCouponUIFromCart(cart);

    applySelectedQuantities(qtyMap);
    applyCouponPricesToMenu();

    const meta = document.getElementById("modalItemMeta");
    if (meta) syncModalQtyUI(meta.getAttribute("data-item-id"));
  }

  // =========================
  // Cart API
  // =========================
  async function refreshCart() {
    if (!URLS.cart_summary) return;

    const res = await fetch(URLS.cart_summary, { headers: xhrHeaders() });
    if (!res.ok) return;

    const data = await res.json().catch(() => null);
    if (!data || !data.ok || !data.cart) return;

    renderCartFromSnapshot(data.cart);
  }

  window.updateQty = async function (id, qty) {
    if (!URLS.cart_update) return;

    const fd = new FormData();
    fd.append("item_id", id);
    fd.append("qty", qty);

    const res = await fetch(URLS.cart_update, {
      method: "POST",
      headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
      body: fd,
    });

    const data = await res.json().catch(() => null);
    if (data && data.ok && data.cart) {
      renderCartFromSnapshot(data.cart); // ✅ no extra GET
    } else {
      refreshCart();
    }
  };

  async function clearCart() {
    if (!URLS.cart_summary || !URLS.cart_update) return;

    const res = await fetch(URLS.cart_summary, { headers: xhrHeaders() });
    if (!res.ok) return;

    const data = await res.json().catch(() => null);
    if (!data || !data.ok || !data.cart) return;

    const lines = data.cart.lines || [];
    for (const line of lines) {
      const fd = new FormData();
      fd.append("item_id", line.id);
      fd.append("qty", 0);

      await fetch(URLS.cart_update, {
        method: "POST",
        headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
        body: fd,
      });
    }
    refreshCart();
  }

  // =========================
  // ✅ Google Maps loader
  // =========================
  async function ensureGoogleMaps() {
    if (window.google && window.google.maps) return true;
    if (window.__gmaps_loading_promise) return window.__gmaps_loading_promise;

    const API_KEY = GOOGLE_MAPS_API_KEY;
    if (!API_KEY) {
      console.error(_("Missing GOOGLE_MAPS_API_KEY."));
      alert(_("Google Maps API key missing."));
      return false;
    }

    window.__gmaps_loading_promise = new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-gmaps="1"]');
      if (existing) {
        if (window.google && window.google.maps) return resolve(true);
        existing.addEventListener("load", () => resolve(true), { once: true });
        existing.addEventListener("error", reject, { once: true });
        return;
      }

      const s = document.createElement("script");
      s.src =
        "https://maps.googleapis.com/maps/api/js?key=" +
        encodeURIComponent(API_KEY) +
        "&libraries=places";
      s.async = true;
      s.defer = true;
      s.setAttribute("data-gmaps", "1");
      s.onload = () => resolve(true);
      s.onerror = reject;
      document.head.appendChild(s);
    });

    try {
      await window.__gmaps_loading_promise;
      return !!(window.google && window.google.maps);
    } catch (e) {
      console.error(_("Google Maps failed to load"), e);
      alert(_("Google Maps failed to load. Check API key / restrictions."));
      return false;
    }
  }

  function destroyDlMap() {
    if (window.__gm_marker) {
      try {
        window.__gm_marker.setMap(null);
      } catch (e) {}
      window.__gm_marker = null;
    }
    window.__gm_map = null;

    const mapEl = document.getElementById("dlMap");
    if (mapEl) mapEl.innerHTML = "";
  }

  // =========================
  // Location modal flow
  // =========================
  const locationModal = document.getElementById("locationModal");
  const locationModalBackdrop = document.getElementById(
    "locationModalBackdrop"
  );
  const locationModalClose = document.getElementById("locationModalClose");
  const locationModalBody = document.getElementById("locationModalBody");

  function openLocationModal() {
    if (!locationModal) return;
    locationModal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeLocationModal() {
    if (!locationModal) return;
    locationModal.classList.add("hidden");
    document.body.style.overflow = "";
  }

  if (locationModalBackdrop)
    locationModalBackdrop.addEventListener("click", closeLocationModal);
  if (locationModalClose)
    locationModalClose.addEventListener("click", closeLocationModal);

  window.initDeliveryLocationModal = function (opts) {
    const setLocationUrl = opts.setLocationUrl;
    const checkoutUrl = opts.checkoutUrl;
    const csrf = opts.csrf;

    const mapEl = document.getElementById("dlMap");
    if (!mapEl) {
      console.error(_("dlMap element not found in partial HTML."));
      return;
    }

    const REST_LAT =
      parseFloat((mapEl.dataset.restLat || "0").replace(",", ".")) || 0;
    const REST_LNG =
      parseFloat((mapEl.dataset.restLng || "0").replace(",", ".")) || 0;

    const addrSearch = document.getElementById("dlAddrSearch");
    const gpsStatus = document.getElementById("dlGpsStatus");
    const accText = document.getElementById("dlAccText");

    const addrLabel = document.getElementById("dlAddrLabel");
    const latEl = document.getElementById("dlLat");
    const lngEl = document.getElementById("dlLng");
    const labelEl = document.getElementById("dlLabelHidden");

    const confirmBtn = document.getElementById("dlConfirmBtn");
    const confirmHint = document.getElementById("dlConfirmHint");

    const distanceText = document.getElementById("dlDistanceText");
    const feeText = document.getElementById("dlFeeText");
    const totalText = document.getElementById("dlTotalText");
    const rangeWarn = document.getElementById("dlRangeWarn");

    const useMyLocationBtn = document.getElementById("dlUseMyLocation");

    if (!confirmBtn || !useMyLocationBtn) {
      console.error(_("Some delivery modal elements are missing."));
      return;
    }

    let calcAbort = null;
    let hasValid = false;

    function setStatus(t, cls) {
      if (!gpsStatus) return;
      gpsStatus.textContent = t;
      gpsStatus.className = "font-semibold " + (cls || "");
    }

    function setConfirmEnabled(enabled, msg) {
      hasValid = !!enabled;
      confirmBtn.classList.toggle("opacity-50", !enabled);
      confirmBtn.classList.toggle("cursor-not-allowed", !enabled);
      if (confirmHint) {
        confirmHint.textContent =
          msg ||
          (enabled
            ? _("Location looks good. Confirm to continue.")
            : _("Select an address or drag the pin, then confirm."));
      }
    }

    function setHidden(lat, lng) {
      if (latEl) latEl.value = Number(lat).toFixed(6);
      if (lngEl) lngEl.value = Number(lng).toFixed(6);
    }

    function setLabel(txt) {
      if (addrLabel) addrLabel.textContent = txt || "—";
      if (labelEl) labelEl.value = txt || "";
    }

    async function calc(lat, lng) {
      try {
        if (!URLS.calc) return;

        if (calcAbort) calcAbort.abort();
        calcAbort = new AbortController();

        const fd = new FormData();
        fd.append("lat", lat);
        fd.append("lng", lng);

        const res = await fetch(URLS.calc, {
          method: "POST",
          headers: { "X-CSRFToken": csrf },
          body: fd,
          signal: calcAbort.signal,
        });

        if (!res.ok) return;

        const data = await res.json().catch(() => null);
        if (!data || !data.ok) return;

        if (distanceText)
          distanceText.textContent =
            Number(data.distance_km || 0).toFixed(2) + " km";
        if (feeText) feeText.textContent = "€ " + Number(data.delivery_fee || 0).toFixed(2);
        if (totalText)
          totalText.textContent =
            "€ " + Number(data.estimated_total || 0).toFixed(2);

        if (data.in_range) {
          if (rangeWarn) rangeWarn.classList.add("hidden");
          setConfirmEnabled(true, _("Location looks good. Confirm to continue."));
        } else {
          if (rangeWarn) rangeWarn.classList.remove("hidden");
          setConfirmEnabled(false, _("Outside delivery range. Move the pin closer."));
        }
      } catch (e) {
        // abort ok
      }
    }

    const geocoder = new google.maps.Geocoder();

    function reverseGeocode(lat, lng) {
      geocoder.geocode({ location: { lat, lng } }, (results, status) => {
        if (status === "OK" && results && results[0]) {
          setLabel(results[0].formatted_address);
        } else {
          setLabel(_("Custom selected location"));
        }
      });
    }

    const map = new google.maps.Map(mapEl, {
      center: { lat: REST_LAT, lng: REST_LNG },
      zoom: 13,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
    });
    window.__gm_map = map;

    const marker = new google.maps.Marker({
      position: { lat: REST_LAT, lng: REST_LNG },
      map,
      draggable: true,
    });
    window.__gm_marker = marker;

    function setPoint(lat, lng, accMeters, center) {
      marker.setPosition({ lat, lng });
      if (center) map.setCenter({ lat, lng });

      setHidden(lat, lng);
      if (accText)
        accText.textContent =
          typeof accMeters === "number" ? "±" + Math.round(accMeters) + " m" : "—";

      reverseGeocode(lat, lng);
      calc(lat, lng);
    }

    marker.addListener("dragstart", () => setStatus(_("Pin adjust"), "text-[#bfa76f]"));
    marker.addListener("dragend", () => {
      const p = marker.getPosition();
      if (!p) return;
      setStatus(_("Pin set"), "text-[#bfa76f]");
      setPoint(p.lat(), p.lng(), null, false);
    });

    if (addrSearch) {
      const ac = new google.maps.places.Autocomplete(addrSearch, {
        fields: ["geometry", "formatted_address", "name"],
      });

      ac.addListener("place_changed", () => {
        const place = ac.getPlace();
        if (!place || !place.geometry || !place.geometry.location) {
          setConfirmEnabled(false, _("Select a valid address from suggestions."));
          return;
        }
        const lat = place.geometry.location.lat();
        const lng = place.geometry.location.lng();
        const label = place.formatted_address || place.name || _("Selected location");

        setStatus(_("Address selected"), "text-[#bfa76f]");
        setLabel(label);
        setPoint(lat, lng, null, true);
      });
    }

    useMyLocationBtn.addEventListener("click", () => {
      if (!navigator.geolocation) {
        alert(_("Geolocation not supported"));
        return;
      }

      setStatus(_("Locating…"), "text-[#bfa76f]");

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          const acc = pos.coords.accuracy;

          setStatus(_("Location detected"), "text-green-600");
          setPoint(lat, lng, acc, true);
        },
        () => {
          setStatus(_("Permission denied"), "text-red-600");
          alert(_("Location permission denied. Please search your address instead."));
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
      );
    });

    confirmBtn.addEventListener("click", async () => {
      if (!hasValid) return;

      const lat = latEl ? latEl.value : "";
      const lng = lngEl ? lngEl.value : "";
      const label =
        labelEl && labelEl.value
          ? labelEl.value
          : addrLabel
          ? addrLabel.textContent
          : "";

      const fd = new FormData();
      fd.append("lat", lat);
      fd.append("lng", lng);
      fd.append("address_label", (label || "").trim());

      await fetch(setLocationUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" },
        body: fd,
      });

      window.location.href = checkoutUrl;
    });

    setConfirmEnabled(false, _("Select an address or drag the pin, then confirm."));
    setStatus(_("Idle"), "text-[#3e2723]/70");
    setHidden(REST_LAT, REST_LNG);
    reverseGeocode(REST_LAT, REST_LNG);
    calc(REST_LAT, REST_LNG);

    setTimeout(() => google.maps.event.trigger(map, "resize"), 120);
  };

  async function loadLocationPartial() {
    if (!locationModalBody) return;
    if (!URLS.location_partial) {
      console.error(_("URLS.location_partial missing."));
      return;
    }

    locationModalBody.innerHTML = `<div class="p-6 text-[#3e2723]/70">${_("Loading...")}</div>`;

    const res = await fetch(URLS.location_partial, { headers: xhrHeaders() });
    locationModalBody.innerHTML = await res.text();

    const ok = await ensureGoogleMaps();
    if (!ok) return;

    requestAnimationFrame(() => {
      destroyDlMap();

      if (typeof window.initDeliveryLocationModal !== "function") {
        console.error(_("initDeliveryLocationModal missing."));
        alert(_("Map init missing. Check console."));
        return;
      }

      window.initDeliveryLocationModal({
        setLocationUrl: URLS.set_location,
        checkoutUrl: URLS.checkout,
        csrf: csrfToken(),
      });
    });
  }

  async function openCheckoutFlow() {
    const cart = window.__LAST_CART__;
    if (!cart || !cart.lines || cart.lines.length === 0) {
      alert(_("Your cart is empty."));
      return;
    }

    closeItemModal();
    openLocationModal();
    await loadLocationPartial();
  }

  const checkoutBtnDesktop = document.getElementById("checkoutBtnDesktop");
  const checkoutBtnMobile = document.getElementById("checkoutBtnMobile");

  if (checkoutBtnDesktop)
    checkoutBtnDesktop.addEventListener("click", openCheckoutFlow);
  if (checkoutBtnMobile)
    checkoutBtnMobile.addEventListener("click", async () => {
      closeDrawer();
      await openCheckoutFlow();
    });

  // =========================
  // Coupon apply (manual)
  // =========================
  const applyBtn = document.getElementById("applyCouponBtn");
  if (applyBtn) {
    applyBtn.addEventListener("click", async () => {
      if (!URLS.apply_coupon) return;

      const inputEl = document.getElementById("couponInput");
      const code = (inputEl?.value || "").trim();
      if (!code) return;

      const couponMsg = document.getElementById("couponMessage");
      if (couponMsg) {
        couponMsg.classList.remove("hidden");
        couponMsg.className = "text-xs mt-2 text-[#3e2723]/70";
        couponMsg.textContent = _("Applying coupon…");
      }

      const fd = new FormData();
      fd.append("coupon_code", code);

      const res = await fetch(URLS.apply_coupon, {
        method: "POST",
        headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
        body: fd,
      });

      const data = await res.json().catch(() => null);

      // ✅ If backend returns cart, render immediately (fast + correct remove button)
      if (data && data.ok && data.cart) {
        renderCartFromSnapshot(data.cart);
      } else {
        await refreshCart(); // fallback
      }

      // ✅ Menu preview should update even if cart is empty
      if (data && data.cart) {
        setCouponStateFromCart(data.cart);
        applyCouponPricesToMenu();
      }

      // message
      if (couponMsg) {
        if (res.ok && data && data.ok) {
          couponMsg.classList.remove("hidden");
          couponMsg.className = "text-xs mt-2 text-green-700";
          couponMsg.textContent =
            _("Coupon applied: ") + (data.cart?.coupon?.code || code);
        } else {
          couponMsg.classList.remove("hidden");
          couponMsg.className = "text-xs mt-2 text-red-700";
          couponMsg.textContent =
            (data && data.error) ? data.error : _("Invalid coupon.");
        }
      }
    });
  }

  // =========================
  // ✅ Coupon remove
  // =========================
  const removeCouponBtn = document.getElementById("removeCouponBtn");
  if (removeCouponBtn) {
    removeCouponBtn.addEventListener("click", async () => {
      if (!URLS.remove_coupon) return;

      const couponMsg = document.getElementById("couponMessage");
      if (couponMsg) {
        couponMsg.classList.remove("hidden");
        couponMsg.className = "text-xs mt-2 text-[#3e2723]/70";
        couponMsg.textContent = _("Removing coupon…");
      }

      const res = await fetch(URLS.remove_coupon, {
        method: "POST",
        headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
      });

      const data = await res.json().catch(() => null);

      // clear input
      const input = document.getElementById("couponInput");
      if (input) input.value = "";

      // reset preview immediately
      couponState = { active: false, discount_type: null, discount_value: null };
      applyCouponPricesToMenu();

      if (data && data.ok && data.cart) {
        renderCartFromSnapshot(data.cart);
      } else {
        await refreshCart();
      }

      // hide message after success
      if (couponMsg) couponMsg.classList.add("hidden");
    });
  }

  // =========================
// ✅ Mobile coupon buttons
// =========================
const mobileApplyCouponBtn = document.getElementById("mobileApplyCouponBtn");
if (mobileApplyCouponBtn) {
  mobileApplyCouponBtn.addEventListener("click", async () => {
    if (!URLS.apply_coupon) return;

    const inputEl = document.getElementById("mobileCouponInput");
    const code = (inputEl?.value || "").trim();
    if (!code) return;

    // sync desktop input also (optional)
    const desktopInput = document.getElementById("couponInput");
    if (desktopInput) desktopInput.value = code;

    const msg = document.getElementById("mobileCouponMessage");
    if (msg) {
      msg.classList.remove("hidden");
      msg.className = "text-xs mt-2 text-[#3e2723]/70";
      msg.textContent = _("Applying coupon…");
    }

    const fd = new FormData();
    fd.append("coupon_code", code);

    const res = await fetch(URLS.apply_coupon, {
      method: "POST",
      headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
      body: fd,
    });

    const data = await res.json().catch(() => null);

    if (data && data.ok && data.cart) renderCartFromSnapshot(data.cart);
    else await refreshCart();

    if (msg) {
      if (res.ok && data && data.ok) {
        msg.classList.remove("hidden");
        msg.className = "text-xs mt-2 text-green-700";
        msg.textContent = _("Coupon applied: ") + (data.cart?.coupon?.code || code);
      } else {
        msg.classList.remove("hidden");
        msg.className = "text-xs mt-2 text-red-700";
        msg.textContent = (data && data.error) ? data.error : _("Invalid coupon.");
      }
    }
  });
}

const mobileRemoveCouponBtn = document.getElementById("mobileRemoveCouponBtn");
if (mobileRemoveCouponBtn) {
  mobileRemoveCouponBtn.addEventListener("click", async () => {
    if (!URLS.remove_coupon) return;

    const msg = document.getElementById("mobileCouponMessage");
    if (msg) {
      msg.classList.remove("hidden");
      msg.className = "text-xs mt-2 text-[#3e2723]/70";
      msg.textContent = _("Removing coupon…");
    }

    const res = await fetch(URLS.remove_coupon, {
      method: "POST",
      headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
    });

    const data = await res.json().catch(() => null);

    // clear inputs (mobile + desktop)
    const mInput = document.getElementById("mobileCouponInput");
    if (mInput) mInput.value = "";
    const dInput = document.getElementById("couponInput");
    if (dInput) dInput.value = "";

    couponState = { active: false, discount_type: null, discount_value: null };
    applyCouponPricesToMenu();

    if (data && data.ok && data.cart) renderCartFromSnapshot(data.cart);
    else await refreshCart();

    if (msg) msg.classList.add("hidden");
  });
}


  // =========================
  // ✅ ONE delegated click handler
  // =========================
  document.addEventListener("click", async (e) => {
    // 0) Cart row +/- remove (desktop + mobile)
    const qtyBtn = e.target.closest("[data-qty-action]");
    if (qtyBtn) {
      const row = qtyBtn.closest("[data-cart-row]");
      if (!row) return;

      const id = row.getAttribute("data-item-id");
      const action = qtyBtn.getAttribute("data-qty-action");

      const current = getQtyFromLastCartSnapshot(id);

      if (action === "inc") return await window.updateQty(id, current + 1);
      if (action === "dec") return await window.updateQty(id, Math.max(0, current - 1));
      if (action === "remove") return await window.updateQty(id, 0);
      return;
    }

    // 1) Category pill smooth scroll
    const a = e.target.closest("a[data-cat-pill]");
    if (a) {
      const href = a.getAttribute("href") || "";
      if (href.startsWith("#")) {
        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
      return;
    }

    // 2) Modal +/-/remove
    if (
      e.target.closest("#modalPlusBtn") ||
      e.target.closest("#modalMinusBtn") ||
      e.target.closest("#modalRemoveBtn")
    ) {
      const meta = document.getElementById("modalItemMeta");
      if (!meta) return;

      const itemId = meta.getAttribute("data-item-id");
      const current = getQtyFromLastCartSnapshot(itemId);

      if (e.target.closest("#modalPlusBtn")) {
        await window.updateQty(itemId, current + 1);
        return;
      }
      if (e.target.closest("#modalMinusBtn")) {
        await window.updateQty(itemId, Math.max(0, current - 1));
        return;
      }
      if (e.target.closest("#modalRemoveBtn")) {
        await window.updateQty(itemId, 0);
        return;
      }
    }

    // 3) Add delivery (+ button and modal Add button)
    const addBtn = e.target.closest("[data-add-delivery]");
    if (addBtn) {
      if (!URLS.cart_add) return;

      const id = addBtn.getAttribute("data-add-delivery");
      const fd = new FormData();
      fd.append("item_id", id);
      fd.append("qty", 1);

      await fetch(URLS.cart_add, {
        method: "POST",
        headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
        body: fd,
      });

      await refreshCart();

      // ✅ Only auto-open the drawer the first time on mobile
      if (window.innerWidth < 1024 && !hasAutoOpenedOnce()) {
        openDrawer();
        markAutoOpenedOnce();
      }

            return;
    } // ✅ CLOSE addBtn block


    // 4) Preview item modal
    const preview = e.target.closest("[data-item-url]");
    if (preview) {
      const url = preview.getAttribute("data-item-url");
      if (!url) return;

      openItemModal();
      if (itemModalBody) itemModalBody.innerHTML = _("Loading...");

      const res = await fetch(url, { headers: xhrHeaders() });
      if (itemModalBody) itemModalBody.innerHTML = await res.text();

      const meta = document.getElementById("modalItemMeta");
      if (meta) syncModalQtyUI(meta.getAttribute("data-item-id"));
      return;
    }

    // 5) Top promo coupon buttons
    const topCouponBtn = e.target.closest("[data-top-coupon]");
    if (topCouponBtn) {
      const code = topCouponBtn.getAttribute("data-top-coupon") || "";
      if (!code) return;

      const input = document.getElementById("couponInput");
      const msg = document.getElementById("topPromoMessage");
      if (input) input.value = code;

      if (msg) {
        msg.textContent = _("Applying coupon: ") + code + _("…");
        msg.classList.remove("hidden");
        setTimeout(() => msg.classList.add("hidden"), 3000);
      }

      // trigger same apply flow
      const applyBtn2 = document.getElementById("applyCouponBtn");
      if (applyBtn2) {
        applyBtn2.click();
        return;
      }

      // fallback: apply directly
      if (!URLS.apply_coupon) return;

      const fd = new FormData();
      fd.append("coupon_code", code);

      const res = await fetch(URLS.apply_coupon, {
        method: "POST",
        headers: xhrHeaders({ "X-CSRFToken": csrfToken() }),
        body: fd,
      });

      const data = await res.json().catch(() => null);

      if (data && data.ok && data.cart) {
        renderCartFromSnapshot(data.cart);
        setCouponStateFromCart(data.cart);
        applyCouponPricesToMenu();
      } else {
        await refreshCart();
      }

      if (msg) {
        msg.classList.remove("hidden");
        if (res.ok && data && data.ok) {
          msg.className = "px-6 pb-4 text-sm font-semibold text-green-700";
          msg.textContent = _("Voucher applied: ") + code;
        } else {
          msg.className = "px-6 pb-4 text-sm font-semibold text-red-700";
          msg.textContent = data && data.error ? data.error : _("Coupon not valid.");
        }
      }
      return;
    }

    // 6) Optional: any element can open checkout flow
    const goCheckout = e.target.closest("[data-open-checkout]");
    if (goCheckout) {
      e.preventDefault();
      await openCheckoutFlow();
      return;
    }
  });

  // =========================
  // Clear cart buttons
  // =========================
  const clearBtn = document.getElementById("clearCartBtn");
  if (clearBtn) clearBtn.addEventListener("click", clearCart);

  const clearBtnMobile = document.getElementById("clearCartBtnMobile");
  if (clearBtnMobile) clearBtnMobile.addEventListener("click", clearCart);

  // =========================
  // Init
  // =========================
  refreshCart();
})();
