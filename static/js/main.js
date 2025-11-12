// Acessibilidade e Funcionalidades JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Menu Toggle para Mobile
    const menuToggle = document.querySelector('.menu-toggle');
    const navMenu = document.querySelector('.nav-menu');
    const navOverlay = document.getElementById('nav-overlay');
    const menuCloseBtn = document.querySelector('.menu-close-btn');
    const menuCloseItem = document.querySelector('.menu-close-item');
    
    // Mostrar/ocultar botão de fechar baseado no tamanho da tela
    function updateMenuCloseButton() {
        if (window.innerWidth <= 768) {
            if (menuCloseItem) menuCloseItem.style.display = 'flex';
            if (menuCloseBtn) menuCloseBtn.style.display = 'flex';
        } else {
            if (menuCloseItem) menuCloseItem.style.display = 'none';
            if (menuCloseBtn) menuCloseBtn.style.display = 'none';
        }
    }
    
    window.addEventListener('resize', updateMenuCloseButton);
    updateMenuCloseButton();
    
    if (menuToggle && navMenu) {
        let isMenuOpen = false;
        
        function openMenu() {
            if (isMenuOpen) return;
            isMenuOpen = true;
            menuToggle.setAttribute('aria-expanded', 'true');
            navMenu.classList.add('active');
            if (navOverlay) {
                navOverlay.classList.add('active');
            }
            document.body.style.overflow = 'hidden';
        }
        
        function closeMenu() {
            if (!isMenuOpen) return;
            isMenuOpen = false;
            menuToggle.setAttribute('aria-expanded', 'false');
            navMenu.classList.remove('active');
            if (navOverlay) {
                navOverlay.classList.remove('active');
            }
            document.body.style.overflow = '';
        }
        
        function toggleMenu() {
            if (isMenuOpen) {
                closeMenu();
            } else {
                openMenu();
            }
        }
        
        // Event listeners para o botão de toggle
        menuToggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleMenu();
        });
        
        // Para touch devices
        menuToggle.addEventListener('touchend', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleMenu();
        }, { passive: false });
        
        // Botão de fechar
        if (menuCloseBtn) {
            menuCloseBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                closeMenu();
            });
            menuCloseBtn.addEventListener('touchend', function(e) {
                e.preventDefault();
                e.stopPropagation();
                closeMenu();
            }, { passive: false });
        }
        
        // Fechar menu ao clicar no overlay
        if (navOverlay) {
            navOverlay.addEventListener('click', function(e) {
                e.preventDefault();
                closeMenu();
            });
            navOverlay.addEventListener('touchend', function(e) {
                e.preventDefault();
                closeMenu();
            }, { passive: false });
        }
        
        // Fechar menu ao clicar em um link
        const navLinks = navMenu.querySelectorAll('a');
        navLinks.forEach(link => {
            link.addEventListener('click', function() {
                closeMenu();
            });
        });
        
        // Fechar menu ao pressionar Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && isMenuOpen) {
                closeMenu();
                menuToggle.focus();
            }
        });
    }
    
    // Menu Suspenso - Agendas
    const dropdownToggle = document.querySelector('.nav-dropdown-toggle');
    const dropdownMenu = document.querySelector('.nav-dropdown-menu');
    
    if (dropdownToggle && dropdownMenu) {
        const navItemDropdown = dropdownToggle.closest('.nav-item-dropdown');
        
        if (navItemDropdown) {
            let hoverTimeout;
            let isDesktop = window.innerWidth > 768;
            
            // Atualizar flag ao redimensionar
            window.addEventListener('resize', function() {
                isDesktop = window.innerWidth > 768;
            });
            
            // Prevenir comportamento padrão do link e toggle no mobile
            dropdownToggle.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Para mobile, toggle no click
                if (!isDesktop) {
                    const isExpanded = dropdownToggle.getAttribute('aria-expanded') === 'true';
                    dropdownToggle.setAttribute('aria-expanded', !isExpanded);
                    dropdownMenu.classList.toggle('active');
                }
            });
            
            // Função para mostrar o menu
            function showMenu() {
                if (isDesktop) {
                    clearTimeout(hoverTimeout);
                    dropdownMenu.style.display = 'block';
                    dropdownToggle.setAttribute('aria-expanded', 'true');
                }
            }
            
            // Função para esconder o menu com delay
            function hideMenu() {
                if (isDesktop) {
                    hoverTimeout = setTimeout(function() {
                        dropdownMenu.style.display = 'none';
                        dropdownToggle.setAttribute('aria-expanded', 'false');
                    }, 200); // Delay para permitir movimento do mouse
                }
            }
            
            // Controlar menu no desktop com JavaScript
            if (isDesktop) {
                // Esconder menu inicialmente (sobrescrever CSS)
                dropdownMenu.style.display = 'none';
                
                // Atualizar aria-expanded no hover (desktop)
                navItemDropdown.addEventListener('mouseenter', showMenu);
                navItemDropdown.addEventListener('mouseleave', hideMenu);
                
                // Manter menu aberto quando mouse está sobre ele
                dropdownMenu.addEventListener('mouseenter', showMenu);
                dropdownMenu.addEventListener('mouseleave', hideMenu);
            }
        }
    }

    // Navegação por teclado melhorada
    const focusableElements = document.querySelectorAll(
        'a[href], button, textarea, input[type="text"], input[type="radio"], input[type="checkbox"], select'
    );
    
    // Adicionar indicadores visuais de foco
    focusableElements.forEach(element => {
        element.addEventListener('focus', function() {
            this.classList.add('keyboard-focus');
        });
        
        element.addEventListener('blur', function() {
            this.classList.remove('keyboard-focus');
        });
    });
    
    // Detectar navegação por teclado vs mouse
    let usingKeyboard = false;
    
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            usingKeyboard = true;
            document.body.classList.add('keyboard-navigation');
        }
    });
    
    document.addEventListener('mousedown', function() {
        usingKeyboard = false;
        document.body.classList.remove('keyboard-navigation');
    });
    
    // Anunciar mudanças dinâmicas para leitores de tela
    const announceToScreenReader = function(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('role', 'status');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = message;
        document.body.appendChild(announcement);
        
        setTimeout(function() {
            document.body.removeChild(announcement);
        }, 1000);
    };
    
    // Melhorar acessibilidade de links externos
    const externalLinks = document.querySelectorAll('a[target="_blank"]');
    externalLinks.forEach(link => {
        if (!link.querySelector('.sr-only')) {
            const srText = document.createElement('span');
            srText.className = 'sr-only';
            srText.textContent = ' (abre em nova aba)';
            link.appendChild(srText);
        }
    });
    
    // Lazy loading de imagens com fallback acessível
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver(function(entries, observer) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        observer.unobserve(img);
                    }
                }
            });
        });
        
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(function(img) {
            imageObserver.observe(img);
        });
    }
    
    // Melhorar navegação com landmarks
    const mainContent = document.getElementById('main-content');
    if (mainContent) {
        mainContent.setAttribute('tabindex', '-1');
        
        // Focar no conteúdo principal quando o skip link for usado
        const skipLink = document.querySelector('.skip-link');
        if (skipLink) {
            skipLink.addEventListener('click', function(e) {
                e.preventDefault();
                mainContent.focus();
                mainContent.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        }
    }
    
    // Adicionar suporte para navegação por atalhos de teclado
    document.addEventListener('keydown', function(e) {
        // Alt + H para ir ao header
        if (e.altKey && e.key === 'h') {
            e.preventDefault();
            const header = document.querySelector('header');
            if (header) {
                const firstFocusable = header.querySelector('a, button');
                if (firstFocusable) {
                    firstFocusable.focus();
                }
            }
        }
        
        // Alt + M para ir ao conteúdo principal
        if (e.altKey && e.key === 'm') {
            e.preventDefault();
            if (mainContent) {
                mainContent.focus();
                mainContent.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
        
        // Alt + F para ir ao footer
        if (e.altKey && e.key === 'f') {
            e.preventDefault();
            const footer = document.querySelector('footer');
            if (footer) {
                const firstFocusable = footer.querySelector('a, button');
                if (firstFocusable) {
                    firstFocusable.focus();
                }
            }
        }
    });
    
    // Melhorar acessibilidade de cards e artigos
    const cards = document.querySelectorAll('.card, .agenda-item');
    cards.forEach(function(card) {
        const links = card.querySelectorAll('a');
        if (links.length > 0) {
            card.setAttribute('tabindex', '0');
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const firstLink = links[0];
                    if (firstLink) {
                        firstLink.click();
                    }
                }
        });
    }
    
    // Seletor de idioma movido para arquivo separado (language-selector.js)
    
    // Lightbox functionality
    const lightboxModal = document.getElementById('lightbox-modal');
    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const lightboxClose = document.querySelector('.lightbox-close');
    const lightboxPrev = document.querySelector('.lightbox-prev');
    const lightboxNext = document.querySelector('.lightbox-next');
    const imageLinks = document.querySelectorAll('.image-link');
    
    let currentImageIndex = 0;
    let images = [];
    
    // Coletar todas as imagens
    if (imageLinks.length > 0) {
        imageLinks.forEach(function(link) {
            // Usar data-image se existir, senão usar href, senão usar src da img dentro do link
            const img = link.querySelector('img');
            const imageSrc = link.getAttribute('data-image') || link.href || (img ? img.src : '');
            images.push({
                src: imageSrc,
                title: link.getAttribute('data-title') || (img ? img.alt : '') || ''
            });
        });
    }
    
    // Função para abrir lightbox
    function openLightbox(index) {
        if (images.length === 0) return;
        
        currentImageIndex = index;
        lightboxImage.src = images[currentImageIndex].src;
        lightboxCaption.textContent = images[currentImageIndex].title;
        lightboxModal.classList.add('active');
        lightboxModal.setAttribute('aria-hidden', 'false');
        
        // Atualizar visibilidade dos botões de navegação
        if (images.length <= 1) {
            lightboxPrev.style.display = 'none';
            lightboxNext.style.display = 'none';
        } else {
            lightboxPrev.style.display = 'block';
            lightboxNext.style.display = 'block';
        }
        
        // Focar no modal para acessibilidade
        lightboxModal.focus();
    }
    
    // Função para fechar lightbox
    function closeLightbox() {
        lightboxModal.classList.remove('active');
        lightboxModal.setAttribute('aria-hidden', 'true');
    }
    
    // Função para navegar para imagem anterior
    function showPrevImage() {
        if (images.length === 0) return;
        currentImageIndex = (currentImageIndex - 1 + images.length) % images.length;
        lightboxImage.src = images[currentImageIndex].src;
        lightboxCaption.textContent = images[currentImageIndex].title;
    }
    
    // Função para navegar para próxima imagem
    function showNextImage() {
        if (images.length === 0) return;
        currentImageIndex = (currentImageIndex + 1) % images.length;
        lightboxImage.src = images[currentImageIndex].src;
        lightboxCaption.textContent = images[currentImageIndex].title;
    }
    
    // Event listeners para lightbox
    if (imageLinks.length > 0) {
        imageLinks.forEach(function(link, index) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                openLightbox(index);
                return false;
            });
            
            // Também adicionar listener no mousedown para garantir
            link.addEventListener('mousedown', function(e) {
                if (e.button === 0) { // Botão esquerdo
                    e.preventDefault();
                }
            });
        });
    }
    
    if (lightboxClose) {
        lightboxClose.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            closeLightbox();
        });
    }
    
    if (lightboxPrev) {
        lightboxPrev.addEventListener('click', showPrevImage);
    }
    
    if (lightboxNext) {
        lightboxNext.addEventListener('click', showNextImage);
    }
    
    // Fechar lightbox ao clicar no fundo
    if (lightboxModal) {
        lightboxModal.addEventListener('click', function(e) {
            if (e.target === lightboxModal) {
                closeLightbox();
            }
        });
    }
    
    // Navegação por teclado no lightbox
    document.addEventListener('keydown', function(e) {
        if (lightboxModal && lightboxModal.classList.contains('active')) {
            if (e.key === 'Escape') {
                closeLightbox();
            } else if (e.key === 'ArrowLeft') {
                showPrevImage();
            } else if (e.key === 'ArrowRight') {
                showNextImage();
            }
        }
    });
    
    // Prevenir scroll do body quando lightbox está aberto
    if (lightboxModal) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName === 'class') {
                    if (lightboxModal.classList.contains('active')) {
                        document.body.style.overflow = 'hidden';
                    } else {
                        document.body.style.overflow = '';
                    }
                }
            });
        });
        
        observer.observe(lightboxModal, {
            attributes: true,
            attributeFilter: ['class']
        });
    }
    
    // Carrossel de Apoiadores - Loop infinito
    const apoiadoresCarousel = document.getElementById('apoiadores-carousel');
    if (apoiadoresCarousel) {
        const items = apoiadoresCarousel.querySelectorAll('.apoiador-carousel-item');
        
        if (items.length > 0) {
            // Duplicar itens para criar loop infinito
            items.forEach(item => {
                const clone = item.cloneNode(true);
                apoiadoresCarousel.appendChild(clone);
            });
            
            // Ajustar velocidade baseada no número de itens
            const totalItems = items.length;
            const duration = totalItems * 1.5; // 1.5 segundos por item (mais rápido)
            apoiadoresCarousel.style.animationDuration = `${duration}s`;
        }
    }
    
    console.log('AADVITA - Site carregado com sucesso! Acessibilidade ativada.');
});

