document.addEventListener("DOMContentLoaded", () => {
    const menu = document.querySelector(".nav-menu");
    const toggle = document.querySelector(".menu-toggle");
    const closeBtn = document.querySelector(".menu-close-btn");
    const overlay = document.getElementById("nav-overlay");
    const dropdownToggles = document.querySelectorAll(".nav-item-dropdown > .nav-dropdown-toggle");

    if (!menu || !toggle) return;

    menu.classList.remove("active");
    menu.setAttribute("aria-hidden", "true");
    if (overlay) overlay.style.display = "none";

    function openMenu() {
        menu.classList.add("active");
        menu.setAttribute("aria-hidden", "false");
        document.body.classList.add("menu-open");
        if (overlay) overlay.style.display = "block";
        const firstFocusable = menu.querySelector("a, button");
        if (firstFocusable) firstFocusable.focus();
    }

    function closeMenu() {
        menu.classList.remove("active");
        menu.setAttribute("aria-hidden", "true");
        document.body.classList.remove("menu-open");
        if (overlay) overlay.style.display = "none";
        toggle.focus();
    }

    toggle.addEventListener("click", (e) => {
        e.preventDefault();
        openMenu();
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", (e) => {
            e.preventDefault();
            closeMenu();
        });
    }

    if (overlay) {
        overlay.addEventListener("click", closeMenu);
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeMenu();
        }
    });

    const menuLinks = menu.querySelectorAll("a, button");
    menuLinks.forEach((link) => {
        link.addEventListener("click", () => {
            closeMenu();
        });
    });

    dropdownToggles.forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const parent = btn.closest(".nav-item-dropdown");
            if (!parent) return;
            const expanded = btn.getAttribute("aria-expanded") === "true";
            btn.setAttribute("aria-expanded", String(!expanded));
            parent.classList.toggle("open", !expanded);
        });
    });
});