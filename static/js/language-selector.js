// Seletor de Idioma - Solução Profissional e Robusta
(function() {
    'use strict';
    
    // Aguardar DOM estar pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLanguageSelector);
    } else {
        initLanguageSelector();
    }
    
    function initLanguageSelector() {
        const langBtn = document.getElementById("selected-lang");
        const langOptions = document.getElementById("lang-options");
        
        if (!langBtn || !langOptions) {
            console.warn('Elementos do seletor de idioma não encontrados');
            return;
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
            if (!e.target.closest('.language-selector')) {
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