// Fechar mensagens flash - Código FORA do DOMContentLoaded para funcionar imediatamente
(function() {
    function closeFlashMessage(message) {
        if (message && message.parentNode) {
            message.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            message.style.opacity = '0';
            message.style.transform = 'translateX(100%)';
            setTimeout(function() {
                if (message.parentNode) {
                    message.remove();
                }
            }, 300);
        }
    }
    
    // Event delegation no document - múltiplas abordagens para garantir funcionamento
    function handleFlashClose(e) {
        // Verificar se o clique foi no botão de fechar
        let closeBtn = null;
        
        // Verificar se o target é o botão
        if (e.target && e.target.classList && e.target.classList.contains('flash-close')) {
            closeBtn = e.target;
        }
        // Verificar se o target está dentro do botão
        else if (e.target && e.target.closest) {
            closeBtn = e.target.closest('.flash-close');
        }
        
        if (closeBtn) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            
            const message = closeBtn.closest('.flash-message');
            if (message) {
                closeFlashMessage(message);
            }
            return false;
        }
    }
    
    // Adicionar listener com capture phase
    document.addEventListener('click', handleFlashClose, true);
    
    // Também adicionar listener direto quando DOM estiver pronto
    function attachDirectListeners() {
        document.querySelectorAll('.flash-close').forEach(function(btn) {
            // Remover listeners anteriores se existirem
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
            
            // Adicionar novo listener
            newBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                const message = this.closest('.flash-message');
                if (message) {
                    closeFlashMessage(message);
                }
                return false;
            }, true);
        });
    }
    
    // Executar quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachDirectListeners);
    } else {
        attachDirectListeners();
    }
    
    // Auto-fechar mensagens flash após 5 segundos
    function autoCloseFlashMessages() {
        document.querySelectorAll('.flash-message').forEach(function(message) {
            if (!message.dataset.autoCloseSet) {
                message.dataset.autoCloseSet = 'true';
                setTimeout(function() {
                    if (message.parentNode) {
                        closeFlashMessage(message);
                    }
                }, 5000);
            }
        });
    }
    
    // Inicializar auto-close quando o DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoCloseFlashMessages);
    } else {
        autoCloseFlashMessages();
    }
    
    // Re-inicializar após mudanças no DOM
    if (typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length) {
                    attachDirectListeners();
                    autoCloseFlashMessages();
                }
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
})();

