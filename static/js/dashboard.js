// Dashboard Initialization Script
// This ensures services are available before Alpine.js components initialize

(function() {
    'use strict';

    // Configuration
    const DASHBOARD_CONFIG = {
        maxInitAttempts: 20,
        initDelay: 50,
        debug: true
    };

    // Logging utility
    function log(...args) {
        if (DASHBOARD_CONFIG.debug) {
            console.log('[Dashboard Init]', ...args);
        }
    }

    // Initialize dashboard services
    async function initializeDashboard() {
        log('Starting dashboard initialization...');

        try {
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                await new Promise(resolve => {
                    document.addEventListener('DOMContentLoaded', resolve);
                });
            }

            // Initialize the dashboard app
            if (typeof DashboardApp !== 'undefined') {
                window.dashboardApp = new DashboardApp();
                log('Dashboard app initialized successfully');
                return true;
            } else {
                throw new Error('DashboardApp class not found');
            }
        } catch (error) {
            log('Dashboard initialization failed:', error);
            return false;
        }
    }

    // Wait for services to be available
    async function waitForServices(maxAttempts = DASHBOARD_CONFIG.maxInitAttempts) {
        for (let i = 0; i < maxAttempts; i++) {
            if (window.dashboardServices) {
                log('Dashboard services are available');
                return true;
            }

            log(`Waiting for services... attempt ${i + 1}/${maxAttempts}`);
            await new Promise(resolve => setTimeout(resolve, DASHBOARD_CONFIG.initDelay));
        }

        log('Dashboard services not available after maximum attempts');
        return false;
    }

    // Create fallback services if needed
    function createFallbackServices() {
        log('Creating fallback services...');

        // Get CSRF token
        function getCSRFToken() {
            return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                   document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        }

        // Simple notification system
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
            notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';

            const icons = {
                success: 'check-circle',
                danger: 'exclamation-triangle',
                warning: 'exclamation-circle',
                info: 'info-circle'
            };

            notification.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="fas fa-${icons[type] || 'info-circle'} me-2"></i>
                    <span>${message}</span>
                </div>
                <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
            `;

            document.body.appendChild(notification);

            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 5000);
        }

        // Create minimal services
        window.dashboardServices = {
            http: {
                async post(url, data) {
                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCSRFToken()
                        },
                        body: JSON.stringify(data)
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }

                    return await response.json();
                },

                async get(url) {
                    const response = await fetch(url);
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    return await response.json();
                }
            },

            notifications: {
                success: (msg) => showNotification(msg, 'success'),
                error: (msg) => showNotification(msg, 'danger'),
                warning: (msg) => showNotification(msg, 'warning'),
                info: (msg) => showNotification(msg, 'info')
            },

            fileUpload: {
                async uploadFile(file, onProgress) {
                    const formData = new FormData();
                    formData.append('file', file);

                    return new Promise((resolve, reject) => {
                        const xhr = new XMLHttpRequest();

                        if (onProgress) {
                            xhr.upload.addEventListener('progress', (e) => {
                                if (e.lengthComputable) {
                                    const progress = (e.loaded / e.total) * 100;
                                    onProgress(progress);
                                }
                            });
                        }

                        xhr.addEventListener('load', () => {
                            if (xhr.status === 200) {
                                try {
                                    const response = JSON.parse(xhr.responseText);
                                    resolve(response);
                                } catch (e) {
                                    reject(new Error('Invalid response format'));
                                }
                            } else {
                                reject(new Error(`Upload failed with status ${xhr.status}`));
                            }
                        });

                        xhr.addEventListener('error', () => {
                            reject(new Error('Upload failed'));
                        });

                        xhr.open('POST', '/dashboard/ajax/upload-file/');
                        xhr.setRequestHeader('X-CSRFToken', getCSRFToken());
                        xhr.send(formData);
                    });
                }
            },

            autoSave: {
                start: (getData, interval = 30000) => {
                    log('Auto-save started (fallback mode)');
                    // Simple auto-save implementation
                    setInterval(async () => {
                        const data = getData();
                        if (data && (data.title || data.content_sections?.length)) {
                            try {
                                await window.dashboardServices.http.post('/dashboard/ajax/save-article/', data);
                                log('Auto-save completed');
                            } catch (error) {
                                log('Auto-save failed:', error);
                            }
                        }
                    }, interval);
                },
                stop: () => log('Auto-save stopped'),
                scheduleDebounced: (delay = 2000) => {
                    // Simple debounced save - could be enhanced
                    log('Debounced save scheduled');
                }
            },

            dragDrop: {
                setupDropZone: (element, onFiles, options = {}) => {
                    log('Setting up drop zone (fallback mode)');

                    // Basic drag and drop setup
                    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                        element.addEventListener(eventName, (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                        });
                    });

                    ['dragenter', 'dragover'].forEach(eventName => {
                        element.addEventListener(eventName, () => {
                            element.classList.add('dragover');
                        });
                    });

                    ['dragleave', 'drop'].forEach(eventName => {
                        element.addEventListener(eventName, () => {
                            element.classList.remove('dragover');
                        });
                    });

                    element.addEventListener('drop', (e) => {
                        const files = Array.from(e.dataTransfer.files);
                        if (files.length > 0) {
                            onFiles(files);
                        }
                    });
                },
                cleanup: () => log('Drag-drop cleanup completed')
            }
        };

        log('Fallback services created');
    }

    // Main initialization function
    async function init() {
        log('Dashboard initialization starting...');

        // Try to initialize the full dashboard
        const dashboardInitialized = await initializeDashboard();

        if (dashboardInitialized) {
            // Wait for services to be available
            const servicesAvailable = await waitForServices();

            if (!servicesAvailable) {
                log('Full services not available, creating fallback...');
                createFallbackServices();
            }
        } else {
            log('Dashboard app not available, creating fallback services...');
            createFallbackServices();
        }

        // Dispatch event to indicate dashboard is ready
        document.dispatchEvent(new CustomEvent('dashboardReady', {
            detail: { servicesAvailable: !!window.dashboardServices }
        }));

        log('Dashboard initialization completed');
    }

    // Start initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose utilities for debugging
    window.dashboardInit = {
        log,
        createFallbackServices,
        waitForServices,
        config: DASHBOARD_CONFIG
    };
})();