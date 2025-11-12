document.addEventListener("DOMContentLoaded", () => {
    const menu = document.querySelector(".nav-menu");
    const toggle = document.querySelector(".menu-toggle");
    const closeBtn = document.querySelector(".menu-close-btn");
    const overlay = document.getElementById("nav-overlay");
    const mobileQuery = window.matchMedia("(max-width: 1023px)");

    if (!menu || !toggle) return;

    const menuLinks = Array.from(menu.querySelectorAll("a"));

    function resetDesktopState() {
        menu.classList.remove("active");
        menu.removeAttribute("aria-hidden");
        menu.style.display = "";
        document.body.classList.remove("menu-open");
        toggle.setAttribute("aria-expanded", "false");
        if (overlay) {
            overlay.style.display = "none";
            overlay.classList.remove("active");
        }
    }

    function hideMenu() {
        if (!mobileQuery.matches) {
            resetDesktopState();
            return;
        }
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

    function showMenu() {
        if (!mobileQuery.matches) return;
        menu.classList.add("active");
        menu.setAttribute("aria-hidden", "false");
        menu.style.display = "flex";
        document.body.classList.add("menu-open");
        toggle.setAttribute("aria-expanded", "true");
        if (overlay) {
            overlay.style.display = "block";
            overlay.classList.add("active");
        }
        if (menuLinks.length) {
            requestAnimationFrame(() => menuLinks[0].focus());
        }
    }

    function applyInitialState() {
        if (mobileQuery.matches) {
            hideMenu();
        } else {
            resetDesktopState();
        }
    }

    applyInitialState();
    mobileQuery.addEventListener("change", applyInitialState);

    function toggleMenu(event) {
        if (!mobileQuery.matches) {
            resetDesktopState();
            return;
        }
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        if (menu.classList.contains("active")) {
            hideMenu();
            toggle.focus();
        } else {
            showMenu();
        }
    }

    toggle.addEventListener("click", toggleMenu);

    if (closeBtn) {
        closeBtn.addEventListener("click", (event) => {
            event.preventDefault();
            hideMenu();
            toggle.focus();
        });
    }

    if (overlay) {
        overlay.addEventListener("click", hideMenu);
    }

    menuLinks.forEach((link) => {
        link.addEventListener("click", () => hideMenu());
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && menu.classList.contains("active")) {
            hideMenu();
            toggle.focus();
        }
    });
});