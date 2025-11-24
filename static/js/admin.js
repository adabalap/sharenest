document.addEventListener('DOMContentLoaded', () => {
    console.log('admin.js: DOMContentLoaded event fired.');
    try {
        // DOM Elements
        const loadingIndicator = document.getElementById('loadingIndicator');
        const fileListContainer = document.getElementById('file-list-container');
        const selectAllCheckbox = document.getElementById('selectAllCheckbox');
        const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
        const searchInput = document.getElementById('searchInput');

        // Modals (Bootstrap 5 instances)
        // Ensure Bootstrap is loaded before attempting to instantiate Modals
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            console.error('admin.js: Bootstrap is not loaded or bootstrap.Modal is not defined.');
            // Potentially disable functionality or show a warning to the user
            showStatus('Required JavaScript libraries (Bootstrap) not loaded. Functionality may be limited.', true);
            return; 
        }
        const deleteConfirmationModal = new bootstrap.Modal(document.getElementById('deleteConfirmationModal'));
        const resultsModal = new bootstrap.Modal(document.getElementById('resultsModal'));
        
        // Modal inner elements
        const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
        const deleteCount = document.getElementById('deleteCount');
        const resultsContent = document.getElementById('resultsContent');
        const statusMessage = document.getElementById('statusMessage');

        let lastCheckedCheckbox = null;
        let allFiles = []; // Cache all files for searching

        // --- Core Functions ---

        async function loadFiles() {
            console.log('admin.js: loadFiles called.');
            showLoading(true);
            try {
                const response = await fetch('/admin/files');
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Server responded with status: ${response.status} - ${errorText}`);
                }
                allFiles = await response.json();
                console.log('admin.js: Files loaded successfully.', allFiles);
                renderFiles(allFiles);
            } catch (error) {
                console.error('admin.js: Error loading files:', error);
                showStatus('Failed to load files. Please try again later.', true);
            } finally {
                showLoading(false);
            }
        }

        function renderFiles(files) {
            console.log('admin.js: renderFiles called with', files.length, 'files.');
            fileListContainer.innerHTML = '';
            if (!files || files.length === 0) {
                showStatus('No files found.');
                return;
            }
            hideStatus();

            files.forEach(file => {
                const checkboxIdentifier = file.status === 'orphaned'
                    ? `data-object-name="${escapeHTML(file.object_name)}"`
                    : `data-file-id="${file.id}"`;

                const fileCard = document.createElement('div');
                fileCard.className = `file-card card mb-2 status-${file.status} is-collapsed`; // Add is-collapsed class by default
                fileCard.innerHTML = `
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <div class="form-check d-flex align-items-center">
                            <input type="checkbox" class="file-checkbox form-check-input me-2" ${checkboxIdentifier}>
                            <label class="form-check-label" title="${escapeHTML(file.original_filename)}">
                                ${escapeHTML(file.original_filename)}
                            </label>
                        </div>
                        <div class="d-flex align-items-center">
                            <span class="badge bg-${getStatusClass(file.status)} me-2">${file.status}</span>
                            <i class="bi bi-chevron-down expand-toggle-icon"></i>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="file-details-list mb-3">
                            <div><strong>Filename:</strong> ${escapeHTML(file.original_filename)}</div>
                            <div><strong>Object Name:</strong> ${escapeHTML(file.object_name)}</div>
                            <div><strong>File ID:</strong> ${file.id ?? 'N/A'}</div>
                            <div><strong>Size:</strong> ${file.size_bytes ? formatBytes(file.size_bytes) : 'N/A'}</div>
                            <div><strong>Created:</strong> ${file.created_at ? new Date(file.created_at).toLocaleString() : 'N/A'}</div>
                            <div><strong>Expires:</strong> ${file.expiry_date ? getExpiryRelative(file.expiry_date) : 'N/A'}</div>
                            <div><strong>Downloads:</strong> ${file.download_count ?? 'N/A'} / ${file.max_downloads ?? 'N/A'}</div>
                            <div><strong>Status:</strong> <span class="badge bg-${getStatusClass(file.status)}">${file.status}</span></div>
                        </div>
                        <div class="text-end">
                            <button class="btn btn-danger btn-sm btn-delete-single" ${checkboxIdentifier}>Delete</button>
                        </div>
                    </div>
                `;
                fileListContainer.appendChild(fileCard);

                const cardHeader = fileCard.querySelector('.card-header');
                cardHeader.addEventListener('click', (e) => {
                    console.log('admin.js: cardHeader clicked. Target:', e.target);
                    // Only toggle if not clicking directly on checkbox or delete button
                    if (!e.target.classList.contains('form-check-input') && !e.target.classList.contains('btn-delete-single')) {
                        if (window.innerWidth < 768) { // Only for small screens
                            fileCard.classList.toggle('is-expanded');
                            fileCard.classList.toggle('is-collapsed');
                            const icon = fileCard.querySelector('.expand-toggle-icon');
                            if (icon) {
                                icon.classList.toggle('bi-chevron-down');
                                icon.classList.toggle('bi-chevron-up');
                            }
                            console.log('admin.js: fileCard toggled expanded/collapsed state.');
                        }
                    }
                });
            });

            updateUI();
        }

        async function performDeletion(selection) {
            console.log('admin.js: performDeletion called with selection:', selection);
            deleteConfirmationModal.hide();
            showLoading(true, 'Deleting selected files...');

            try {
                const response = await fetch('/admin/cleanup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(selection),
                });
                const results = await response.json();
                if (!response.ok) {
                    throw new Error(results.error || `Deletion request failed with status: ${response.status}`);
                }
                console.log('admin.js: Deletion results:', results);
                displayResults(results);
            } catch (error) {
                console.error('admin.js: Error during deletion:', error);
                showStatus('An unexpected error occurred during deletion.', true);
            } finally {
                showLoading(false);
                loadFiles(); // Refresh the file list
            }
        }

        // --- UI Update and State Management ---

        function updateUI() {
            console.log('admin.js: updateUI called.');
            const selectedCount = fileListContainer.querySelectorAll('.file-checkbox:checked').length;
            const totalCount = fileListContainer.querySelectorAll('.file-checkbox').length;
            deleteSelectedBtn.disabled = selectedCount === 0;
            selectAllCheckbox.checked = totalCount > 0 && selectedCount === totalCount;
            selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < totalCount;
            console.log(`admin.js: Selected count: ${selectedCount}, Total count: ${totalCount}`);
        }

        function getSelection() {
            console.log('admin.js: getSelection called.');
            const selection = { file_ids: [], object_names: [] };
            fileListContainer.querySelectorAll('.file-checkbox:checked').forEach(cb => {
                if (cb.dataset.fileId) {
                    selection.file_ids.push(parseInt(cb.dataset.fileId, 10));
                } else if (cb.dataset.objectName) {
                    selection.object_names.push(cb.dataset.objectName);
                }
            });
            console.log('admin.js: Current selection:', selection);
            return selection;
        }

        function displayResults(results) {
            console.log('admin.js: displayResults called with:', results);
            let content = '';
            if (results.success?.length > 0) {
                content += `<div class="alert alert-success"><h6>Successfully Deleted (${results.success.length})</h6><ul>`;
                results.success.forEach(f => content += `<li>${f.id ? `ID ${f.id}: ` : ''}${escapeHTML(f.object_name)}</li>`);
                content += '</ul></div>';
            }

            const allFailures = [...(results.failed_db || []), ...(results.failed_oci || []), ...(results.failed_both || [])];
            if (allFailures.length > 0) {
                content += `<div class="alert alert-danger"><h6>Failed to Delete (${allFailures.length})</h6><ul>`;
                const renderFailure = (f, reason) => `<li>${f.id ? `ID ${f.id}: ` : ''}${escapeHTML(f.object_name)} - ${reason}</li>`;
                (results.failed_db || []).forEach(f => content += renderFailure(f, 'DB error'));
                (results.failed_oci || []).forEach(f => content += renderFailure(f, 'Storage error'));
                (results.failed_both || []).forEach(f => content += renderFailure(f, 'All ops failed'));
                content += '</ul></div>';
            }
            resultsContent.innerHTML = content || '<p>No changes were made.</p>';
            resultsModal.show();
        }
        
        function filterFiles() {
            console.log('admin.js: filterFiles called.');
            const query = searchInput.value.toLowerCase();
            const filteredFiles = allFiles.filter(file => 
                file.original_filename.toLowerCase().includes(query) ||
                (file.id && file.id.toString().includes(query))
            );
            renderFiles(filteredFiles);
        }

        // --- Event Listeners ---

        fileListContainer.addEventListener('click', (e) => {
            console.log('admin.js: fileListContainer click event. Target:', e.target);
            if (e.target.classList.contains('file-checkbox')) {
                const checkbox = e.target;
                if (e.shiftKey && lastCheckedCheckbox && lastCheckedCheckbox !== checkbox) {
                    const checkboxes = Array.from(fileListContainer.querySelectorAll('.file-checkbox'));
                    const start = checkboxes.indexOf(lastCheckedCheckbox);
                    const end = checkboxes.indexOf(checkbox);
                    if (start !== -1 && end !== -1) {
                        checkboxes.slice(Math.min(start, end), Math.max(start, end) + 1).forEach(cb => cb.checked = lastCheckedCheckbox.checked);
                    }
                }
                lastCheckedCheckbox = checkbox;
                updateUI();
            } else if (e.target.classList.contains('btn-delete-single')) {
                console.log('admin.js: Single delete button clicked.');
                const button = e.target;
                const fileId = button.dataset.fileId;
                const objectName = button.dataset.objectName;
                const selection = {
                    file_ids: fileId ? [parseInt(fileId, 10)] : [], // Ensure fileId is integer
                    object_names: objectName ? [objectName] : [],
                };
                deleteCount.textContent = '1';
                confirmDeleteBtn.onclick = () => performDeletion(selection);
                deleteConfirmationModal.show();
            }
        });

        selectAllCheckbox.addEventListener('change', (e) => {
            console.log('admin.js: selectAllCheckbox change event. Checked:', e.target.checked);
            fileListContainer.querySelectorAll('.file-checkbox').forEach(cb => cb.checked = e.target.checked);
            updateUI();
        });

        deleteSelectedBtn.addEventListener('click', () => {
            console.log('admin.js: deleteSelectedBtn clicked.');
            const selection = getSelection();
            const count = selection.file_ids.length + selection.object_names.length;
            if (count > 0) {
                deleteCount.textContent = count;
                confirmDeleteBtn.onclick = () => performDeletion(selection);
                deleteConfirmationModal.show();
            } else {
                console.warn('admin.js: No files selected for deletion.');
            }
        });

        searchInput.addEventListener('input', filterFiles);
        console.log('admin.js: Search input event listener attached.');

        // --- Utility Functions ---

        function showLoading(show, message = 'Loading files...') {
            if (show) {
                loadingIndicator.querySelector('p').textContent = message;
                loadingIndicator.classList.remove('d-none');
            } else {
                loadingIndicator.classList.add('d-none');
            }
            console.log('admin.js: showLoading set to', show, 'with message:', message);
        }

        function showStatus(message, isError = false) {
            statusMessage.textContent = message;
            statusMessage.className = `status-message alert ${isError ? 'alert-danger' : 'alert-info'}`;
            statusMessage.classList.remove('d-none');
            console.log(`admin.js: showStatus: ${message} (Error: ${isError})`);
        }
        
        function hideStatus() {
            statusMessage.classList.add('d-none');
            console.log('admin.js: hideStatus called.');
        }
        
        function getStatusClass(status) {
            // console.log('admin.js: getStatusClass called for status:', status); // Too noisy
            switch (status) {
                case 'synced': return 'success';
                case 'orphaned': return 'warning';
                case 'missing': return 'danger';
                default: return 'secondary';
            }
        }

        function formatBytes(bytes, decimals = 2) {
            // console.log('admin.js: formatBytes called for bytes:', bytes); // Too noisy
            if (!+bytes) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
        }

        function getExpiryRelative(isoDate) {
            // console.log('admin.js: getExpiryRelative called for date:', isoDate); // Too noisy
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
            return str.toString().replace(/[&<>"']/g, match => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[match]));
        }

        // --- Initial Load ---
        loadFiles();
        console.log('admin.js: Initial file load initiated.');

    } catch (e) {
        console.error('admin.js: Uncaught error in DOMContentLoaded handler:', e);
        // Display a user-friendly error message if critical JS fails
        const appContainer = document.querySelector('.admin-container');
        if (appContainer) {
            appContainer.innerHTML = '<div class="alert alert-danger" role="alert">An error occurred loading the admin panel. Please refresh the page. Details logged to console.</div>';
        }
    }
});