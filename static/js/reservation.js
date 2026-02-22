(function () {
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const $ = (sel, root = document) => root.querySelector(sel);
  const money2 = (n) => (Math.round((n + Number.EPSILON) * 100) / 100).toFixed(2);

  // i18n helpers (safe fallbacks)
  const T = (window.gettext ? window.gettext : (s) => s);
  const TN = (window.ngettext ? window.ngettext : (s, p, n) => (n === 1 ? s : p));

  // -----------------------------
  // Scroll lock (modal-safe, iOS-safe)
  // -----------------------------
  function lockScroll() {
    document.documentElement.classList.add("overflow-hidden");
    document.body.classList.add("overflow-hidden");
  }

  function unlockScroll() {
    document.documentElement.classList.remove("overflow-hidden");
    document.body.classList.remove("overflow-hidden");
  }

  // -----------------------------
  // Summary
  // -----------------------------
  const sumWhen = $("#sumWhen");
  const sumGuests = $("#sumGuests");
  const sumPreorder = $("#sumPreorder");
  const sumTotal = $("#sumTotal");

  const dateInput = document.getElementById("id_date");
  const timeInput = document.getElementById("id_time");

  const partyInput = document.getElementById("id_party_size");
  const babyInput = document.getElementById("id_baby_seats");

  const dtSelectedPreview = document.getElementById("dtSelectedPreview");

  function updateSummaryBasics() {
    const d = dateInput?.value || "";
    const t = timeInput?.value || "";
    const whenText = (d && t) ? `${d} ${t}` : "—";
    if (sumWhen) sumWhen.textContent = whenText;
    if (dtSelectedPreview) dtSelectedPreview.textContent = whenText;

    const party = partyInput?.value || "";
    const baby = babyInput?.value || "0";
    if (sumGuests) sumGuests.textContent = party ? `${party} (${T("baby")}: ${baby || 0})` : "—";
  }

  [dateInput, timeInput, partyInput, babyInput].forEach(el => {
    if (!el) return;
    el.addEventListener("input", updateSummaryBasics);
    el.addEventListener("change", updateSummaryBasics);
  });
  updateSummaryBasics();

  // =========================================================
  // SUCCESS MODAL close
  // =========================================================
  const successModal = document.getElementById("reservationSuccessModal");
  const successClose = document.getElementById("successClose");

  function closeSuccessModal() {
    if (!successModal) return;

    successModal.classList.add("hidden");
    unlockScroll();

    const homeUrl = window.__RES_HOME_URL__ || "/";
    window.location.href = homeUrl;
  }

  successClose?.addEventListener("click", closeSuccessModal);

  successModal?.addEventListener("click", (e) => {
    if (e.target === successModal) closeSuccessModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (successModal && !successModal.classList.contains("hidden")) {
      closeSuccessModal();
    }
  });

  // =========================================================
  // PRE-ORDER STATE + EDITOR
  // =========================================================
  const preorder = new Map(); // id -> { name, price, qty, image }

  const preorderHiddenInputs = $("#preorderHiddenInputs");
  const preorderEditor = $("#preorderEditor");
  const preorderTotalEl = $("#preorderTotal");

  function writeHiddenInputs() {
    if (!preorderHiddenInputs) return;
    preorderHiddenInputs.innerHTML = "";

    preorder.forEach((v, id) => {
      if (!v.qty || v.qty <= 0) return;

      const hidId = document.createElement("input");
      hidId.type = "hidden";
      hidId.name = "preorder_ids";
      hidId.value = String(id);

      const hidQty = document.createElement("input");
      hidQty.type = "hidden";
      hidQty.name = "preorder_qty";
      hidQty.value = String(v.qty);

      preorderHiddenInputs.appendChild(hidId);
      preorderHiddenInputs.appendChild(hidQty);
    });
  }

  // =========================================================
  // Picker modal references (needed by computeTotals)
  // =========================================================
  const pickerModal = $("#pickerModal");
  const pickerCartCount = document.getElementById("pickerCartCount");
  const pickerCartTotal = document.getElementById("pickerCartTotal");
  const pickerCartCountMobile = document.getElementById("pickerCartCountMobile");
  const pickerCartTotalMobile = document.getElementById("pickerCartTotalMobile");
  const pickerGoTop = document.getElementById("pickerGoTop");

  function computeTotals() {
    let count = 0;
    let total = 0;

    preorder.forEach(v => {
      if (!v.qty || v.qty <= 0) return;
      count += v.qty;
      total += (v.price * v.qty);
    });

    const itemLabel = TN(T("item"), T("items"), count);
    if (sumPreorder) sumPreorder.textContent = `${count} ${itemLabel}`;
    if (sumTotal) sumTotal.textContent = money2(total);
    if (preorderTotalEl) preorderTotalEl.textContent = money2(total);

    if (pickerCartCount) pickerCartCount.textContent = `${count} ${itemLabel}`;
    if (pickerCartTotal) pickerCartTotal.textContent = money2(total);
    if (pickerCartCountMobile) pickerCartCountMobile.textContent = `${count} ${itemLabel}`;
    if (pickerCartTotalMobile) pickerCartTotalMobile.textContent = money2(total);
  }

  function syncPickerQtyUI(id, qty) {
    const card = document.querySelector(`.pickerItem[data-id="${id}"]`);
    const input = card?.querySelector(".qtyInput");
    if (input) input.value = String(qty);
  }

  function setQtyById(id, qty) {
    const prev = preorder.get(String(id));
    qty = Math.max(0, parseInt(qty || 0, 10) || 0);

    if (!prev) {
      return;
    }

    if (qty <= 0) preorder.delete(String(id));
    else preorder.set(String(id), { ...prev, qty });

    syncPickerQtyUI(String(id), qty);
    renderEditor();
  }

  function renderEditor() {
    if (!preorderEditor) return;

    const hasAny = Array.from(preorder.values()).some(v => (parseInt(v.qty || 0, 10) || 0) > 0);
    if (!hasAny) {
      preorderEditor.innerHTML = `<div class="text-sm text-[#3e2723]/65">${T("No items selected.")}</div>`;
      writeHiddenInputs();
      computeTotals();
      return;
    }

    const rows = [];
    preorder.forEach((v, id) => {
      if (!v.qty || v.qty <= 0) return;

      const img = v.image
        ? `<img src="${v.image}" alt="${v.name}" class="w-full h-full object-cover">`
        : `<div class="w-full h-full flex items-center justify-center text-xs text-[#3e2723]/45">${T("No image")}</div>`;

      rows.push(`
        <div class="flex items-center justify-between gap-3 p-3 rounded-2xl border border-[#3e2723]/10 bg-[#f5f0e6]">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-14 h-12 rounded-2xl border border-[#3e2723]/10 overflow-hidden bg-white shrink-0">
              ${img}
            </div>
            <div class="min-w-0">
              <div class="font-semibold text-[#3e2723] truncate">${v.name}</div>
              <div class="text-xs text-[#3e2723]/60 mt-0.5">€ ${money2(v.price)} ${T("each")}</div>
            </div>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            <button type="button"
                    class="edMinus w-10 h-10 rounded-2xl border border-[#3e2723]/10 bg-white text-[#3e2723] font-semibold hover:bg-white/80 active:scale-[0.99] transition"
                    data-id="${id}">−</button>

            <input type="number" min="0" value="${v.qty}"
                   class="edQty w-14 h-10 text-center rounded-2xl border border-[#3e2723]/10 bg-white text-sm outline-none"
                   data-id="${id}" />

            <button type="button"
                    class="edPlus w-10 h-10 rounded-2xl border border-[#3e2723]/10 bg-white text-[#3e2723] font-semibold hover:bg-white/80 active:scale-[0.99] transition"
                    data-id="${id}">+</button>
          </div>
        </div>
      `);
    });

    preorderEditor.innerHTML = `<div class="space-y-2">${rows.join("")}</div>`;

    $$(".edMinus", preorderEditor).forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const v = preorder.get(String(id));
        if (!v) return;
        setQtyById(id, (v.qty || 0) - 1);
      });
    });

    $$(".edPlus", preorderEditor).forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const v = preorder.get(String(id));
        if (!v) return;
        setQtyById(id, (v.qty || 0) + 1);
      });
    });

    $$(".edQty", preorderEditor).forEach(inp => {
      inp.addEventListener("input", () => {
        const id = inp.getAttribute("data-id");
        setQtyById(id, inp.value);
      });
    });

    writeHiddenInputs();
    computeTotals();
  }

  $("#preorderClear")?.addEventListener("click", () => {
    preorder.clear();
    $$(".qtyInput").forEach(i => i.value = "0");
    renderEditor();
  });

  // =========================================================
  // Picker modal open/close
  // =========================================================
  const openPicker = $("#openPicker");
  const pickerClose = $("#pickerClose");
  const pickerDone = $("#pickerDone");
  const pickerSearch = $("#pickerSearch");
  const pickerBackdrop = $("#pickerBackdrop");

  function openPickerModal() {
    if (!pickerModal) return;
    pickerModal.classList.remove("hidden");
    lockScroll();
  }
  function closePickerModal() {
    if (!pickerModal) return;
    pickerModal.classList.add("hidden");
    if ($("#itemModal") && !$("#itemModal").classList.contains("hidden")) return;
    unlockScroll();
  }

  openPicker?.addEventListener("click", openPickerModal);
  pickerClose?.addEventListener("click", closePickerModal);
  pickerDone?.addEventListener("click", closePickerModal);
  pickerBackdrop?.addEventListener("click", closePickerModal);

  // =========================================================
  // Category + Search
  // =========================================================
  let activeCat = "all";
  const catButtons = $$(".catBtn");
  const catChips = $$(".catChip");
  const itemCards = $$(".pickerItem");
  const pickerScroller = document.querySelector("#pickerModal [data-picker-scroll]");
  const pickerSections = $$(".pickerSection"); // new grouped sections

  function setActiveButtons(value) {
    catButtons.forEach(b => {
      const on = (b.getAttribute("data-cat") === value);
      b.classList.toggle("bg-[#3e2723]", on);
      b.classList.toggle("text-white", on);
    });

    catChips.forEach(b => {
      const on = (b.getAttribute("data-cat") === value);
      if (on) {
        b.classList.add("bg-[#3e2723]", "text-white");
        b.classList.remove("bg-white", "text-[#3e2723]", "border", "border-[#3e2723]/10");
      } else {
        b.classList.remove("bg-[#3e2723]", "text-white");
        b.classList.add("bg-white", "text-[#3e2723]", "border", "border-[#3e2723]/10");
      }
    });
  }

  function applyFilter() {
    const q = (pickerSearch?.value || "").trim().toLowerCase();
    itemCards.forEach(card => {
      const cat = card.getAttribute("data-cat");
      const name = card.getAttribute("data-name") || "";
      const okCat = (activeCat === "all") || (String(cat) === String(activeCat));
      const okSearch = !q || name.includes(q);
      card.style.display = (okCat && okSearch) ? "" : "none";
    });
  }

  function setCat(cat) {
    activeCat = cat;
    setActiveButtons(cat);
    applyFilter();

    // Menu-page behavior: scroll to the section (only if not "all")
    if (pickerScroller && cat !== "all") {
      const sec = document.querySelector(`.pickerSection[data-section-cat="${cat}"]`);
      if (sec) {
        pickerScroller.scrollTo({ top: sec.offsetTop - 110, behavior: "smooth" });
      }
    }
  }

  catButtons.forEach(btn => btn.addEventListener("click", () => setCat(btn.getAttribute("data-cat") || "all")));
  catChips.forEach(btn => btn.addEventListener("click", () => setCat(btn.getAttribute("data-cat") || "all")));
  pickerSearch?.addEventListener("input", () => {
  applyFilter();
  // After search, keep "All" highlighted (like menu behavior)
  setCat("all");
});

