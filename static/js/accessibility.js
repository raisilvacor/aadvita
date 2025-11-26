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
    let isAudioDescEnabled = false;
    let clickTimeout = null;
    let lastClickedElement = null;
    let speechSynthesis = null;
    let maleVoice = null;
    
    // Inicializar Speech Synthesis e encontrar voz masculina
    function initSpeechSynthesis() {
        if ('speechSynthesis' in window) {
            speechSynthesis = window.speechSynthesis;
            
            // Aguardar vozes carregarem
            function loadVoices() {
                const voices = speechSynthesis.getVoices();
                
                // Procurar por voz masculina em português
                // Prioridade: português brasileiro masculina > português masculina > qualquer masculina
                maleVoice = voices.find(voice => 
                    (voice.lang.startsWith('pt') || voice.lang.startsWith('pt-BR')) && 
                    (voice.name.toLowerCase().includes('male') || 
                     voice.name.toLowerCase().includes('masculina') ||
                     voice.name.toLowerCase().includes('masculino') ||
                     voice.name.toLowerCase().includes('joão') ||
                     voice.name.toLowerCase().includes('carlos') ||
                     voice.name.toLowerCase().includes('paulo') ||
                     voice.name.toLowerCase().includes('ricardo') ||
                     voice.gender === 'male')
                ) || voices.find(voice => 
                    (voice.lang.startsWith('pt') || voice.lang.startsWith('pt-BR')) &&
                    !voice.name.toLowerCase().includes('female') &&
                    !voice.name.toLowerCase().includes('feminina') &&
                    !voice.name.toLowerCase().includes('maria') &&
                    !voice.name.toLowerCase().includes('helena') &&
                    !voice.name.toLowerCase().includes('lucia') &&
                    voice.gender !== 'female'
                ) || voices.find(voice => 
                    voice.lang.startsWith('pt')
                ) || voices.find(voice => 
                    voice.gender === 'male'
                ) || voices.find(voice => 
                    voice.name.toLowerCase().includes('male') || 
                    voice.name.toLowerCase().includes('masculina')
                ) || voices[0]; // Fallback para primeira voz disponível
            }
            
            // Carregar vozes (pode ser assíncrono)
            if (speechSynthesis.getVoices().length > 0) {
                loadVoices();
            } else {
                speechSynthesis.addEventListener('voiceschanged', loadVoices);
            }
        }
    }
    
    // Ler texto usando síntese de voz
    function speakText(text) {
        if (!speechSynthesis || !text || !isAudioDescEnabled) return;
        
        // Parar qualquer fala anterior
        speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        
        // Configurar voz masculina se disponível
        if (maleVoice) {
            utterance.voice = maleVoice;
        } else {
            // Tentar encontrar voz masculina novamente
            const voices = speechSynthesis.getVoices();
            maleVoice = voices.find(voice => 
                (voice.lang.startsWith('pt') || voice.lang.startsWith('pt-BR')) && 
                (voice.name.toLowerCase().includes('male') || 
                 voice.name.toLowerCase().includes('masculina') ||
                 voice.name.toLowerCase().includes('masculino') ||
                 voice.gender === 'male')
            ) || voices.find(voice => 
                voice.lang.startsWith('pt') &&
                !voice.name.toLowerCase().includes('female') &&
                !voice.name.toLowerCase().includes('feminina') &&
                voice.gender !== 'female'
            ) || voices.find(voice => voice.lang.startsWith('pt')) || voices[0];
            
            if (maleVoice) {
                utterance.voice = maleVoice;
            }
        }
        
        // Configurações de voz
        utterance.lang = 'pt-BR';
        utterance.rate = 1.0; // Velocidade normal
        utterance.pitch = 0.9; // Tom ligeiramente mais grave (masculino)
        utterance.volume = 1.0; // Volume máximo
        
        speechSynthesis.speak(utterance);
    }
    
    // Obter descrição completa de uma imagem (apenas descrições textuais reais)
    function getImageDescription(img) {
        if (!img || img.tagName !== 'IMG') return '';
        
        const parts = [];
        
        // 1. Alt text (prioridade máxima - descrição textual fornecida)
        // Ignorar se for apenas nome de arquivo ou vazio
        if (img.alt && img.alt.trim()) {
            const altText = img.alt.trim();
            // Verificar se não é apenas um nome de arquivo
            const isFileName = /^[a-z0-9_-]+\.(jpg|jpeg|png|gif|webp|svg)$/i.test(altText);
            if (!isFileName && altText !== 'undefined' && altText.length > 2) {
                parts.push(altText);
            }
        }
        
        // 2. Title
        if (img.title && img.title.trim()) {
            parts.push(img.title.trim());
        }
        
        // 3. Aria-label
        const ariaLabel = img.getAttribute('aria-label');
        if (ariaLabel && ariaLabel.trim()) {
            parts.push(ariaLabel.trim());
        }
        
        // 4. Buscar contexto próximo (título, descrição, etc.)
        let contextText = '';
        let parent = img.parentElement;
        
        if (parent) {
            // Procurar em parent com data-title ou aria-label
            const dataTitle = parent.getAttribute('data-title');
            if (dataTitle && dataTitle.trim()) {
                contextText = dataTitle.trim();
            } else {
                const parentAriaLabel = parent.getAttribute('aria-label');
                if (parentAriaLabel && parentAriaLabel.trim()) {
                    contextText = parentAriaLabel.trim();
                }
            }
            
            // Procurar em overlay de imagem
            if (!contextText) {
                const overlay = parent.querySelector('.image-overlay, .overlay, .caption, .image-title, .image-subtitle');
                if (overlay) {
                    const overlayText = overlay.textContent || overlay.innerText;
                    if (overlayText && overlayText.trim()) {
                        contextText = overlayText.trim();
                    }
                }
            }
            
            // Procurar em elementos com classe de título/descrição
            if (!contextText) {
                const titleEl = parent.querySelector('.title, .image-title, .photo-title, .gallery-title, .slider-title');
                if (titleEl) {
                    const titleText = titleEl.textContent || titleEl.innerText;
                    if (titleText && titleText.trim()) {
                        contextText = titleText.trim();
                    }
                }
                
                const descEl = parent.querySelector('.description, .image-description, .photo-description, .caption, .slider-description');
                if (descEl) {
                    const descText = descEl.textContent || descEl.innerText;
                    if (descText && descText.trim()) {
                        contextText = (contextText ? contextText + '. ' : '') + descText.trim();
                    }
                }
            }
        }
        
        // 5. Buscar em elementos próximos (antes ou depois)
        if (!contextText) {
            const nextSibling = img.nextElementSibling;
            if (nextSibling) {
                const siblingText = nextSibling.textContent || nextSibling.innerText;
                if (siblingText && siblingText.trim() && siblingText.trim().length < 200) {
                    contextText = siblingText.trim();
                }
            }
            
            if (!contextText) {
                const prevSibling = img.previousElementSibling;
                if (prevSibling) {
                    const siblingText = prevSibling.textContent || prevSibling.innerText;
                    if (siblingText && siblingText.trim() && siblingText.trim().length < 200) {
                        contextText = siblingText.trim();
                    }
                }
            }
        }
        
        // 6. Buscar em elementos pais mais distantes (avô, etc.)
        if (!contextText && parent) {
            const grandParent = parent.parentElement;
            if (grandParent) {
                const grandParentText = grandParent.textContent || grandParent.innerText;
                if (grandParentText && grandParentText.trim() && grandParentText.trim().length < 300) {
                    // Remover texto da imagem atual para evitar duplicação
                    const cleanText = grandParentText.replace(img.alt || '', '').trim();
                    if (cleanText && cleanText.length > 10) {
                        contextText = cleanText.substring(0, 200).trim();
                    }
                }
            }
        }
        
        // Combinar todas as informações
        if (parts.length > 0) {
            let description = parts.join('. ');
            if (contextText && !parts.some(p => contextText.includes(p))) {
                description += '. ' + contextText;
            }
            return description;
        }
        
        // Se temos contexto, usar ele
        if (contextText) {
            return contextText;
        }
        
        // Se não há descrição disponível, informar
        return 'Imagem sem descrição disponível. Por favor, adicione um texto alternativo (alt) descrevendo o conteúdo da imagem.';
    }
    
    // Obter texto de um elemento para leitura
    function getElementText(element) {
        if (!element) return '';
        
        // Tratamento especial para imagens - descrição completa
        if (element.tagName === 'IMG') {
            return getImageDescription(element);
        }
        
        // Priorizar aria-label
        if (element.getAttribute('aria-label')) {
            return element.getAttribute('aria-label');
        }
        
        // Priorizar title
        if (element.title) {
            return element.title;
        }
        
        // Obter texto visível
        let text = '';
        
        // Se for input, textarea ou select, usar value ou selected option
        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
            if (element.type === 'button' || element.type === 'submit' || element.type === 'reset') {
                text = element.value || element.textContent || '';
            } else if (element.type === 'checkbox' || element.type === 'radio') {
                const label = element.closest('label') || document.querySelector(`label[for="${element.id}"]`);
                if (label) {
                    text = label.textContent.trim();
                } else {
                    text = element.value || element.getAttribute('aria-label') || '';
                }
            } else {
                text = element.value || element.placeholder || '';
            }
        } else if (element.tagName === 'SELECT') {
            const selectedOption = element.options[element.selectedIndex];
            text = selectedOption ? selectedOption.text : '';
        } else {
            // Para outros elementos, pegar texto visível
            text = element.textContent || element.innerText || '';
        }
        
        // Limpar texto (remover espaços extras, quebras de linha, etc)
        text = text.trim().replace(/\s+/g, ' ').replace(/\n+/g, ' ');
        
        // Se não houver texto, tentar pegar do primeiro filho com texto
        if (!text && element.children.length > 0) {
            for (let child of element.children) {
                // Ignorar imagens nos filhos para evitar loops
                if (child.tagName !== 'IMG') {
                    const childText = getElementText(child);
                    if (childText) {
                        text = childText;
                        break;
                    }
                }
            }
        }
        
        return text;
    }
    
    // Carregar preferências do localStorage
    function loadPreferences() {
        const savedFontSize = localStorage.getItem('accessibility_font_size');
        const savedContrast = localStorage.getItem('accessibility_high_contrast');
        const savedAudioDesc = localStorage.getItem('accessibility_audio_desc');
        
        if (savedFontSize) {
            currentFontSize = parseInt(savedFontSize, 10);
            applyFontSize(currentFontSize);
        }
        
        if (savedContrast === 'true') {
            isHighContrast = true;
            applyContrast(true);
        }
        
        if (savedAudioDesc === 'true') {
            isAudioDescEnabled = true;
            enableAudioDesc(true);
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
        
        if (enabled) {
            body.classList.add('high-contrast');
            // Aplicar filter apenas em elementos específicos, não no body
            // Isso evita problemas com position: fixed
            const elementsToFilter = document.querySelectorAll('body > *:not(.accessibility-float):not(.language-float):not(.whatsapp-float)');
            elementsToFilter.forEach(el => {
                el.style.filter = 'contrast(1.5)';
                el.setAttribute('data-high-contrast', 'true');
            });
        } else {
            body.classList.remove('high-contrast');
            // Remover filter de todos os elementos que receberam
            const elementsWithFilter = document.querySelectorAll('[data-high-contrast="true"]');
            elementsWithFilter.forEach(el => {
                el.style.filter = '';
                el.removeAttribute('data-high-contrast');
            });
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
    
    // Habilitar/desabilitar áudio descrição
    function enableAudioDesc(enabled) {
        isAudioDescEnabled = enabled;
        
        if (enabled) {
            document.body.classList.add('audio-desc-enabled');
            // Adicionar listeners para cliques
            document.addEventListener('click', handleClickWithAudioDesc, true);
            document.addEventListener('touchstart', handleTouchWithAudioDesc, true);
        } else {
            document.body.classList.remove('audio-desc-enabled');
            // Remover listeners
            document.removeEventListener('click', handleClickWithAudioDesc, true);
            document.removeEventListener('touchstart', handleTouchWithAudioDesc, true);
            // Parar qualquer fala em andamento
            if (speechSynthesis) {
                speechSynthesis.cancel();
            }
            // Limpar timeouts
            if (clickTimeout) {
                clearTimeout(clickTimeout);
                clickTimeout = null;
            }
            lastClickedElement = null;
        }
        
        // Atualizar label
        const labelElement = document.getElementById('audio-desc-label');
        if (labelElement) {
            if (enabled) {
                labelElement.textContent = labelElement.getAttribute('data-on') || 'Áudio Descrição Ativa';
            } else {
                labelElement.textContent = labelElement.getAttribute('data-off') || 'Áudio Descrição';
            }
        }
        
        // Salvar preferência
        localStorage.setItem('accessibility_audio_desc', enabled.toString());
    }
    
    // Alternar áudio descrição
    function toggleAudioDesc() {
        enableAudioDesc(!isAudioDescEnabled);
    }
    
    // Manipular clique com áudio descrição
    function handleClickWithAudioDesc(e) {
        // Ignorar cliques nos botões de acessibilidade
        if (e.target.closest('.accessibility-float') || 
            e.target.closest('.language-float') || 
            e.target.closest('.whatsapp-float')) {
            return;
        }
        
        const target = e.target;
        
        // Verificar se é o mesmo elemento clicado anteriormente
        if (lastClickedElement === target && clickTimeout) {
            // Segundo clique - executar ação normal
            clearTimeout(clickTimeout);
            clickTimeout = null;
            lastClickedElement = null;
            // Permitir que o evento continue normalmente
            return;
        }
        
        // Primeiro clique - ler o texto
        e.preventDefault();
        e.stopPropagation();
        
        // Parar qualquer fala anterior
        if (speechSynthesis) {
            speechSynthesis.cancel();
        }
        
        // Obter texto do elemento
        const text = getElementText(target);
        
        if (text) {
            speakText(text);
        }
        
        // Armazenar elemento clicado
        lastClickedElement = target;
        
        // Limpar timeout anterior se existir
        if (clickTimeout) {
            clearTimeout(clickTimeout);
        }
        
        // Definir timeout para resetar após 2 segundos
        clickTimeout = setTimeout(() => {
            lastClickedElement = null;
            clickTimeout = null;
        }, 2000);
    }
    
    // Manipular touch com áudio descrição
    function handleTouchWithAudioDesc(e) {
        // Ignorar toques nos botões de acessibilidade
        if (e.target.closest('.accessibility-float') || 
            e.target.closest('.language-float') || 
            e.target.closest('.whatsapp-float')) {
            return;
        }
        
        const target = e.target;
        
        // Verificar se é o mesmo elemento tocado anteriormente
        if (lastClickedElement === target && clickTimeout) {
            // Segundo toque - executar ação normal
            clearTimeout(clickTimeout);
            clickTimeout = null;
            lastClickedElement = null;
            // Permitir que o evento continue normalmente
            return;
        }
        
        // Primeiro toque - ler o texto
        e.preventDefault();
        e.stopPropagation();
        
        // Parar qualquer fala anterior
        if (speechSynthesis) {
            speechSynthesis.cancel();
        }
        
        // Obter texto do elemento
        const text = getElementText(target);
        
        if (text) {
            speakText(text);
        }
        
        // Armazenar elemento tocado
        lastClickedElement = target;
        
        // Limpar timeout anterior se existir
        if (clickTimeout) {
            clearTimeout(clickTimeout);
        }
        
        // Definir timeout para resetar após 2 segundos
        clickTimeout = setTimeout(() => {
            lastClickedElement = null;
            clickTimeout = null;
        }, 2000);
    }
    
    // Redefinir tudo
    function resetAccessibility() {
        currentFontSize = DEFAULT_FONT_SIZE;
        isHighContrast = false;
        isAudioDescEnabled = false;
        applyFontSize(currentFontSize);
        applyContrast(false);
        enableAudioDesc(false);
        localStorage.removeItem('accessibility_font_size');
        localStorage.removeItem('accessibility_high_contrast');
        localStorage.removeItem('accessibility_audio_desc');
    }
    
    // Inicializar quando DOM estiver pronto
    function init() {
        // Inicializar Speech Synthesis
        initSpeechSynthesis();
        
        // Carregar preferências salvas
        loadPreferences();
        
        // Elementos
        const btn = document.getElementById('accessibility-float-btn');
        const dropdown = document.getElementById('accessibility-options-float');
        const fontIncrease = document.getElementById('font-increase');
        const fontDecrease = document.getElementById('font-decrease');
        const contrastToggle = document.getElementById('contrast-toggle');
        const audioDescToggle = document.getElementById('audio-desc-toggle');
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
        
        // Controle de áudio descrição
        if (audioDescToggle) {
            audioDescToggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleAudioDesc();
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

