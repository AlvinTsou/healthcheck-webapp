document.addEventListener('DOMContentLoaded', () => {
    // --- Admin Dashboard Logic ---
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

    // Tabs Switch Logic
    if (tabKb && tabResearch) {
        tabKb.addEventListener('click', () => {
            tabKb.classList.add('active');
            tabKb.style.color = '#fff';
            tabKb.style.borderBottom = '2px solid #3b82f6';
            
            tabResearch.classList.remove('active');
            tabResearch.style.color = 'rgba(255, 255, 255, 0.6)';
            tabResearch.style.borderBottom = '2px solid transparent';
            
            tabContentKb.classList.remove('hidden');
            tabContentResearch.classList.add('hidden');
        });
        
        tabResearch.addEventListener('click', () => {
            tabResearch.classList.add('active');
            tabResearch.style.color = '#fff';
            tabResearch.style.borderBottom = '2px solid #3b82f6';
            
            tabKb.classList.remove('active');
            tabKb.style.color = 'rgba(255, 255, 255, 0.6)';
            tabKb.style.borderBottom = '2px solid transparent';
            
            tabContentResearch.classList.remove('hidden');
            tabContentKb.classList.add('hidden');
            
            // Auto load stats when switching tabs if token exists
            const token = adminTokenInput.value.trim();
            if (token) {
                loadResearchStats(token);
            } else {
                keywordListContainer.innerHTML = `
                    <div style="text-align: center; padding: 20px; color: rgba(255,255,255,0.4);">
                        請先在知識庫管理頁籤中輸入管理憑證 Token 以獲取研究數據。
                    </div>
                `;
            }
        });
    }

    // Load research stats and dynamic visual rendering
    const loadResearchStats = async (token) => {
        try {
            keywordListContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: rgba(255,255,255,0.6);">數據載入中...</div>';
            
            const response = await fetch(`/api/admin/research-stats?token=${encodeURIComponent(token)}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || '讀取數據失敗。');
            }
            
            if (!data.success) {
                throw new Error(data.error || '獲取研究統計資料異常。');
            }
            
            // 1. Render accuracy score
            const score = data.average_accuracy !== undefined ? data.average_accuracy : 100.0;
            accuracyPercentage.textContent = `${score}%`;
            accuracyBar.style.width = `${score}%`;
            
            // Adjust bar colors dynamically using HSL
            const hue = (score / 100) * 120; // 0 is red, 60 is orange/yellow, 120 is green
            accuracyBar.style.background = `hsl(${hue}, 80%, 45%)`;
            
            // 2. Render keyword list with progress bars
            keywordListContainer.innerHTML = '';
            const kwStats = data.keyword_stats || [];
            
            if (kwStats.length === 0) {
                keywordListContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: rgba(255,255,255,0.4);">尚無關鍵字統計數據。</div>';
                return;
            }
            
            const maxMentions = kwStats[0].count || 1; // Used to calculate relative width percentages
            
            kwStats.forEach((stat, index) => {
                const percentage = Math.round((stat.count / maxMentions) * 100);
                const itemDiv = document.createElement('div');
                itemDiv.className = 'keyword-stat-item';
                itemDiv.style.cssText = `
                    background: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(255, 255, 255, 0.04);
                    border-radius: 8px;
                    padding: 10px 14px;
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                `;
                
                // Calculate dynamic color for ranks using HSL
                const rankColor = index === 0 ? 'hsl(45, 100%, 50%)' : // Gold
                                  index === 1 ? 'hsl(0, 0%, 80%)' :    // Silver
                                  index === 2 ? 'hsl(30, 60%, 50%)' :   // Bronze
                                  'rgba(255, 255, 255, 0.4)';
                
                itemDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 500;">
                            <span style="color: ${rankColor}; font-weight: bold; margin-right: 6px;">#${index + 1}</span>
                            ${stat.keyword}
                        </span>
                        <span style="font-weight: bold; font-family: monospace; color: #60a5fa;">
                            ${stat.count} 次 <span style="font-size: 0.75rem; font-weight: normal; color: rgba(255,255,255,0.3);">(提問 ${stat.question_count} / 報告 ${stat.report_count})</span>
                        </span>
                    </div>
                    <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${percentage}%; height: 100%; background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%); border-radius: 3px;"></div>
                    </div>
                `;
                keywordListContainer.appendChild(itemDiv);
            });
            
        } catch (error) {
            keywordListContainer.innerHTML = `
                <div style="text-align: center; padding: 20px; color: #ef4444;">
                    讀取數據失敗：${error.message}
                </div>
            `;
            alert(`讀取研究統計失敗：${error.message}`);
        }
    };

    // Helper functions for admin upload monitoring
    const setStepState = (element, state) => {
        if (!element) return;
        const icon = element.querySelector('.step-status-icon');
        element.className = `step-item ${state}`;
        if (state === 'active') {
            icon.textContent = '⚡';
            icon.style.animation = 'pulse 1s infinite';
        } else if (state === 'success') {
            icon.textContent = '✅';
            icon.style.animation = 'none';
        } else if (state === 'failed') {
            icon.textContent = '❌';
            icon.style.animation = 'none';
        } else {
            icon.textContent = '⏳';
            icon.style.animation = 'none';
        }
    };

    const resetSteps = () => {
        setStepState(stepUpload, 'pending');
        setStepState(stepTrigger, 'pending');
        setStepState(stepSync, 'pending');
        pollingInfo.textContent = 'Operation: --';
    };

    // Admin drop zone and file select
    if (adminDropZone && adminFileInput) {
        // Drag over
        adminDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            adminDropZone.classList.add('dragover');
        });

        // Drag leave
        adminDropZone.addEventListener('dragleave', () => {
            adminDropZone.classList.remove('dragover');
        });

        // Drop
        adminDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            adminDropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleAdminFileSelect(files[0]);
            }
        });

        // Click zone to browse
        adminDropZone.addEventListener('click', () => {
            adminFileInput.click();
        });

        // File change
        adminFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleAdminFileSelect(e.target.files[0]);
            }
        });
    }

    const handleAdminFileSelect = (file) => {
        if (!file.name.endsWith('.pdf')) {
            alert('系統目前僅支援上傳 PDF 格式的健檢對照手冊！');
            return;
        }
        
        adminFile = file;
        adminDropZoneContent.classList.add('hidden');
        adminPreviewContainer.classList.remove('hidden');
        
        // Show PDF file info
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        adminPreviewContainer.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 8px; border: 1px dashed rgba(255,255,255,0.1);">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.5rem;">📄</span>
                    <div style="text-align: left;">
                        <p style="font-weight: 500; font-size: 0.9rem; color: #fff; margin: 0; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</p>
                        <p style="font-size: 0.75rem; color: rgba(255,255,255,0.4); margin: 0;">${sizeMb} MB</p>
                    </div>
                </div>
                <button type="button" id="remove-admin-file-btn" style="background: none; border: none; color: #ef4444; font-size: 1.2rem; cursor: pointer; padding: 4px;">&times;</button>
            </div>
        `;
        
        adminSubmitBtn.disabled = false;
        
        // Bind remove button
        document.getElementById('remove-admin-file-btn').addEventListener('click', (e) => {
            e.stopPropagation(); // Avoid triggering dropzone click
            removeAdminFile();
        });
    };

    const removeAdminFile = () => {
        adminFile = null;
        adminFileInput.value = '';
        adminPreviewContainer.classList.add('hidden');
        adminPreviewContainer.innerHTML = '';
        adminDropZoneContent.classList.remove('hidden');
        adminSubmitBtn.disabled = true;
        syncMonitor.classList.add('hidden');
        resetSteps();
    };

    // Handbook Upload and Sync Form Submission
    if (adminUploadForm) {
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
    }

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
});
