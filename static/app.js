document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('preview-container');
    const dropZoneContent = document.querySelector('.drop-zone-content');
    const questionInput = document.getElementById('question-input');
    const submitBtn = document.getElementById('submit-btn');
    const analyzeForm = document.getElementById('analyze-form');
    
    const inviteInput = document.getElementById('invite-input');
    const quotaBadge = document.getElementById('quota-badge');
    
    // Result panels
    const statusBadge = document.getElementById('status-badge');
    const resultIdle = document.getElementById('result-idle');
    const resultLoading = document.getElementById('result-loading');
    const resultSuccess = document.getElementById('result-success');
    const reportBody = document.getElementById('report-body');
    const citationsArea = document.getElementById('citations-area');
    const citationsList = document.getElementById('citations-list');
    
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
            copyReportBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="currentColor"/>
                </svg>
                <span>已複製！</span>
            `;
            copyReportBtn.classList.add('copied');
            setTimeout(() => {
                copyReportBtn.innerHTML = originalText;
                copyReportBtn.classList.remove('copied');
            }, 1500);
        } catch (err) {
            alert('複製失敗，請手動選取複製。');
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
            alert('不支援的檔案格式！請上傳 PNG, JPG, JPEG 圖片或 PDF 檔案。');
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
        
        statusBadge.textContent = '分析中...';
        statusBadge.className = 'status-badge analyzing';
        
        resultIdle.classList.add('hidden');
        resultSuccess.classList.add('hidden');
        resultLoading.classList.remove('hidden');

        // Create FormData
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('question', questionInput.value.trim());
        formData.append('invite_code', inviteInput.value.trim());

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || '分析失敗，請檢查後端連線。');
            }

            // Success UI
            statusBadge.textContent = '分析完成';
            statusBadge.className = 'status-badge success';
            resultLoading.classList.add('hidden');
            resultSuccess.classList.remove('hidden');

            // Render Quota Badge
            if (data.remaining_quota !== undefined) {
                quotaBadge.textContent = `剩餘額度: ${data.remaining_quota} 次`;
                quotaBadge.style.display = 'inline-block';
            } else {
                quotaBadge.style.display = 'none';
            }

            // Save analysis text for copy function
            currentAnalysisText = data.analysis;

            // Render Markdown Cards
            const renderer = new marked.Renderer();
            renderer.link = (href, title, text) => {
                return `<a href="${href}" title="${title || ''}" target="_blank" rel="noopener noreferrer">${text}</a>`;
            };
            marked.setOptions({ renderer: renderer });
            
            reportBody.innerHTML = '';
            
            // Split markdown by H2 headers "## "
            const rawSections = data.analysis.split(/^(?=##\s+)/m);
            rawSections.forEach(section => {
                const trimmed = section.trim();
                if (!trimmed) return;
                
                const card = document.createElement('div');
                card.className = 'result-card';
                card.innerHTML = marked.parse(trimmed);
                reportBody.appendChild(card);
            });

            // Render Citations
            if (data.citations && data.citations.length > 0) {
                citationsArea.classList.remove('hidden');
                citationsList.innerHTML = '';
                data.citations.forEach(cit => {
                    const badge = document.createElement('a');
                    badge.className = 'citation-badge';
                    badge.href = cit.uri;
                    badge.target = '_blank';
                    badge.rel = 'noopener noreferrer';
                    badge.innerHTML = `
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 4px;">
                            <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2ZM18 20H6V4H13V9H18V20Z" fill="currentColor"/>
                        </svg>${cit.title}
                    `;
                    citationsList.appendChild(badge);
                });
            } else {
                citationsArea.classList.add('hidden');
            }

        } catch (error) {
            // Error UI
            statusBadge.textContent = '發生錯誤';
            statusBadge.className = 'status-badge idle';
            resultLoading.classList.add('hidden');
            resultIdle.classList.remove('hidden');
            quotaBadge.style.display = 'none';
            
            alert(`錯誤：${error.message}`);
        } finally {
            // Restore UI states
            submitBtn.disabled = false;
            questionInput.disabled = false;
            inviteInput.disabled = false;
            if (document.getElementById('remove-file-btn')) {
                document.getElementById('remove-file-btn').disabled = false;
            }
            checkFormValidity();
        }
    });

    // --- Admin Modal Logic ---
    const adminEntranceBtn = document.getElementById('admin-entrance-btn');
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

    // --- Security Modal Logic ---
    const securityEntranceBtn = document.getElementById('security-entrance-btn');
    const securityModal = document.getElementById('security-modal');
    const closeSecurityBtn = document.getElementById('close-security-btn');

    if (securityEntranceBtn && securityModal && closeSecurityBtn) {
        securityEntranceBtn.addEventListener('click', () => {
            securityModal.classList.remove('hidden');
        });

        const closeSecurityModal = () => {
            securityModal.classList.add('hidden');
        };

        closeSecurityBtn.addEventListener('click', closeSecurityModal);
        securityModal.addEventListener('click', (e) => {
            if (e.target === securityModal) {
                closeSecurityModal();
            }
        });
    }
});