// =========================================================
// Scroll-sync category rail (like menu page)
// =========================================================
let _scrollRaf = null;

function getActiveSectionCat() {
  if (!pickerScroller || pickerSections.length === 0) return null;

  // If searching, don't auto-switch categories
  const q = (pickerSearch?.value || "").trim();
  if (q) return null;

  const scTop = pickerScroller.scrollTop;
  const padding = 140; // header+rail area inside modal

  // Choose the last section whose top is above the viewport line
  let active = null;
  for (const sec of pickerSections) {
    // skip empty sections (all items filtered out)
    const anyVisibleCard = sec.querySelector('.pickerItem:not([style*="display: none"])');
    if (!anyVisibleCard) continue;

    const top = sec.offsetTop;
    if (top <= scTop + padding) active = sec;
    else break;
  }

  return active ? (active.getAttribute("data-section-cat") || null) : null;
}

function syncCatRailToScroll() {
  const cat = getActiveSectionCat();
  if (!cat) return;

  if (String(activeCat) !== String(cat)) {
    activeCat = String(cat);
    setActiveButtons(activeCat);

    // Smoothly bring active chip into view (menu-like)
    const chip = document.querySelector(`.catBtn[data-cat="${activeCat}"]`);
    chip?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }
}

pickerScroller?.addEventListener("scroll", () => {
  if (_scrollRaf) cancelAnimationFrame(_scrollRaf);
  _scrollRaf = requestAnimationFrame(syncCatRailToScroll);
}, { passive: true });

  // =========================================================
  // ITEM PREVIEW MODAL (reservation partial)
  // =========================================================
  const itemModal = $("#itemModal");
  const itemModalBody = $("#itemModalBody");
  const itemModalClose = $("#itemModalClose");
  const itemModalBackdrop = $("#itemModalBackdrop");

  function openItemModal() {
    if (!itemModal) return;
    itemModal.classList.remove("hidden");
    lockScroll();
  }

  function closeItemModal() {
    if (!itemModal) return;
    itemModal.classList.add("hidden");
    if (itemModalBody) itemModalBody.innerHTML = `<div class="p-6 text-sm text-[#3e2723]/70">${T("Loading...")}</div>`;
    if (pickerModal && !pickerModal.classList.contains("hidden")) return;
    unlockScroll();
  }

  function bindReservationPreviewControls() {
    if (!itemModalBody) return;

    const meta = itemModalBody.querySelector("[data-res-item]");
    if (!meta) return;

    const id = meta.getAttribute("data-item-id");
    const name = meta.getAttribute("data-item-name") || "";
    const price = parseFloat(meta.getAttribute("data-item-price") || "0") || 0;

    if (!preorder.has(String(id))) {
      const card = document.querySelector(`.pickerItem[data-id="${id}"]`);
      const img = card?.getAttribute("data-image") || "";
      preorder.set(String(id), { name, price, qty: 0, image: img });
    }

    const qtyInput = itemModalBody.querySelector("[data-res-qty]");
    const minusBtn = itemModalBody.querySelector("[data-res-minus]");
    const plusBtn = itemModalBody.querySelector("[data-res-plus]");
    const applyBtn = itemModalBody.querySelector("[data-res-apply]");
    const removeBtn = itemModalBody.querySelector("[data-res-remove]");

    function currentQty() {
      const v = preorder.get(String(id));
      return v ? (parseInt(v.qty || 0, 10) || 0) : 0;
    }

    function setLocalQty(q) {
      q = Math.max(0, parseInt(q || 0, 10) || 0);
      if (qtyInput) qtyInput.value = String(q);
    }

    setLocalQty(currentQty());

    minusBtn?.addEventListener("click", () => setLocalQty((parseInt(qtyInput?.value || "0", 10) || 0) - 1));
    plusBtn?.addEventListener("click", () => setLocalQty((parseInt(qtyInput?.value || "0", 10) || 0) + 1));
    qtyInput?.addEventListener("input", () => setLocalQty(qtyInput.value));

    applyBtn?.addEventListener("click", () => {
      const q = parseInt(qtyInput?.value || "0", 10) || 0;
      if (q <= 0) {
        preorder.delete(String(id));
        syncPickerQtyUI(String(id), 0);
      } else {
        const prev = preorder.get(String(id)) || { name, price, qty: 0, image: "" };
        preorder.set(String(id), { ...prev, name, price, qty: q });
        syncPickerQtyUI(String(id), q);
      }
      renderEditor();
    });

    removeBtn?.addEventListener("click", () => {
      preorder.delete(String(id));
      setLocalQty(0);
      syncPickerQtyUI(String(id), 0);
      renderEditor();
    });
  }

  async function loadPreview(url) {
    if (!url) return;
    openItemModal();
    if (itemModalBody) itemModalBody.innerHTML = `<div class="p-6 text-sm text-[#3e2723]/70">${T("Loading...")}</div>`;

    try {
      const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!res.ok) throw new Error("failed");
      const html = await res.text();
      if (itemModalBody) itemModalBody.innerHTML = html;

      bindReservationPreviewControls();
    } catch {
      if (itemModalBody) itemModalBody.innerHTML = `<div class="p-6 text-sm text-[#3e2723]/70">${T("Could not load item.")}</div>`;
    }
  }

  itemModalClose?.addEventListener("click", closeItemModal);
  itemModalBackdrop?.addEventListener("click", closeItemModal);

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (itemModal && !itemModal.classList.contains("hidden")) { closeItemModal(); return; }
    if (pickerModal && !pickerModal.classList.contains("hidden")) { closePickerModal(); return; }
  });

  // =========================================================
  // Picker card qty controls + click-to-preview
  // =========================================================
  itemCards.forEach(card => {
    const id = card.getAttribute("data-id");
    const name = (card.querySelector(".font-semibold")?.textContent || "").trim();
    const price = parseFloat(card.getAttribute("data-price") || "0") || 0;
    const img = card.getAttribute("data-image") || "";
    const previewUrl = card.getAttribute("data-preview-url") || "";

    const minus = card.querySelector(".qtyMinus");
    const plus = card.querySelector(".qtyPlus");
    const input = card.querySelector(".qtyInput");

    if (!preorder.has(String(id))) {
      preorder.set(String(id), { name, price, qty: 0, image: img });
    }

    function setQty(qty) {
      qty = Math.max(0, parseInt(qty || 0, 10) || 0);
      if (input) input.value = String(qty);

      if (qty <= 0) {
        preorder.set(String(id), { name, price, qty: 0, image: img });
      } else {
        preorder.set(String(id), { name, price, qty, image: img });
      }

      renderEditor();
    }

    [minus, plus, input].forEach(el => {
      if (!el) return;
      el.addEventListener("click", (e) => e.stopPropagation());
      el.addEventListener("mousedown", (e) => e.stopPropagation());
      el.addEventListener("touchstart", (e) => e.stopPropagation(), { passive: true });
    });

    minus?.addEventListener("click", () => setQty((parseInt(input?.value || "0", 10) || 0) - 1));
    plus?.addEventListener("click", () => setQty((parseInt(input?.value || "0", 10) || 0) + 1));
    input?.addEventListener("input", () => setQty(input.value));

    card.addEventListener("click", () => {
      if (!previewUrl) return;
      loadPreview(previewUrl);
    });
  });

  renderEditor();
  setCat("all");

  // =========================================================
  // DateTime Modal Logic (WORKING with your dt partial)
  // =========================================================
  const dtModal = document.getElementById("dtModal");
  const dtBackdrop = document.getElementById("dtBackdrop");
  const dtClose = document.getElementById("dtClose");
  const dtCancel = document.getElementById("dtCancel");
  const openDTBtn = document.getElementById("openDateTimeModal");

  const dtPrevMonth = document.getElementById("dtPrevMonth");
  const dtNextMonth = document.getElementById("dtNextMonth");
  const dtMonthLabel = document.getElementById("dtMonthLabel");
  const dtCalendar = document.getElementById("dtCalendar");

  const dtHour = document.getElementById("dtHour");
  const dtMinute = document.getElementById("dtMinute");
  const dtAmPm = document.getElementById("dtAmPm");
  const dtSetTime = document.getElementById("dtSetTime");
  const dtError = document.getElementById("dtError");

  const handH = document.getElementById("dtHandHour");
  const handM = document.getElementById("dtHandMin");
  const handS = document.getElementById("dtHandSec");

  const OPEN_START = { h: 10, m: 0 };
  const LAST_START = { h: 21, m: 30 };

  let viewYear, viewMonth;
  let selectedDate = null;
  let selectedHour12 = 11;
  let selectedMinute = 0;
  let selectedAmPm = "AM";

  function pad2(n) { return String(n).padStart(2, "0"); }
  function ymd(d) { return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`; }

  function hour12To24(h12, ampm) {
    let h = h12 % 12;
    if (ampm === "PM") h += 12;
    return h;
  }

  function withinBusiness(h24, m) {
    if (h24 < OPEN_START.h) return false;
    if (h24 === OPEN_START.h && m < OPEN_START.m) return false;
    if (h24 > LAST_START.h) return false;
    if (h24 === LAST_START.h && m > LAST_START.m) return false;
    return true;
  }

  function showError(msg) {
    if (!dtError) return;
    dtError.textContent = msg;
    dtError.classList.remove("hidden");
  }
  function clearError() {
    if (!dtError) return;
    dtError.textContent = "";
    dtError.classList.add("hidden");
  }

  function syncClock() {
    if (!handH || !handM || !handS) return;
    const h24 = hour12To24(selectedHour12, selectedAmPm);
    const m = selectedMinute;
    const hourAngle = ((h24 % 12) * 30) + (m * 0.5);
    const minAngle = m * 6;
    const secAngle = minAngle;
    handH.setAttribute("transform", `rotate(${hourAngle} 60 60)`);
    handM.setAttribute("transform", `rotate(${minAngle} 60 60)`);
    handS.setAttribute("transform", `rotate(${secAngle} 60 60)`);
  }

  function buildTimeOptions() {
    if (!dtHour || !dtMinute || !dtAmPm) return;

    dtHour.innerHTML = "";
    for (let h = 1; h <= 12; h++) {
      const opt = document.createElement("option");
      opt.value = String(h);
      opt.textContent = pad2(h);
      if (h === selectedHour12) opt.selected = true;
      dtHour.appendChild(opt);
    }

    dtMinute.innerHTML = "";
    [0, 30].forEach(m => {
      const opt = document.createElement("option");
      opt.value = String(m);
      opt.textContent = pad2(m);
      if (m === selectedMinute) opt.selected = true;
      dtMinute.appendChild(opt);
    });

    dtAmPm.value = selectedAmPm;

    dtHour.onchange = () => { selectedHour12 = parseInt(dtHour.value, 10); syncClock(); };
    dtMinute.onchange = () => { selectedMinute = parseInt(dtMinute.value, 10); syncClock(); };
    dtAmPm.onchange = () => { selectedAmPm = dtAmPm.value; syncClock(); };

    syncClock();
  }

  function parseExisting() {
    const d = dateInput?.value;
    const t = timeInput?.value;

    const now = new Date();
    viewYear = now.getFullYear();
    viewMonth = now.getMonth();
    selectedDate = null;

    if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) {
      const [yy, mm, dd] = d.split("-").map(Number);
      selectedDate = new Date(yy, mm - 1, dd);
      viewYear = selectedDate.getFullYear();
      viewMonth = selectedDate.getMonth();
    }

    if (t && /^\d{2}:\d{2}$/.test(t)) {
      const [hh, mm] = t.split(":").map(Number);
      selectedMinute = mm;

      selectedAmPm = (hh >= 12) ? "PM" : "AM";
      let h12 = hh % 12;
      if (h12 === 0) h12 = 12;
      selectedHour12 = h12;
    }
  }

  function renderCalendar() {
    if (!dtCalendar || !dtMonthLabel) return;

    const monthNames = [
      T("January"), T("February"), T("March"), T("April"), T("May"), T("June"),
      T("July"), T("August"), T("September"), T("October"), T("November"), T("December")
    ];

    dtMonthLabel.textContent = `${monthNames[viewMonth]}, ${viewYear}`;
    dtCalendar.innerHTML = "";

    const first = new Date(viewYear, viewMonth, 1);
    const startDay = first.getDay();
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

    const today = new Date();
    const todayMid = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    for (let i = 0; i < startDay; i++) {
      const blank = document.createElement("div");
      blank.className = "h-10";
      dtCalendar.appendChild(blank);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const cellDate = new Date(viewYear, viewMonth, day);
      const isPast = cellDate < todayMid;

      const isSelected = selectedDate
        && cellDate.getFullYear() === selectedDate.getFullYear()
        && cellDate.getMonth() === selectedDate.getMonth()
        && cellDate.getDate() === selectedDate.getDate();

      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = String(day);

      let base = "h-10 rounded-2xl text-sm font-semibold border transition flex items-center justify-center";
      if (isPast) {
        btn.disabled = true;
        btn.className = base + " border-[#3e2723]/10 bg-white/40 text-[#3e2723]/30 cursor-not-allowed";
      } else if (isSelected) {
        btn.className = base + " border-[#3e2723]/10 bg-[#3e2723] text-white shadow-sm";
      } else {
        btn.className = base + " border-[#3e2723]/10 bg-white text-[#3e2723]/75 hover:bg-white/80 active:scale-[0.99]";
      }

      btn.addEventListener("click", () => {
        selectedDate = new Date(viewYear, viewMonth, day);
        renderCalendar();
        clearError();
      });

      dtCalendar.appendChild(btn);
    }
  }

  function openDT() {
    if (!dtModal) return;
    parseExisting();
    buildTimeOptions();
    renderCalendar();
    dtModal.classList.remove("hidden");
    lockScroll();
    clearError();
  }

  function closeDT() {
    if (!dtModal) return;
    dtModal.classList.add("hidden");
    if ((pickerModal && !pickerModal.classList.contains("hidden")) || (itemModal && !itemModal.classList.contains("hidden"))) return;
    unlockScroll();
    clearError();
  }

  function commitDT() {
    if (!selectedDate) { showError(T("Please select a date.")); return; }

    const h24 = hour12To24(selectedHour12, selectedAmPm);
    const m = selectedMinute;

    if (!withinBusiness(h24, m)) {
      showError(T("Time must be between 10:00 and 21:30."));
      return;
    }

    dateInput.value = ymd(selectedDate);
    timeInput.value = `${pad2(h24)}:${pad2(m)}`;

    dateInput.dispatchEvent(new Event("input", { bubbles: true }));
    dateInput.dispatchEvent(new Event("change", { bubbles: true }));
    timeInput.dispatchEvent(new Event("input", { bubbles: true }));
    timeInput.dispatchEvent(new Event("change", { bubbles: true }));

    closeDT();
  }

  openDTBtn?.addEventListener("click", openDT);
  dtBackdrop?.addEventListener("click", closeDT);
  dtClose?.addEventListener("click", closeDT);
  dtCancel?.addEventListener("click", closeDT);
  dtPrevMonth?.addEventListener("click", () => {
    viewMonth -= 1;
    if (viewMonth < 0) { viewMonth = 11; viewYear -= 1; }
    renderCalendar();
  });
  dtNextMonth?.addEventListener("click", () => {
    viewMonth += 1;
    if (viewMonth > 11) { viewMonth = 0; viewYear += 1; }
    renderCalendar();
  });
  dtSetTime?.addEventListener("click", commitDT);

  // =========================================================
  // Picker Review Panel (selected items at top)
  // =========================================================
  const pickerReviewPanel = document.getElementById("pickerReviewPanel");
  const pickerReviewBody = document.getElementById("pickerReviewBody");
  const pickerReviewTotal = document.getElementById("pickerReviewTotal");

  function reorderPickerItemsSelectedFirst() {
    const grid = document.getElementById("pickerItems");
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll(".pickerItem"));
    const selected = [];
    const others = [];

    for (const card of cards) {
      const id = card.getAttribute("data-id");
      const v = preorder.get(String(id));
      const qty = v ? (parseInt(v.qty || 0, 10) || 0) : 0;

      if (qty > 0) selected.push(card);
      else others.push(card);
    }

    const frag = document.createDocumentFragment();
    selected.forEach(c => frag.appendChild(c));
    others.forEach(c => frag.appendChild(c));
    grid.appendChild(frag);
  }

  function renderPickerReviewPanel() {
  if (!pickerReviewPanel || !pickerReviewBody || !pickerReviewTotal) return;

  const items = [];
  let total = 0;

  preorder.forEach((v, id) => {
    const qty = parseInt(v.qty || 0, 10) || 0;
    if (qty <= 0) return;

    total += (v.price * qty);

    const img = v.image
      ? `<img src="${v.image}" alt="${v.name}" class="w-full h-full object-cover">`
      : `<div class="w-full h-full flex items-center justify-center text-[10px] text-[#3e2723]/45">${T("No image")}</div>`;

    items.push(`
      <div class="flex items-center justify-between gap-3 p-3 rounded-[18px] border border-[#3e2723]/10 bg-[#f5f0e6]">
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-12 h-10 rounded-2xl border border-[#3e2723]/10 overflow-hidden bg-white shrink-0">
            ${img}
          </div>

          <div class="min-w-0">
            <div class="text-sm font-semibold text-[#3e2723] truncate">${v.name}</div>
            <div class="text-[11px] text-[#3e2723]/60">€ ${money2(v.price)} ${T("each")}</div>
          </div>
        </div>

        <div class="flex items-center gap-3 shrink-0">
          <!-- Qty controls (adjust from selected panel) -->
          <div class="flex items-center gap-2">
            <button type="button"
                    class="rvMinus w-9 h-9 rounded-full border border-[#3e2723]/15 bg-white text-[#3e2723] font-semibold
                           hover:bg-[#f5f0e6] active:scale-[0.99] transition"
                    data-id="${id}">−</button>

            <input type="number" min="0" value="${qty}"
                   class="rvQty w-14 h-9 text-center rounded-full border border-[#3e2723]/15 bg-white text-sm outline-none"
                   data-id="${id}" />

            <button type="button"
                    class="rvPlus w-9 h-9 rounded-full border border-[#3e2723]/15 bg-white text-[#3e2723] font-semibold
                           hover:bg-[#f5f0e6] active:scale-[0.99] transition"
                    data-id="${id}">+</button>
          </div>

          <div class="text-sm font-semibold text-[#3e2723] w-[82px] text-right">
            € ${money2(v.price * qty)}
          </div>
        </div>
      </div>
    `);
  });

  pickerReviewTotal.textContent = money2(total);

  if (items.length === 0) {
    pickerReviewPanel.classList.add("hidden");
    pickerReviewBody.innerHTML = "";
    return;
  }

  pickerReviewPanel.classList.remove("hidden");
  pickerReviewBody.innerHTML = items.join("");

  // Bind events for review controls (no other functionality touched)
  const stop = (e) => e.stopPropagation();

  $$(".rvMinus", pickerReviewBody).forEach(btn => {
    btn.addEventListener("click", stop);
    btn.addEventListener("mousedown", stop);
    btn.addEventListener("touchstart", stop, { passive: true });

    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const v = preorder.get(String(id));
      const cur = v ? (parseInt(v.qty || 0, 10) || 0) : 0;
      setQtyById(id, cur - 1);
    });
  });

  $$(".rvPlus", pickerReviewBody).forEach(btn => {
    btn.addEventListener("click", stop);
    btn.addEventListener("mousedown", stop);
    btn.addEventListener("touchstart", stop, { passive: true });

    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const v = preorder.get(String(id));
      const cur = v ? (parseInt(v.qty || 0, 10) || 0) : 0;
      setQtyById(id, cur + 1);
    });
  });

  $$(".rvQty", pickerReviewBody).forEach(inp => {
    inp.addEventListener("click", stop);
    inp.addEventListener("mousedown", stop);
    inp.addEventListener("touchstart", stop, { passive: true });

    inp.addEventListener("input", () => {
      const id = inp.getAttribute("data-id");
      setQtyById(id, inp.value);
    });
  });
}
  const _computeTotals = computeTotals;
  computeTotals = function () {
    _computeTotals();
    renderPickerReviewPanel();

    // ✅ Do NOT reorder grid items anymore.
    // Selected items are shown only in the top review panel.
    applyFilter();
  };

  pickerGoTop?.addEventListener("click", () => {
    if (pickerSearch) pickerSearch.value = "";
    setCat("all");

    reorderPickerItemsSelectedFirst();
    renderPickerReviewPanel();

    const scroller = document.querySelector("#pickerModal [data-picker-scroll]");
    scroller?.scrollTo({ top: 0, behavior: "smooth" });
  });

})();