// MENU MOBILE - Código ULTRA SIMPLIFICADO para garantir funcionamento
(function() {
    'use strict';
    
    var menuOpen = false;
    
    function setupMenu() {
        var btn = document.querySelector('.menu-toggle');
        var menu = document.querySelector('.nav-menu');
        var overlay = document.getElementById('nav-overlay');
        
        if (!btn || !menu) {
            setTimeout(setupMenu, 100);
            return;
        }
        
        function openMenu() {
            menuOpen = true;
            menu.classList.add('active');
            menu.style.display = 'flex';
            menu.style.transform = 'translateX(0)';
            menu.style.visibility = 'visible';
            if (overlay) {
                overlay.classList.add('active');
                overlay.style.display = 'block';
            }
            document.body.style.overflow = 'hidden';
        }
        
        function closeMenu() {
            menuOpen = false;
            menu.classList.remove('active');
            menu.style.transform = 'translateX(-100%)';
            if (overlay) {
                overlay.classList.remove('active');
                overlay.style.display = 'none';
            }
            document.body.style.overflow = '';
            setTimeout(function() {
                if (!menuOpen) {
                    menu.style.display = 'none';
                    menu.style.visibility = 'hidden';
                }
            }, 300);
        }
        
        function toggleMenu(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            if (menuOpen) {
                closeMenu();
            } else {
                openMenu();
            }
            return false;
        }
        
        // Remover listeners antigos
        var newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        btn = newBtn;
        
        // Adicionar listeners
        btn.onclick = toggleMenu;
        btn.addEventListener('click', toggleMenu, false);
        btn.addEventListener('touchend', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleMenu(e);
        }, false);
        
        if (overlay) {
            overlay.onclick = closeMenu;
            overlay.addEventListener('click', closeMenu, false);
            overlay.addEventListener('touchend', function(e) {
                e.preventDefault();
                closeMenu();
            }, false);
        }
        
        // Botão de fechar
        var closeBtn = document.querySelector('.menu-close-btn');
        if (closeBtn) {
            var newCloseBtn = closeBtn.cloneNode(true);
            closeBtn.parentNode.replaceChild(newCloseBtn, closeBtn);
            closeBtn = newCloseBtn;
            
            closeBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                closeMenu();
            };
            closeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                closeMenu();
            }, false);
            closeBtn.addEventListener('touchend', function(e) {
                e.preventDefault();
                closeMenu();
            }, false);
        }
        
        var links = menu.querySelectorAll('a');
        for (var i = 0; i < links.length; i++) {
            (function(link) {
                link.addEventListener('click', function() {
                    if (menuOpen) closeMenu();
                }, false);
            })(links[i]);
        }
    }
    
    // Executar imediatamente
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupMenu);
    } else {
        setupMenu();
    }
    
    // Backup: executar após delays
    setTimeout(setupMenu, 50);
    setTimeout(setupMenu, 200);
    setTimeout(setupMenu, 500);
    window.addEventListener('load', setupMenu);
})();

