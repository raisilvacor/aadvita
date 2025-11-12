document.addEventListener("DOMContentLoaded", function () {
    const menuToggle = document.querySelector(".menu-toggle");
    const menu = document.querySelector(".nav-menu");
    const closeBtn = document.querySelector(".menu-close-btn");
    const overlay = document.getElementById("nav-overlay");

    function openMenu() {
        menu.classList.add("active");
        document.body.classList.add("menu-open");
        if (overlay) {
            overlay.style.display = "block";
        }
    }

    function closeMenu() {
        menu.classList.remove("active");
        document.body.classList.remove("menu-open");
        if (overlay) {
            overlay.style.display = "none";
        }
    }

    if (menuToggle) {
        menuToggle.addEventListener("click", openMenu);
    }

    if (closeBtn) {
        closeBtn.addEventListener("click", closeMenu);
    }

    if (overlay) {
        overlay.addEventListener("click", closeMenu);
    }

    const menuLinks = menu ? menu.querySelectorAll("a, button") : [];
    menuLinks.forEach(function (link) {
        link.addEventListener("click", closeMenu);
    });
});