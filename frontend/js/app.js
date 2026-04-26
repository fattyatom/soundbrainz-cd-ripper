/**
 * Main application logic.
 * Handles view switching and toast notifications.
 */
const App = {
    // Track current view
    currentView: "drives",

    // Background monitoring
    _backgroundCheckTimer: null,
    _lastKnownRipState: null,

    // Application state persistence
    state: {
        // Rip state persistence
        isRipping: false,
        ripStatus: null,

        // Save rip state before navigation
        saveRipState() {
            const container = document.getElementById("rip-container");
            if (!container) return;

            const progressBar = document.getElementById("rip-progress-fill");
            const progressText = document.getElementById("rip-progress-text");

            this.isRipping = progressBar !== null;
            if (progressBar && progressText) {
                this.ripStatus = {
                    phase: progressBar.dataset.phase || "",
                    track: progressBar.dataset.track || "0",
                    total: progressBar.dataset.total || "0",
                    percent: progressBar.style.width || "0%",
                    text: progressText.textContent || "Starting..."
                };
            }
        },

        // Restore rip state when returning to rip view
        async restoreRipState() {
            // First check if we have in-memory state
            if (this.isRipping && this.ripStatus) {
                RipView.resumePolling(this.ripStatus);
                return;
            }

            // If no in-memory state, check backend directly
            try {
                const status = await API.getRipStatus();
                if (status.active) {
                    // Backend has active rip - initialize state and show it
                    this.isRipping = true;
                    this.ripStatus = {
                        phase: status.phase || "",
                        track: status.track || "0",
                        total: status.total_tracks || "0",
                        percent: `${status.percent || 0}%`,
                        text: this._getPhaseTextForStatus(status),
                        active: true
                    };
                    RipView.resumePolling(this.ripStatus);
                } else {
                    // No active rip - show default state
                    RipView.render();
                }
            } catch (err) {
                console.error('Failed to check rip status when restoring:', err);
                // On error, show default state
                RipView.render();
            }
        }
    },

    _getPhaseTextForStatus(status) {
        if (status.phase === 'ripping') {
            return `Ripping track ${status.track} of ${status.total_tracks} (${status.percent}%)`;
        } else if (status.phase === 'transcoding') {
            return `Transcoding to FLAC (${status.percent}%)`;
        } else if (status.phase === 'organizing') {
            return 'Organizing files...';
        } else if (status.phase === 'done') {
            return 'Complete!';
        } else if (status.phase === 'starting') {
            return 'Starting rip...';
        }
        return 'In progress...';
    },

    async checkForActiveRip() {
        try {
            const status = await API.getRipStatus();

            if (status.active) {
                // Active rip - initialize state but don't auto-navigate
                this.state.isRipping = true;
                this.state.ripStatus = {
                    phase: status.phase || "",
                    track: status.track || "0",
                    total: status.total_tracks || "0",
                    percent: `${status.percent || 0}%`,
                    text: this._getPhaseTextForStatus(status),
                    active: true
                };

                // Update navigation indicator
                this.updateRipNavigationIndicator(true);

                // Show toast - user can manually navigate to Rip view
                this.showToast('Active rip detected - click Rip view to see progress', 'info');
            } else if (status.phase === 'done') {
                // Rip completed while closed
                this.showToast('Previous rip completed successfully', 'success');
            } else if (status.phase === 'error') {
                // Previous rip failed
                this.showToast(`Previous rip failed: ${status.error || 'Unknown error'}`, 'error');
            }
        } catch (err) {
            console.error('Failed to check rip status on init:', err);
            // Non-blocking - don't prevent app from loading
        }
    },

    startBackgroundRipMonitoring() {
        // Check every 10 seconds
        this._backgroundCheckTimer = setInterval(async () => {
            await this._checkRipStateInBackground();
        }, 10000);
    },

    stopBackgroundRipMonitoring() {
        if (this._backgroundCheckTimer) {
            clearInterval(this._backgroundCheckTimer);
            this._backgroundCheckTimer = null;
        }
    },

    async _checkRipStateInBackground() {
        try {
            const status = await API.getRipStatus();
            const currentState = JSON.stringify(status);

            // Only act if state changed
            if (currentState !== this._lastKnownRipState) {
                this._handleRipStateChange(status);
                this._lastKnownRipState = currentState;
            }
        } catch (err) {
            console.error('Background rip check failed:', err);
        }
    },

    _handleRipStateChange(status) {
        const oldState = this._lastKnownRipState ? JSON.parse(this._lastKnownRipState) : null;

        // Handle rip completion
        if (!status.active && status.phase === 'done') {
            this.showToast('Rip completed successfully!', 'success');
            this.updateRipNavigationIndicator(false);

            // Clear in-memory state
            this.state.isRipping = false;
            this.state.ripStatus = null;
            return;
        }

        // Handle rip error
        if (status.phase === 'error') {
            this.showToast(`Rip failed: ${status.error || 'Unknown error'}`, 'error');
            this.updateRipNavigationIndicator(false);

            // Clear in-memory state
            this.state.isRipping = false;
            this.state.ripStatus = null;
            return;
        }

        // Handle rip becoming active
        if (status.active && (!oldState || !oldState.active)) {
            this.showToast('Rip started - check Rip view for progress', 'info');
            this.updateRipNavigationIndicator(true);

            // Initialize in-memory state
            this.state.isRipping = true;
            this.state.ripStatus = {
                phase: status.phase || "",
                track: status.track || "0",
                total: status.total_tracks || "0",
                percent: `${status.percent || 0}%`,
                text: this._getPhaseTextForStatus(status),
                active: true
            };

            // If currently on rip view, auto-start polling
            if (this.currentView === 'rip') {
                RipView.resumePolling(this.state.ripStatus);
            }
            return;
        }

        // Handle rip stopping (not complete/error)
        if (!status.active && oldState && oldState.active) {
            this.updateRipNavigationIndicator(false);

            // Clear in-memory state
            this.state.isRipping = false;
            this.state.ripStatus = null;
        }
    },

    updateRipNavigationIndicator(isActive) {
        const ripBtn = document.querySelector('.nav-btn[data-view="rip"]');
        if (ripBtn) {
            // Add visual indicator for active rip
            ripBtn.classList.toggle('rip-active', isActive);
            ripBtn.textContent = isActive ? 'Rip ●' : 'Rip';
        }
    },

    async init() {
        // Set up nav buttons
        document.querySelectorAll(".nav-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                this.switchView(btn.dataset.view);
            });
        });

        // Load initial view (await to ensure it completes)
        await DrivesView.render();

        // Check for active rip on page load (after drives are loaded)
        await this.checkForActiveRip();

        // Start background monitoring
        this.startBackgroundRipMonitoring();
    },

    switchView(viewName) {
        // Save current state before switching
        if (this.currentView === "rip") {
            this.state.saveRipState();
        }

        // Update nav
        document.querySelectorAll(".nav-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.view === viewName);
        });

        // Update views
        document.querySelectorAll(".view").forEach(view => {
            view.classList.toggle("active", view.id === `view-${viewName}`);
        });

        // Trigger view render
        if (viewName === "drives") DrivesView.render();
        if (viewName === "settings") SettingsView.render();
        if (viewName === "rip") {
            // Check for active rip and restore
            this.state.restoreRipState();
        }

        this.currentView = viewName;
    },

    showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transition = "opacity 0.3s";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },
};

// Start the app
document.addEventListener("DOMContentLoaded", () => App.init());

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    App.stopBackgroundRipMonitoring();
    RipView._stopPolling();
});
