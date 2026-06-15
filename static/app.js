document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('preview-container');
    const dropZoneContent = document.querySelector('.drop-zone-content');
    const questionInput = document.getElementById('question-input');
    const submitBtn = document.getElementById('submit-btn');
    const analyzeForm = document.getElementById('analyze-form');
    
    // Result panels
    const statusBadge = document.getElementById('status-badge');
    const resultIdle = document.getElementById('result-idle');
    const resultLoading = document.getElementById('result-loading');
    const resultSuccess = document.getElementById('result-success');
    const reportBody = document.getElementById('report-body');
    const citationsArea = document.getElementById('citations-area');
    const citationsList = document.getElementById('citations-list');
    
    let selectedFile = null;

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
        submitBtn.disabled = !(hasFile && hasQuestion);
    }

    questionInput.addEventListener('input', checkFormValidity);

    // --- Submit Form ---
    analyzeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!selectedFile || !questionInput.value.trim()) return;

        // UI States
        submitBtn.disabled = true;
        questionInput.disabled = true;
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

            // Render Markdown
            // Config marked to open links in new tab
            const renderer = new marked.Renderer();
            renderer.link = (href, title, text) => {
                return `<a href="${href}" title="${title || ''}" target="_blank" rel="noopener noreferrer">${text}</a>`;
            };
            marked.setOptions({ renderer: renderer });
            reportBody.innerHTML = marked.parse(data.analysis);

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
            
            alert(`錯誤：${error.message}`);
        } finally {
            // Restore UI states
            submitBtn.disabled = false;
            questionInput.disabled = false;
            if (document.getElementById('remove-file-btn')) {
                document.getElementById('remove-file-btn').disabled = false;
            }
            checkFormValidity();
        }
    });
});
