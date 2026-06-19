document.addEventListener('DOMContentLoaded', () => {
    let db = null;
    let firebaseInitialized = false;
    let currentLang = 'zh';
    let translations = {};

    // Load Firebase configuration from FastAPI backend
    const initFirebase = async () => {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            if (data.firebase_config && data.firebase_config.apiKey) {
                firebase.initializeApp(data.firebase_config);
                db = firebase.firestore();
                firebaseInitialized = true;
                console.log("Firebase initialized successfully from remote config.");
            } else {
                console.warn("Firebase configuration was empty. Local dev mode or missing env vars.");
            }
        } catch (err) {
            console.error("Failed to load Firebase configuration: ", err);
        }
    };

    const loadLanguage = async (lang) => {
        try {
            let res = await fetch(`/lang/${lang}.json`);
            if (!res.ok) {
                res = await fetch(`/static/lang/${lang}.json`);
            }
            translations = await res.json();
            currentLang = lang;
            const selectEl = document.getElementById('lang-select');
            if (selectEl) selectEl.value = lang;
            localStorage.setItem('preferred_language', lang);
            applyTranslations();
            console.log(`Language loaded: ${lang}`);
        } catch (err) {
            console.error("Failed to load language: ", err);
        }
    };

    const applyTranslations = () => {
        // Translate elements with data-i18n
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (translations[key]) {
                el.textContent = translations[key];
            }
        });

        // Translate elements with data-i18n-html
        document.querySelectorAll('[data-i18n-html]').forEach(el => {
            const key = el.getAttribute('data-i18n-html');
            if (translations[key]) {
                el.innerHTML = translations[key];
            }
        });

        // Translate placeholders
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (translations[key]) {
                el.placeholder = translations[key];
            }
        });

        // Update document title
        if (translations['document_title']) {
            document.title = translations['document_title'];
        }
    };

    const detectLanguage = () => {
        const saved = localStorage.getItem('preferred_language');
        if (saved) return saved;
        
        const sysLang = navigator.language || navigator.userLanguage || 'zh';
        if (sysLang.toLowerCase().startsWith('zh')) {
            return 'zh';
        }
        return 'en';
    };

    // Bind lang-select change
    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
        langSelect.addEventListener('change', (e) => {
            loadLanguage(e.target.value);
        });
    }

    initFirebase();
    const initialLang = detectLanguage();
    loadLanguage(initialLang);

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('preview-container');
    const dropZoneContent = document.querySelector('.drop-zone-content');
    const questionInput = document.getElementById('question-input');
    const submitBtn = document.getElementById('submit-btn');
    const analyzeForm = document.getElementById('analyze-form');
    
    const inviteInput = document.getElementById('invite-input');
    const quotaBadge = document.getElementById('quota-badge');
    
    // Automatically populate invite code from URL query parameters (?code=XXX or ?invite=XXX)
    const urlParams = new URLSearchParams(window.location.search);
    const codeParam = urlParams.get('code') || urlParams.get('invite');
    if (codeParam && inviteInput) {
        inviteInput.value = codeParam.trim().toUpperCase();
        // Trigger input event to update submit button disabled state
        setTimeout(() => {
            inviteInput.dispatchEvent(new Event('input'));
        }, 100);
    }
    
    // Result panels
    const statusBadge = document.getElementById('status-badge');
    const resultIdle = document.getElementById('result-idle');
    const resultLoading = document.getElementById('result-loading');
    const resultSuccess = document.getElementById('result-success');
    const reportBody = document.getElementById('report-body');
    
    // Action Bar Buttons
    const copyReportBtn = document.getElementById('copy-report-btn');
    const printPdfBtn = document.getElementById('print-pdf-btn');
    
    let selectedFile = null;
    let currentAnalysisText = '';

    // --- Action Bar Listeners ---
    copyReportBtn.addEventListener('click', async () => {
        if (!currentAnalysisText) return;
        try {
            await navigator.clipboard.writeText(currentAnalysisText);
            const originalText = copyReportBtn.innerHTML;
            const successText = translations['copied_success'] || '已複製！';
            copyReportBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="currentColor"/>
                </svg>
                <span>${successText}</span>
            `;
            copyReportBtn.classList.add('copied');
            setTimeout(() => {
                copyReportBtn.innerHTML = originalText;
                copyReportBtn.classList.remove('copied');
            }, 1500);
        } catch (err) {
            const failAlert = currentLang === 'en' ? 'Copy failed, please select and copy manually.' : '複製失敗，請手動選取複製。';
            alert(failAlert);
        }
    });

    printPdfBtn.addEventListener('click', () => {
        window.print();
    });

    // --- Drag and Drop Listeners ---
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // --- File Handling & Preview ---
    function handleFileSelect(file) {
        // Validate file type
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf'];
        if (!validTypes.includes(file.type)) {
            const formatAlert = currentLang === 'en' ? 'Unsupported file format! Please upload PNG, JPG, JPEG image or PDF file.' : '不支援的檔案格式！請上傳 PNG, JPG, JPEG 圖片或 PDF 檔案。';
            alert(formatAlert);
            return;
        }

        selectedFile = file;
        
        // Hide drop zone instruction, show preview
        dropZoneContent.classList.add('hidden');
        previewContainer.classList.remove('hidden');
        
        // Create preview element
        previewContainer.innerHTML = '';
        
        const previewCard = document.createElement('div');
        previewCard.className = 'preview-card';
        
        if (file.type === 'application/pdf') {
            previewCard.innerHTML = `
                <div class="preview-pdf-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3ZM19 19H5V5H19V19ZM16 12H8V14H16V12ZM16 8H8V10H16V8ZM13 16H8V18H13V16Z" fill="currentColor"/>
                    </svg>
                </div>
                <div class="preview-info">
                    <div class="preview-name">${file.name}</div>
                    <div class="preview-size">${formatBytes(file.size)}</div>
                </div>
                <button type="button" class="remove-btn" id="remove-file-btn">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="currentColor"/>
                    </svg>
                </button>
            `;
        } else {
            const objectUrl = URL.createObjectURL(file);
            previewCard.innerHTML = `
                <img src="${objectUrl}" class="preview-thumbnail" alt="Preview">
                <div class="preview-info">
                    <div class="preview-name">${file.name}</div>
                    <div class="preview-size">${formatBytes(file.size)}</div>
                </div>
                <button type="button" class="remove-btn" id="remove-file-btn">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="currentColor"/>
                    </svg>
                </button>
            `;
        }
        
        previewContainer.appendChild(previewCard);
        
        // Add remove listener
        document.getElementById('remove-file-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            removeSelectedFile();
        });

        checkFormValidity();
    }

    function removeSelectedFile() {
        selectedFile = null;
        fileInput.value = '';
        previewContainer.classList.add('hidden');
        previewContainer.innerHTML = '';
        dropZoneContent.classList.remove('hidden');
        checkFormValidity();
    }

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // --- Form Validation ---
    function checkFormValidity() {
        const hasFile = selectedFile !== null;
        const hasQuestion = questionInput.value.trim().length > 0;
        const hasInvite = inviteInput.value.trim().length > 0;
        submitBtn.disabled = !(hasFile && hasQuestion && hasInvite);
    }

    questionInput.addEventListener('input', checkFormValidity);
    inviteInput.addEventListener('input', checkFormValidity);

    // --- Submit Form ---
    let isProcessingAsync = false;

    const restoreFormUI = () => {
        submitBtn.disabled = false;
        questionInput.disabled = false;
        inviteInput.disabled = false;
        if (document.getElementById('remove-file-btn')) {
            document.getElementById('remove-file-btn').disabled = false;
        }
        checkFormValidity();
        const submitText = translations['submit_btn_text'] || '開始智慧分析';
        submitBtn.innerHTML = `
            <span>${submitText}</span>
            <svg class="arrow-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    };

    analyzeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!selectedFile || !questionInput.value.trim() || !inviteInput.value.trim()) return;

        // UI States
        submitBtn.disabled = true;
        questionInput.disabled = true;
        inviteInput.disabled = true;
        if (document.getElementById('remove-file-btn')) {
            document.getElementById('remove-file-btn').disabled = true;
        }
        
        const loadingTaskText = currentLang === 'en' ? 'Creating analysis task...' : '建立分析任務...';
        submitBtn.innerHTML = `
            <span>${loadingTaskText}</span>
        `;
        
        statusBadge.textContent = translations['status_badge_processing'] || '分析中...';
        statusBadge.className = 'status-badge analyzing';
        
        resultIdle.classList.add('hidden');
        resultSuccess.classList.add('hidden');
        resultLoading.classList.remove('hidden');

        // Create FormData
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('question', questionInput.value.trim());
        formData.append('invite_code', inviteInput.value.trim());
        formData.append('lang', currentLang);

        isProcessingAsync = false;

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'NETWORK_ERROR');
            }

            // Render Quota Badge
            if (data.remaining_quota !== undefined) {
                const quotaCountEl = document.getElementById('quota-count');
                if (quotaCountEl) {
                    quotaCountEl.textContent = data.remaining_quota;
                } else {
                    quotaBadge.textContent = `剩餘額度: ${data.remaining_quota} 次`;
                }
                quotaBadge.style.display = 'inline-block';
            } else {
                quotaBadge.style.display = 'none';
            }

            const taskId = data.task_id;
            if (!taskId) {
                throw new Error(currentLang === 'en' ? 'Failed to get Task ID. Cannot track status.' : '未取得 Task ID，無法追蹤分析狀態。');
            }

            if (!firebaseInitialized || !db) {
                throw new Error(currentLang === 'en' ? 'Firebase not initialized yet. Please verify GCP access.' : 'Firebase 尚未初始化完成，無法即時監聽分析狀態。請確認 GCP 存取權限。');
            }

            isProcessingAsync = true;
            submitBtn.innerHTML = `
                <span>${currentLang === 'en' ? 'AI Analysis & Retrieval...' : 'AI 分析與檢索中...'}</span>
            `;

            // Subscribe to task updates in Firestore
            const unsubscribe = db.collection("analysis_tasks").doc(taskId).onSnapshot((doc) => {
                if (!doc.exists) return;
                const taskData = doc.data();

                if (taskData.status === 'processing') {
                    statusBadge.textContent = translations['status_badge_processing'] || '分析與檢索中...';
                    statusBadge.className = 'status-badge analyzing';
                } else if (taskData.status === 'success') {
                    unsubscribe(); // Stop listening
                    isProcessingAsync = false;

                    // Success UI
                    statusBadge.textContent = translations['status_badge_success'] || '分析完成';
                    statusBadge.className = 'status-badge success';
                    resultLoading.classList.add('hidden');
                    resultSuccess.classList.remove('hidden');

                    // Save analysis text for copy function
                    currentAnalysisText = taskData.result;

                    // Render Markdown Cards
                    const renderer = new marked.Renderer();
                    renderer.link = (href, title, text) => {
                        return `<a href="${href}" title="${title || ''}" target="_blank" rel="noopener noreferrer">${text}</a>`;
                    };
                    marked.setOptions({ renderer: renderer });
                    
                    reportBody.innerHTML = '';
                    
                    // Split markdown by H2 headers "## "
                    const rawSections = taskData.result.split(/^(?=##\s+)/m);
                    rawSections.forEach(section => {
                        const trimmed = section.trim();
                        if (!trimmed) return;
                        
                        const card = document.createElement('div');
                        card.className = 'result-card';
                        card.innerHTML = marked.parse(trimmed);
                        reportBody.appendChild(card);
                    });

                    restoreFormUI();

                } else if (taskData.status === 'failed') {
                    unsubscribe(); // Stop listening
                    isProcessingAsync = false;

                    // Error UI
                    statusBadge.textContent = translations['status_badge_failed'] || '發生錯誤';
                    statusBadge.className = 'status-badge idle';
                    resultLoading.classList.add('hidden');
                    resultIdle.classList.remove('hidden');
                    quotaBadge.style.display = 'none';
                    
                    const errMsg = translations[taskData.error] || taskData.error || translations['UNKNOWN_ERROR'] || '背景分析發生未知錯誤。';
                    const errTitle = translations['error_title'] || '分析失敗';
                    alert(`${errTitle}: ${errMsg}`);
                    restoreFormUI();
                }
            }, (error) => {
                unsubscribe();
                isProcessingAsync = false;
                console.error("Firestore subscription error: ", error);
                
                statusBadge.textContent = translations['status_badge_failed'] || '發生錯誤';
                statusBadge.className = 'status-badge idle';
                resultLoading.classList.add('hidden');
                resultIdle.classList.remove('hidden');
                alert(`Subscription Error: ${error.message}`);
                restoreFormUI();
            });

        } catch (error) {
            isProcessingAsync = false;
            // Error UI
            statusBadge.textContent = translations['status_badge_failed'] || '發生錯誤';
            statusBadge.className = 'status-badge idle';
            resultLoading.classList.add('hidden');
            resultIdle.classList.remove('hidden');
            quotaBadge.style.display = 'none';
            
            const errMsg = translations[error.message] || error.message || translations['UNKNOWN_ERROR'] || '發生錯誤。';
            const errTitle = translations['error_title'] || '分析失敗';
            alert(`${errTitle}: ${errMsg}`);
        } finally {
            if (!isProcessingAsync) {
                restoreFormUI();
            }
        }
    });

    // --- Admin Modal Logic ---
    const adminEntranceBtn = document.getElementById('admin-entrance-btn');
    if (adminEntranceBtn) {
    const adminModal = document.getElementById('admin-modal');
    const closeAdminBtn = document.getElementById('close-admin-btn');
    const adminUploadForm = document.getElementById('admin-upload-form');
    const adminTokenInput = document.getElementById('admin-token-input');
    const adminDropZone = document.getElementById('admin-drop-zone');
    const adminFileInput = document.getElementById('admin-file-input');
    const adminDropZoneContent = document.getElementById('admin-drop-zone-content');
    const adminPreviewContainer = document.getElementById('admin-preview-container');
    const syncMonitor = document.getElementById('sync-monitor');
    const adminSubmitBtn = document.getElementById('admin-submit-btn');
    const pollingInfo = document.getElementById('polling-info');
    
    // Tabs Elements
    const tabKb = document.getElementById('tab-kb');
    const tabResearch = document.getElementById('tab-research');
    const tabContentKb = document.getElementById('tab-content-kb');
    const tabContentResearch = document.getElementById('tab-content-research');
    const accuracyPercentage = document.getElementById('accuracy-percentage');
    const accuracyBar = document.getElementById('accuracy-bar');
    const keywordListContainer = document.getElementById('keyword-list-container');
    
    const stepUpload = document.getElementById('step-upload');
    const stepTrigger = document.getElementById('step-trigger');
    const stepSync = document.getElementById('step-sync');
    
    let adminFile = null;
    let pollingIntervalId = null;

    // Show/Hide Modal
    adminEntranceBtn.addEventListener('click', () => {
        adminModal.classList.remove('hidden');
    });

    const closeAdminModal = () => {
        adminModal.classList.add('hidden');
        resetAdminForm();
    };

    closeAdminBtn.addEventListener('click', closeAdminModal);
    adminModal.addEventListener('click', (e) => {
        if (e.target === adminModal) {
            closeAdminModal();
        }
    });

    const resetAdminForm = () => {
        adminFile = null;
        adminFileInput.value = '';
        adminTokenInput.value = '';
        adminPreviewContainer.classList.add('hidden');
        adminPreviewContainer.innerHTML = '';
        adminDropZoneContent.classList.remove('hidden');
        syncMonitor.classList.add('hidden');
        if (pollingIntervalId) {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
        }
        resetSteps();
        checkAdminFormValidity();
        switchTab('kb'); // 切換回預設 Tab
    };

    // Tab switching logic
    const switchTab = (tab) => {
        if (tab === 'kb') {
            tabKb.classList.add('active');
            tabKb.style.color = '#fff';
            tabKb.style.borderBottomColor = '#3b82f6';
            
            tabResearch.classList.remove('active');
            tabResearch.style.color = 'rgba(255, 255, 255, 0.6)';
            tabResearch.style.borderBottomColor = 'transparent';
            
            tabContentKb.classList.remove('hidden');
            tabContentResearch.classList.add('hidden');
        } else if (tab === 'research') {
            tabResearch.classList.add('active');
            tabResearch.style.color = '#fff';
            tabResearch.style.borderBottomColor = '#3b82f6';
            
            tabKb.classList.remove('active');
            tabKb.style.color = 'rgba(255, 255, 255, 0.6)';
            tabKb.style.borderBottomColor = 'transparent';
            
            tabContentResearch.classList.remove('hidden');
            tabContentKb.classList.add('hidden');
            
            loadResearchStats(); // 載入統計數據
        }
    };

    tabKb.addEventListener('click', () => switchTab('kb'));
    tabResearch.addEventListener('click', () => switchTab('research'));

    // Load research statistics from API
    const loadResearchStats = async () => {
        const token = adminTokenInput.value.trim();
        if (!token) {
            keywordListContainer.innerHTML = `<div style="text-align: center; color: rgba(255,255,255,0.4); padding: 20px 0;">請先在「知識庫管理」頁面輸入管理憑證 Token</div>`;
            accuracyPercentage.textContent = '--%';
            accuracyBar.style.width = '0%';
            return;
        }
        
        keywordListContainer.innerHTML = `<div style="text-align: center; color: rgba(255,255,255,0.4); padding: 20px 0;">載入統計數據中...</div>`;
        
        try {
            const response = await fetch(`/api/admin/research-stats?token=${encodeURIComponent(token)}`);
            const data = await response.json();
            
            if (!data.success) {
                keywordListContainer.innerHTML = `<div style="text-align: center; color: #ef4444; padding: 20px 0;">載入失敗：${data.error || '未知錯誤'}</div>`;
                accuracyPercentage.textContent = '--%';
                accuracyBar.style.width = '0%';
                return;
            }
            
            // 1. Render Accuracy Percentage
            const acc = data.average_accuracy;
            accuracyPercentage.textContent = `${acc}%`;
            accuracyBar.style.width = `${acc}%`;
            if (acc >= 90) {
                accuracyPercentage.style.color = '#10b981';
            } else if (acc >= 75) {
                accuracyPercentage.style.color = '#f59e0b';
            } else {
                accuracyPercentage.style.color = '#ef4444';
            }
            
            // 2. Render Keywords Chart
            const kws = data.keyword_stats;
            if (!kws || kws.length === 0) {
                keywordListContainer.innerHTML = `<div style="text-align: center; color: rgba(255,255,255,0.4); padding: 20px 0;">尚無關鍵字統計研究數據</div>`;
                return;
            }
            
            const maxCount = Math.max(...kws.map(k => k.count), 1);
            
            let html = '';
            kws.forEach(k => {
                const percentage = (k.count / maxCount) * 100;
                html += `
                    <div style="margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.02); padding-bottom: 8px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:0.85rem;">
                            <span style="font-weight:500;">${k.keyword} <span style="color:#3b82f6;">(${k.count}次)</span></span>
                            <span style="color:rgba(255,255,255,0.45); font-size:0.75rem;">提問: ${k.question_count}次 | 報告: ${k.report_count}次</span>
                        </div>
                        <div style="width:100%; height:6px; background:rgba(255, 255, 255, 0.05); border-radius:3px; overflow:hidden;">
                            <div style="width: ${percentage}%; height:100%; background:linear-gradient(90deg, #3b82f6, #60a5fa); border-radius:3px; transition: width 0.5s ease-out;"></div>
                        </div>
                    </div>
                `;
            });
            keywordListContainer.innerHTML = html;
        } catch (error) {
            console.error("Failed to load research stats: ", error);
            keywordListContainer.innerHTML = `<div style="text-align: center; color: #ef4444; padding: 20px 0;">網路連線錯誤，無法載入數據。</div>`;
        }
    };

    const resetSteps = () => {
        [stepUpload, stepTrigger, stepSync].forEach(step => {
            step.className = 'step-item';
            step.querySelector('.step-status-icon').textContent = '⏳';
        });
        pollingInfo.textContent = 'Operation: --';
    };

    const setStepState = (step, state) => {
        step.className = `step-item ${state}`;
        const icon = step.querySelector('.step-status-icon');
        if (state === 'active') {
            icon.textContent = '🔄';
        } else if (state === 'success') {
            icon.textContent = '✅';
        } else if (state === 'failed') {
            icon.textContent = '❌';
        } else {
            icon.textContent = '⏳';
        }
    };

    // Form validation
    const checkAdminFormValidity = () => {
        const hasToken = adminTokenInput.value.trim().length > 0;
        const hasFile = adminFile !== null;
        adminSubmitBtn.disabled = !(hasToken && hasFile);
    };

    adminTokenInput.addEventListener('input', checkAdminFormValidity);

    // Admin Drag & Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        adminDropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            adminDropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        adminDropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            adminDropZone.classList.remove('dragover');
        }, false);
    });

    adminDropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleAdminFileSelect(files[0]);
        }
    });

    adminFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleAdminFileSelect(e.target.files[0]);
        }
    });

    const handleAdminFileSelect = (file) => {
        if (file.type !== 'application/pdf') {
            alert('知識庫手冊僅支援 PDF 格式！');
            return;
        }
        adminFile = file;
        adminDropZoneContent.classList.add('hidden');
        adminPreviewContainer.classList.remove('hidden');
        adminPreviewContainer.innerHTML = `
            <div class="preview-card" style="max-width:100%;">
                <div class="preview-pdf-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3ZM19 19H5V5H19V19ZM16 12H8V14H16V12ZM16 8H8V10H16V8ZM13 16H8V18H13V16Z" fill="currentColor"/>
                    </svg>
                </div>
                <div class="preview-info">
                    <div class="preview-name">${file.name}</div>
                    <div class="preview-size">${formatBytes(file.size)}</div>
                </div>
                <button type="button" class="remove-btn" id="remove-admin-file-btn">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="currentColor"/>
                    </svg>
                </button>
            </div>
        `;
        document.getElementById('remove-admin-file-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            removeAdminFile();
        });
        checkAdminFormValidity();
    };

    const removeAdminFile = () => {
        adminFile = null;
        adminFileInput.value = '';
        adminPreviewContainer.classList.add('hidden');
        adminPreviewContainer.innerHTML = '';
        adminDropZoneContent.classList.remove('hidden');
        checkAdminFormValidity();
    };

    // Submit Sync
    adminUploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!adminFile || !adminTokenInput.value.trim()) return;

        adminSubmitBtn.disabled = true;
        adminTokenInput.disabled = true;
        document.getElementById('remove-admin-file-btn').disabled = true;
        
        syncMonitor.classList.remove('hidden');
        resetSteps();
        
        // Step 1: Uploading to GCS
        setStepState(stepUpload, 'active');
        
        const formData = new FormData();
        formData.append('file', adminFile);
        formData.append('token', adminTokenInput.value.trim());

        try {
            const response = await fetch('/api/admin/upload-handbook', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || '上傳與觸發同步失敗。');
            }

            // GCS Upload and Sync Trigger is done together in backend API
            setStepState(stepUpload, 'success');
            setStepState(stepTrigger, 'success');
            
            // Step 3: Polling RAG LRO Operation
            setStepState(stepSync, 'active');
            const opName = data.operation_name;
            pollingInfo.textContent = `Operation: ${opName.split('/').pop()}`;
            
            // Start polling status
            startOperationPolling(opName, adminTokenInput.value.trim());

        } catch (error) {
            if (stepUpload.className.includes('active')) {
                setStepState(stepUpload, 'failed');
            } else if (stepTrigger.className.includes('active')) {
                setStepState(stepTrigger, 'failed');
            } else {
                setStepState(stepUpload, 'failed');
            }
            alert(`管理操作失敗：${error.message}`);
            
            adminSubmitBtn.disabled = false;
            adminTokenInput.disabled = false;
            document.getElementById('remove-admin-file-btn').disabled = false;
        }
    });

    const startOperationPolling = (operationName, token) => {
        if (pollingIntervalId) clearInterval(pollingIntervalId);
        
        pollingIntervalId = setInterval(async () => {
            try {
                const response = await fetch(`/api/admin/operation-status?operation_name=${encodeURIComponent(operationName)}&token=${encodeURIComponent(token)}`);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || '查詢進度失敗。');
                }

                if (data.success && data.done) {
                    clearInterval(pollingIntervalId);
                    pollingIntervalId = null;
                    
                    if (data.error) {
                        setStepState(stepSync, 'failed');
                        alert(`知識庫同步失敗：${data.error}`);
                    } else {
                        setStepState(stepSync, 'success');
                        alert('知識庫手冊已成功同步並解析，AI 將即刻使用新資料！');
                    }
                    
                    // Restore inputs
                    adminSubmitBtn.disabled = false;
                    adminTokenInput.disabled = false;
                    if (document.getElementById('remove-admin-file-btn')) {
                        document.getElementById('remove-admin-file-btn').disabled = false;
                    }
                }
            } catch (err) {
                console.error("Polling error: ", err.message);
            }
        }, 10000); // Poll every 10 seconds
    };
    }

    // --- Security Modal Logic ---
    const securityEntranceBtn = document.getElementById('security-entrance-btn');
    const securityModal = document.getElementById('security-modal');
    const closeSecurityBtn = document.getElementById('close-security-btn');

    if (securityModal && closeSecurityBtn) {
        const openSecurityModal = () => {
            securityModal.classList.remove('hidden');
        };

        const closeSecurityModal = () => {
            securityModal.classList.add('hidden');
        };

        if (securityEntranceBtn) {
            securityEntranceBtn.addEventListener('click', openSecurityModal);
        }

        closeSecurityBtn.addEventListener('click', closeSecurityModal);
        securityModal.addEventListener('click', (e) => {
            if (e.target === securityModal) {
                closeSecurityModal();
            }
        });
    }
});
