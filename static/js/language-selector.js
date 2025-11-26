// Seletor de Idioma - Solução Profissional e Robusta
(function() {
    'use strict';
    
    // Aguardar DOM estar pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLanguageSelectors);
    } else {
        initLanguageSelectors();
    }
    
    function initLanguageSelectors() {
        // Inicializar seletor do menu (se existir)
        initLanguageSelector('selected-lang', 'lang-options', '.language-selector');
        
        // Inicializar seletor flutuante
        initLanguageSelector('selected-lang-float', 'lang-options-float', '.language-float');
    }
    
    function initLanguageSelector(btnId, optionsId, containerSelector) {
        const langBtn = document.getElementById(btnId);
        const langOptions = document.getElementById(optionsId);
        
        if (!langBtn || !langOptions) {
            return; // Elementos não existem, pular
        }
        
        // Toggle do dropdown ao clicar no botão
        langBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const isVisible = langOptions.style.display === 'block' || langOptions.classList.contains('active');
            
            if (isVisible) {
                hideDropdown();
            } else {
                showDropdown();
            }
        });
        
        // Fechar dropdown ao clicar fora
        document.addEventListener('click', function(e) {
            if (!e.target.closest(containerSelector)) {
                hideDropdown();
            }
        });
        
        // Prevenir que cliques dentro do dropdown o fechem
        langOptions.addEventListener('click', function(e) {
            e.stopPropagation();
            // Permitir que os links funcionem normalmente
        });
        
        // Fechar ao pressionar Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && isDropdownVisible()) {
                hideDropdown();
                langBtn.focus();
            }
        });
        
        function showDropdown() {
            langOptions.style.display = 'block';
            langOptions.classList.add('active');
            langBtn.setAttribute('aria-expanded', 'true');
        }
        
        function hideDropdown() {
            langOptions.style.display = 'none';
            langOptions.classList.remove('active');
            langBtn.setAttribute('aria-expanded', 'false');
        }
        
        function isDropdownVisible() {
            return langOptions.style.display === 'block' || langOptions.classList.contains('active');
        }
        
        // Garantir que comece fechado
        hideDropdown();
    }
})();
