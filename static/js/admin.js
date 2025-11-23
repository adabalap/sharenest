document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const loadingIndicator = document.getElementById('loadingIndicator');
    const filesTable = document.getElementById('filesTable');
    const filesTableBody = document.getElementById('filesTableBody');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
    
    // Modals
    const deleteConfirmationModal = document.getElementById('deleteConfirmationModal');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    const deleteCount = document.getElementById('deleteCount');
    
    const resultsModal = document.getElementById('resultsModal');
    const resultsContent = document.getElementById('resultsContent');
    const closeResultsBtn = document.getElementById('closeResultsBtn');
    
    const statusMessage = document.getElementById('statusMessage');

    let lastCheckedCheckbox = null;

    // --- Core Functions ---

    /**
     * Fetches file data from the server and renders the table.
     */
    async function loadFiles() {
        showLoading('Loading files...');
        filesTable.classList.add('hidden');

        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            controller.abort();
            console.warn('File loading request timed out after 30 seconds.');
        }, 30000); // 30 seconds timeout

        try {
            const response = await fetch('/admin/files', { signal: controller.signal });
            clearTimeout(timeoutId); // Clear the timeout if the request completes in time

            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }
            const files = await response.json();
            try {
                renderTable(files);
            } catch (e) {
                console.error('Error rendering table:', e);
                showStatus('Failed to display files due to a rendering error.', true);
            }
        } catch (error) {
            clearTimeout(timeoutId); // Ensure timeout is cleared even on other errors
            if (error.name === 'AbortError') {
                console.error('File loading request was aborted (timeout):', error);
                showStatus('Loading files is taking a long time. The server may be busy or there may be a large number of files. Please try refreshing or check your OCI configuration.', true);
            } else {
                console.error('Error loading files:', error);
                showStatus('Failed to load files. Please try again later. Check browser console for details.', true);
            }
        } finally {
            hideLoading();
        }
    }

    /**
     * Renders the file data into the HTML table.
     * @param {Array} files - The array of file objects from the server.
     */
    function renderTable(files) {
        filesTableBody.innerHTML = ''; // Clear existing rows

        if (!files || files.length === 0) {
            showStatus('No files found.');
            filesTable.classList.add('hidden');
            return;
        }

        filesTable.classList.remove('hidden');
        statusMessage.classList.add('hidden');

        files.forEach(file => {
            const row = document.createElement('tr');
            row.className = `status-${file.status}`;

            // Determine the unique identifier for the checkbox
            const checkboxIdentifier = file.status === 'orphaned' 
                ? `data-object-name="${escapeHTML(file.object_name)}"`
                : `data-file-id="${file.id}"`;

            row.innerHTML = `
                <td><input type="checkbox" class="file-checkbox" ${checkboxIdentifier}></td>
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

        updateUI();
    }

    /**
     * Performs the deletion of selected files.
     */
    async function performDeletion() {
        hideModal(deleteConfirmationModal);
        showLoading('Deleting selected files...');

        const selection = getSelection();
        if (selection.file_ids.length === 0 && selection.object_names.length === 0) {
            hideLoading();
            return;
        }

        try {
            const response = await fetch('/admin/cleanup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(selection),
            });

            const results = await response.json();
            if (!response.ok) {
                throw new Error(results.error || 'Deletion request failed');
            }
            
            displayResults(results);

        } catch (error) {
            console.error('Error during deletion:', error);
            showStatus('An unexpected error occurred during deletion.', true);
        } finally {
            hideLoading();
            loadFiles(); // Refresh the file list
        }
    }


    // --- UI Update and State Management ---

    /**
     * Updates the state of UI elements like buttons based on selection.
     */
    function updateUI() {
        const selectedCount = filesTableBody.querySelectorAll('.file-checkbox:checked').length;
        const totalCount = filesTableBody.querySelectorAll('.file-checkbox').length;

        deleteSelectedBtn.disabled = selectedCount === 0;
        selectAllCheckbox.checked = totalCount > 0 && selectedCount === totalCount;
        selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < totalCount;
    }

    /**
     * Gathers the selected file IDs and object names.
     * @returns {{file_ids: Number[], object_names: String[]}}
     */
    function getSelection() {
        const selection = { file_ids: [], object_names: [] };
        filesTableBody.querySelectorAll('.file-checkbox:checked').forEach(cb => {
            if (cb.dataset.fileId) {
                selection.file_ids.push(parseInt(cb.dataset.fileId, 10));
            } else if (cb.dataset.objectName) {
                selection.object_names.push(cb.dataset.objectName);
            }
        });
        return selection;
    }

    /**
     * Displays the results of the deletion operation in a modal.
     * @param {Object} results - The results object from the server.
     */
    function displayResults(results) {
        if (!results) {
            resultsContent.innerHTML = '<div class="failed"><h4>An unknown error occurred.</h4></div>';
            showModal(resultsModal);
            return;
        }
        
        let content = '<div class="results-summary">';
        
        if (results.success?.length > 0) {
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

    // --- Event Listeners ---

    // Handle clicks on checkboxes
    filesTableBody.addEventListener('click', (e) => {
        if (e.target.classList.contains('file-checkbox')) {
            const checkbox = e.target;
            if (e.shiftKey && lastCheckedCheckbox && lastCheckedCheckbox !== checkbox) {
                const checkboxes = Array.from(filesTableBody.querySelectorAll('.file-checkbox'));
                const start = checkboxes.indexOf(lastCheckedCheckbox);
                const end = checkboxes.indexOf(checkbox);
                
                if (start !== -1 && end !== -1) {
                    // Check or uncheck all checkboxes in the range
                    const range = checkboxes.slice(Math.min(start, end), Math.max(start, end) + 1);
                    range.forEach(cb => cb.checked = lastCheckedCheckbox.checked);
                }
            }
            lastCheckedCheckbox = checkbox;
            updateUI();
        }
    });

    // Handle "Select All" checkbox
    selectAllCheckbox.addEventListener('change', (e) => {
        filesTableBody.querySelectorAll('.file-checkbox').forEach(cb => {
            cb.checked = e.target.checked;
        });
        updateUI();
    });

    // Handle "Delete Selected" button
    deleteSelectedBtn.addEventListener('click', () => {
        const selection = getSelection();
        const count = selection.file_ids.length + selection.object_names.length;
        if (count > 0) {
            deleteCount.textContent = count;
            showModal(deleteConfirmationModal);
        }
    });

    // Handle modal confirmation/cancellation
    confirmDeleteBtn.addEventListener('click', performDeletion);
    cancelDeleteBtn.addEventListener('click', () => hideModal(deleteConfirmationModal));
    closeResultsBtn.addEventListener('click', () => hideModal(resultsModal));


    // --- Utility Functions ---

    function showLoading(message) {
        loadingIndicator.textContent = message;
        loadingIndicator.classList.remove('hidden');
    }

    function hideLoading() {
        loadingIndicator.classList.add('hidden');
    }

    function showStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.className = `status-message ${isError ? 'error-message' : 'success-message'}`;
        statusMessage.classList.remove('hidden');
    }

    function showModal(modal) {
        if (modal) modal.classList.remove('hidden');
    }

    function hideModal(modal) {
        if (modal) modal.classList.add('hidden');
    }

    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    function getExpiryRelative(isoDate) {
        if (!isoDate) return 'N/A';
        const delta = new Date(isoDate) - new Date();
        if (delta <= 0) return "Expired";
        
        const days = Math.floor(delta / (1000 * 60 * 60 * 24));
        const hours = Math.floor((delta / (1000 * 60 * 60)) % 24);
        const minutes = Math.floor((delta / 1000 / 60) % 60);

        if (days > 0) return `${days}d ${hours}h`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    }

    function escapeHTML(str) {
        if (str === null || str === undefined) return '';
        return str.toString().replace(/[&<>"']/g, match => ({ 
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' 
        }[match]));
    }

    // --- Initial Load ---
    
    // Hide modals by default as a safeguard
    hideModal(deleteConfirmationModal);
    hideModal(resultsModal);
    
    // Load the initial file list
    loadFiles();
});
