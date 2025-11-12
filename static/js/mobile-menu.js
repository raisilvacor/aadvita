document.addEventListener("DOMContentLoaded", () => {
    const menu = document.querySelector(".nav-menu");
    const toggle = document.querySelector(".menu-toggle");
    const closeBtn = document.querySelector(".menu-close-btn");
    const overlay = document.getElementById("nav-overlay");
    const dropdownToggles = document.querySelectorAll(".nav-item-dropdown > .nav-dropdown-toggle");

    if (!menu || !toggle) return;

    function hideMenu() {
        menu.classList.remove("active");
        menu.setAttribute("aria-hidden", "true");
        menu.style.display = "none";
        document.body.classList.remove("menu-open");
        toggle.setAttribute("aria-expanded", "false");
        if (overlay) {
            overlay.style.display = "none";
            overlay.classList.remove("active");
        }
    }

    hideMenu();

    function openMenu() {
        menu.classList.add("active");
        menu.setAttribute("aria-hidden", "false");
        menu.style.display = "flex";
        document.body.classList.add("menu-open");
        toggle.setAttribute("aria-expanded", "true");
        if (overlay) {
            overlay.style.display = "block";
            overlay.classList.add("active");
        }
        const firstFocusable = menu.querySelector("a, button");
        if (firstFocusable) firstFocusable.focus();
    }

    function closeMenu() {
        hideMenu();
        toggle.focus();
    }

    toggle.addEventListener("click", (e) => {
        e.preventDefault();
        if (menu.classList.contains("active")) {
            closeMenu();
        } else {
            openMenu();
        }
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
        if (e.key === "Escape" && menu.classList.contains("active")) {
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