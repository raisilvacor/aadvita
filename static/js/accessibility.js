// Acessibilidade - Controle de Fonte e Contraste
(function() {
    'use strict';
    
    // Configurações padrão
    const DEFAULT_FONT_SIZE = 100; // 100%
    const FONT_SIZE_STEP = 15; // Incremento/decremento em %
    const MIN_FONT_SIZE = 85;
    const MAX_FONT_SIZE = 150;
    
    // Estado atual
    let currentFontSize = DEFAULT_FONT_SIZE;
    let isHighContrast = false;
    
    // Carregar preferências do localStorage
    function loadPreferences() {
        const savedFontSize = localStorage.getItem('accessibility_font_size');
        const savedContrast = localStorage.getItem('accessibility_high_contrast');
        
        if (savedFontSize) {
            currentFontSize = parseInt(savedFontSize, 10);
            applyFontSize(currentFontSize);
        }
        
        if (savedContrast === 'true') {
            isHighContrast = true;
            applyContrast(true);
        }
    }
    
    // Aplicar tamanho da fonte
    function applyFontSize(size) {
        const body = document.body;
        
        // Remover classes anteriores
        body.classList.remove('font-small', 'font-medium', 'font-large', 'font-xlarge', 'font-xxlarge');
        
        // Aplicar nova classe baseada no tamanho
        if (size < 95) {
            body.classList.add('font-small');
        } else if (size < 110) {
            body.classList.add('font-medium');
        } else if (size < 125) {
            body.classList.add('font-large');
        } else if (size < 140) {
            body.classList.add('font-xlarge');
        } else {
            body.classList.add('font-xxlarge');
        }
        
        // Atualizar valor exibido
        const valueElement = document.getElementById('font-size-value');
        if (valueElement) {
            valueElement.textContent = size + '%';
        }
        
        // Salvar preferência
        localStorage.setItem('accessibility_font_size', size.toString());
    }
    
    // Aplicar contraste
    function applyContrast(enabled) {
        const body = document.body;
        const html = document.documentElement;
        
        if (enabled) {
            body.classList.add('high-contrast');
            // Aplicar filter no html ao invés do body para evitar problemas com position: fixed
            // Mas precisamos aplicar apenas no conteúdo, não nos botões flutuantes
            // Criar um wrapper se não existir
            let wrapper = document.getElementById('content-wrapper');
            if (!wrapper) {
                // Criar wrapper para o conteúdo principal
                wrapper = document.createElement('div');
                wrapper.id = 'content-wrapper';
                wrapper.style.cssText = 'filter: contrast(1.5); min-height: 100vh;';
                
                // Mover todos os filhos do body para o wrapper, exceto os botões flutuantes
                const children = Array.from(body.children);
                children.forEach(child => {
                    if (!child.classList.contains('accessibility-float') && 
                        !child.classList.contains('language-float') && 
                        !child.classList.contains('whatsapp-float')) {
                        wrapper.appendChild(child);
                    }
                });
                body.appendChild(wrapper);
            } else {
                wrapper.style.filter = 'contrast(1.5)';
            }
        } else {
            body.classList.remove('high-contrast');
            const wrapper = document.getElementById('content-wrapper');
            if (wrapper) {
                wrapper.style.filter = '';
                // Se o wrapper foi criado por nós, restaurar estrutura original
                if (wrapper.parentNode === body) {
                    const wrapperChildren = Array.from(wrapper.children);
                    wrapperChildren.forEach(child => {
                        body.insertBefore(child, wrapper);
                    });
                    wrapper.remove();
                }
            }
        }
        
        // Atualizar label
        const labelElement = document.getElementById('contrast-label');
        if (labelElement) {
            const dataOn = labelElement.getAttribute('data-on');
            const dataOff = labelElement.getAttribute('data-off');
            if (enabled) {
                labelElement.textContent = dataOn || labelElement.getAttribute('data-text-on') || 'Alto Contraste Ativo';
            } else {
                labelElement.textContent = dataOff || labelElement.getAttribute('data-text-off') || 'Alto Contraste';
            }
        }
        
        // Salvar preferência
        localStorage.setItem('accessibility_high_contrast', enabled.toString());
    }
    
    // Aumentar fonte
    function increaseFont() {
        if (currentFontSize < MAX_FONT_SIZE) {
            currentFontSize = Math.min(currentFontSize + FONT_SIZE_STEP, MAX_FONT_SIZE);
            applyFontSize(currentFontSize);
        }
    }
    
    // Diminuir fonte
    function decreaseFont() {
        if (currentFontSize > MIN_FONT_SIZE) {
            currentFontSize = Math.max(currentFontSize - FONT_SIZE_STEP, MIN_FONT_SIZE);
            applyFontSize(currentFontSize);
        }
    }
    
    // Alternar contraste
    function toggleContrast() {
        isHighContrast = !isHighContrast;
        applyContrast(isHighContrast);
    }
    
    // Redefinir tudo
    function resetAccessibility() {
        currentFontSize = DEFAULT_FONT_SIZE;
        isHighContrast = false;
        applyFontSize(currentFontSize);
        applyContrast(false);
        localStorage.removeItem('accessibility_font_size');
        localStorage.removeItem('accessibility_high_contrast');
    }
    
    // Inicializar quando DOM estiver pronto
    function init() {
        // Carregar preferências salvas
        loadPreferences();
        
        // Elementos
        const btn = document.getElementById('accessibility-float-btn');
        const dropdown = document.getElementById('accessibility-options-float');
        const fontIncrease = document.getElementById('font-increase');
        const fontDecrease = document.getElementById('font-decrease');
        const contrastToggle = document.getElementById('contrast-toggle');
        const resetBtn = document.getElementById('accessibility-reset');
        
        if (!btn || !dropdown) return;
        
        // Toggle dropdown
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const isVisible = dropdown.style.display === 'block' || dropdown.classList.contains('active');
            
            if (isVisible) {
                dropdown.style.display = 'none';
                dropdown.classList.remove('active');
                btn.setAttribute('aria-expanded', 'false');
            } else {
                dropdown.style.display = 'block';
                dropdown.classList.add('active');
                btn.setAttribute('aria-expanded', 'true');
            }
        });
        
        // Fechar ao clicar fora
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.accessibility-float')) {
                dropdown.style.display = 'none';
                dropdown.classList.remove('active');
                btn.setAttribute('aria-expanded', 'false');
            }
        });
        
        // Controles de fonte
        if (fontIncrease) {
            fontIncrease.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                increaseFont();
            });
        }
        
        if (fontDecrease) {
            fontDecrease.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                decreaseFont();
            });
        }
        
        // Controle de contraste
        if (contrastToggle) {
            contrastToggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleContrast();
            });
        }
        
        // Botão reset
        if (resetBtn) {
            resetBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                resetAccessibility();
            });
        }
        
        // Fechar ao pressionar Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && (dropdown.style.display === 'block' || dropdown.classList.contains('active'))) {
                dropdown.style.display = 'none';
                dropdown.classList.remove('active');
                btn.setAttribute('aria-expanded', 'false');
                btn.focus();
            }
        });
    }
    
    // Aguardar DOM estar pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

