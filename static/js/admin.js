document.addEventListener('DOMContentLoaded', () => {
    const loadingIndicator = document.getElementById('loadingIndicator');
    const filesTable = document.getElementById('filesTable');
    const filesTableBody = document.getElementById('filesTableBody');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
    const deleteConfirmationModal = document.getElementById('deleteConfirmationModal');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    const deleteCount = document.getElementById('deleteCount');
    const resultsModal = document.getElementById('resultsModal');
    const resultsContent = document.getElementById('resultsContent');
    const closeResultsBtn = document.getElementById('closeResultsBtn');
    const statusMessage = document.getElementById('statusMessage');

    let files = [];
    let lastCheckedCheckbox = null;

    async function loadFiles() {
        showLoading('Loading files...');
        filesTable.classList.add('hidden');
        try {
            const response = await fetch('/admin/files');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            files = await response.json();
            renderTable(files);
            filesTable.classList.remove('hidden');
        } catch (error) {
            console.error('Error loading files:', error);
            showStatus('Failed to load files. Please try again later.', true);
        } finally {
            hideLoading();
        }
    }

    function renderTable(filesToRender) {
        filesTableBody.innerHTML = '';
        if (filesToRender.length === 0) {
            showStatus('No files found.');
            filesTable.classList.add('hidden');
            return;
        }
        
        filesToRender.forEach(file => {
            const row = document.createElement('tr');
            if (file.status) {
                row.classList.add(`status-${file.status}`);
            }
            row.dataset.objectName = file.object_name;

            const checkboxDataAttr = file.status === 'orphaned' 
                ? `data-object-name="${escapeHTML(file.object_name)}"`
                : `data-file-id="${file.id}"`;

            row.innerHTML = `
                <td><input type="checkbox" class="file-checkbox" ${checkboxDataAttr}></td>
                <td>${file.id || 'N/A'}</td>
                <td class="filename" title="${escapeHTML(file.original_filename)}">${escapeHTML(file.original_filename)}</td>
                <td>${file.size_bytes ? formatBytes(file.size_bytes) : 'N/A'}</td>
                <td>${file.created_at ? new Date(file.created_at).toLocaleString() : 'N/A'}</td>
                <td>${file.expiry_date ? getExpiryRelative(file.expiry_date) : 'N/A'}</td>
                <td>${file.download_count ?? 'N/A'} / ${file.max_downloads ?? 'N/A'}</td>
                <td><span class="status-label status-${file.status}">${file.status}</span></td>
            `;
            filesTableBody.appendChild(row);
        });
    }

    function updateSelectionState() {
        const selectedCheckboxes = filesTableBody.querySelectorAll('.file-checkbox:checked');
        const allCheckboxes = filesTableBody.querySelectorAll('.file-checkbox');
        deleteSelectedBtn.disabled = selectedCheckboxes.length === 0;
        selectAllCheckbox.checked = allCheckboxes.length > 0 && selectedCheckboxes.length === allCheckboxes.length;
    }

    function handleRowCheckboxClick(e) {
        const checkbox = e.target;
        if (e.shiftKey && lastCheckedCheckbox && lastCheckedCheckbox !== checkbox) {
            const checkboxes = Array.from(filesTableBody.querySelectorAll('.file-checkbox'));
            const start = checkboxes.indexOf(lastCheckedCheckbox);
            const end = checkboxes.indexOf(checkbox);
            const shouldBeChecked = lastCheckedCheckbox.checked;
            
            if (start !== -1 && end !== -1) {
                const range = checkboxes.slice(Math.min(start, end), Math.max(start, end) + 1);
                range.forEach(cb => cb.checked = shouldBeChecked);
            }
        }
        lastCheckedCheckbox = checkbox;
        updateSelectionState();
    }

    function getSelection() {
        const selection = {
            file_ids: [],
            object_names: [],
        };
        filesTableBody.querySelectorAll('.file-checkbox:checked').forEach(cb => {
            if (cb.dataset.fileId) {
                selection.file_ids.push(parseInt(cb.dataset.fileId, 10));
            } else if (cb.dataset.objectName) {
                selection.object_names.push(cb.dataset.objectName);
            }
        });
        return selection;
    }

    async function performDeletion() {
        const selection = getSelection();
        if (selection.file_ids.length === 0 && selection.object_names.length === 0) return;

        hideModal(deleteConfirmationModal);
        showLoading('Deleting files...');

        try {
            const response = await fetch('/admin/cleanup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(selection),
            });

            if (!response.ok) {
                throw new Error(`Deletion request failed with status: ${response.status}`);
            }

            const results = await response.json();
            displayResults(results);
            await loadFiles(); // Reload the file list
            updateSelectionState();

        } catch (error) {
            console.error('Error during deletion:', error);
            showStatus('An unexpected error occurred during deletion.', true);
        } finally {
            hideLoading();
        }
    }

    function displayResults(results) {
        let content = '<div class="results-summary">';
        
        if (results.success && results.success.length > 0) {
            content += `<div class="success"><h4>Successfully Deleted (${results.success.length})</h4><ul>`;
            results.success.forEach(f => content += `<li>${f.id ? `ID ${f.id}: ` : ''}${escapeHTML(f.object_name)}</li>`);
            content += '</ul></div>';
        }

        const allFailures = [
            ...(results.failed_db || []), 
            ...(results.failed_oci || []), 
            ...(results.failed_both || [])
        ];

        if (allFailures.length > 0) {
            content += `<div class="failed"><h4>Failed to Delete (${allFailures.length})</h4><ul>`;
            const renderFailure = (f, reason) => `<li>${f.id ? `ID ${f.id}: ` : ''}${escapeHTML(f.object_name)} - ${reason}</li>`;

            (results.failed_db || []).forEach(f => content += renderFailure(f, 'DB delete failed'));
            (results.failed_oci || []).forEach(f => content += renderFailure(f, 'Storage delete failed'));
            (results.failed_both || []).forEach(f => content += renderFailure(f, 'All operations failed'));
            
            content += '</ul></div>';
        }

        content += '</div>';
        resultsContent.innerHTML = content;
        showModal(resultsModal);
    }
    
    // Event Listeners
    selectAllCheckbox.addEventListener('change', (e) => {
        filesTableBody.querySelectorAll('.file-checkbox').forEach(cb => cb.checked = e.target.checked);
        updateSelectionState();
    });

    filesTableBody.addEventListener('click', e => {
        if (e.target.matches('.file-checkbox')) {
            handleRowCheckboxClick(e);
        }
    });

    deleteSelectedBtn.addEventListener('click', () => {
        const selection = getSelection();
        const count = selection.file_ids.length + selection.object_names.length;
        if (count > 0) {
            deleteCount.textContent = count;
            showModal(deleteConfirmationModal);
        }
    });

    confirmDeleteBtn.addEventListener('click', performDeletion);
    cancelDeleteBtn.addEventListener('click', () => hideModal(deleteConfirmationModal));
    closeResultsBtn.addEventListener('click', () => hideModal(resultsModal));

    // Utility functions
    function showLoading(message) {
        loadingIndicator.textContent = message;
        loadingIndicator.classList.remove('hidden');
        clearStatus();
    }
    function hideLoading() { loadingIndicator.classList.add('hidden'); }
    function showStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.className = `status-message ${isError ? 'error-message' : 'success-message'}`;
        statusMessage.classList.remove('hidden');
    }
    function clearStatus() { statusMessage.classList.add('hidden'); }
    function showModal(modal) { modal.classList.remove('hidden'); }
    function hideModal(modal) { modal.classList.add('hidden'); }
    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }
    function getExpiryRelative(isoDate) {
        const now = new Date();
        const expiry = new Date(isoDate);
        const delta = expiry - now;

        if (delta <= 0) return "Expired";
        
        const days = Math.floor(delta / (1000 * 60 * 60 * 24));
        const hours = Math.floor((delta / (1000 * 60 * 60)) % 24);
        const minutes = Math.floor((delta / 1000 / 60) % 60);

        if (days > 0) return `${days}d ${hours}h`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    }
    function escapeHTML(str) {
        return str.replace(/[&<>"']/g, match => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[match]));
    }

    // Initial Load
    loadFiles();
});
