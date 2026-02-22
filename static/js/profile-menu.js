(function () {
  // Desktop
  const btn = document.getElementById("profileMenuBtn");
  const menu = document.getElementById("profileMenu");

  function closeDesktop() {
    if (!menu || !btn) return;
    menu.classList.add("hidden");
    btn.setAttribute("aria-expanded", "false");
  }

  function toggleDesktop() {
    if (!menu || !btn) return;
    const isHidden = menu.classList.contains("hidden");
    if (isHidden) {
      menu.classList.remove("hidden");
      btn.setAttribute("aria-expanded", "true");
    } else {
      closeDesktop();
    }
  }

  if (btn && menu) {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleDesktop();
    });

    document.addEventListener("click", closeDesktop);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDesktop();
    });
  }

  // Mobile (inside hamburger)
  const btnM = document.getElementById("profileMenuBtnMobile");
  const menuM = document.getElementById("profileMenuMobile");

  function toggleMobile() {
    if (!menuM) return;
    menuM.classList.toggle("hidden");
  }

  if (btnM && menuM) {
    btnM.addEventListener("click", toggleMobile);
  }
})();
