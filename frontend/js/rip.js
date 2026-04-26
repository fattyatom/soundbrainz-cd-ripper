/**
 * Rip controls and progress view.
 * Handles the rip workflow and progress polling.
 */
const RipView = {
    _pollTimer: null,
    _consecutiveErrors: 0,

    render() {
        // Initial state shown in index.html; dynamic content added by startLookup/startRip
    },

    async startLookup(drive) {
        const container = document.getElementById("rip-container");
        container.innerHTML = '<p class="loading">Looking up disc on MusicBrainz...</p>';

        try {
            const data = await API.lookupDisc(drive.device);
            MetadataView.render(container, data, drive);
        } catch (err) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>Lookup failed</h3>
                    <p>${err.message}</p>
                    <p style="margin-top: 0.5rem; font-size: 0.85rem;">You can still rip without metadata.</p>
                </div>
                <div class="action-bar">
                    <button class="btn" onclick="RipView.startRipWithoutMetadata('${drive.device}')">Rip Without Metadata</button>
                    <button class="btn btn-secondary" onclick="App.switchView('drives')">Back</button>
                </div>`;
        }
    },

    async startRip(device, release, selectedTracks = null) {
        const container = document.getElementById("rip-container");
        container.innerHTML = `
            <h2 style="margin-bottom: 1rem;">Ripping: ${release ? release.album : 'Unknown Album'}</h2>
            <div class="progress-bar"><div class="progress-fill" id="rip-progress-fill"></div></div>
            <p class="progress-text" id="rip-progress-text">Starting...</p>
        `;

        try {
            await API.startRip({ device, release, selectedTracks });
            this._startPolling();
            App.showToast("Rip started successfully", "success");
        } catch (err) {
            App.showToast("Failed to start rip: " + err.message, "error");

            // Show helpful error message for missing dependencies
            if (err.message && err.message.includes("Missing dependencies")) {
                App.showToast("Install missing tools: brew install cdparanoia ffmpeg", "error", 10000);
            }
        }
    },

    startRipWithoutMetadata(device) {
        this.startRip(device, null);
    },

    _getSavedStatus() {
        const progressBar = document.getElementById("rip-progress-fill");
        const progressText = document.getElementById("rip-progress-text");

        if (!progressBar || !progressText) return null;

        return {
            phase: progressBar.dataset.phase || "",
            track: progressBar.dataset.track || "0",
            total: progressBar.dataset.total || "0",
            percent: progressBar.style.width || "0%",
            text: progressText.textContent || "Starting...",
            active: true
        };
    },

    _getPhaseText(status) {
        if (status.phase === 'ripping') {
            return `Ripping track ${status.track} of ${status.total_tracks} (${status.percent}%)`;
        } else if (status.phase === 'transcoding') {
            return `Transcoding to FLAC (${status.percent}%)`;
        } else if (status.phase === 'organizing') {
            return 'Organizing files...';
        } else if (status.phase === 'done') {
            return 'Complete!';
        } else if (status.phase === 'error') {
            return `Error: ${status.error || 'Unknown error'}`;
        } else if (status.phase === 'starting') {
            return 'Starting rip...';
        }
        return 'Starting...';
    },

    resumePolling(backendStatus) {
        // Accept either backend status or saved state
        const status = backendStatus || this._getSavedStatus();

        if (!status || (status.active === false && status.phase !== 'done' && status.phase !== 'error')) {
            this.render();
            return;
        }

        // Map backend status to UI format
        const uiStatus = {
            phase: status.phase || "",
            track: status.track || "0",
            total: status.total_tracks || "0",
            percent: `${status.percent || 0}%`,
            text: this._getPhaseText(status),
            active: status.active
        };

        this._showProgress(uiStatus);
        this._startPolling();
    },

    _showProgress(status) {
        const container = document.getElementById("rip-container");

        container.innerHTML = `
            <h2 style="margin-bottom: 1rem;">Ripping Progress</h2>
            <div class="progress-section">
                <div class="progress-bar">
                    <div class="progress-fill" id="rip-progress-fill"
                         data-phase="${status.phase}"
                         data-track="${status.track}"
                         data-total="${status.total}"
                         style="width: ${status.percent}">
                    </div>
                </div>
                <p class="progress-text" id="rip-progress-text">${status.text}</p>
            </div>
            <div class="action-bar">
                <button class="btn btn-secondary" onclick="App.switchView('drives')">Back to Drives</button>
            </div>
        `;
    },

    _startPolling() {
        this._stopPolling();
        this._pollTimer = setInterval(() => this._pollStatus(), 2000);
    },

    _stopPolling() {
        if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
    },

    async _pollStatus() {
        // Add resilience to missing elements
        const progressBar = document.getElementById("rip-progress-fill");
        const progressText = document.getElementById("rip-progress-text");

        // If elements don't exist (user navigated away), skip this poll
        if (!progressBar || !progressText) {
            return;
        }

        try {
            const status = await API.getRipStatus();

            // Reset error counter on success
            this._consecutiveErrors = 0;

            // Update progress bar
            progressBar.style.width = `${status.percent || 0}%`;
            progressBar.dataset.phase = status.phase || "";
            progressBar.dataset.track = status.track || "0";
            progressBar.dataset.total = status.total_tracks || "0";

            // Update text based on phase
            if (status.phase === "ripping") {
                progressText.textContent = `Ripping track ${status.track} of ${status.total_tracks} (${status.percent}%)`;
            } else if (status.phase === "transcoding") {
                progressText.textContent = `Transcoding to FLAC (${status.percent}%)`;
            } else if (status.phase === "organizing") {
                progressText.textContent = "Organizing files...";
            } else if (status.phase === "done") {
                progressText.textContent = "Complete!";
                progressBar.style.width = "100%";
                this._stopPolling();
                App.showToast("Rip complete!", "success");
                App.updateRipNavigationIndicator(false);
            } else if (status.phase === "error") {
                progressText.textContent = `Error: ${status.error || "Unknown error"}`;
                this._stopPolling();
                App.showToast(status.error || "Unknown error", "error");
                App.updateRipNavigationIndicator(false);
            } else if (status.phase === "starting") {
                progressText.textContent = "Starting rip...";
            }

            // Stop polling if rip is no longer active and not done
            if (!status.active && status.phase !== "done" && status.phase !== "error") {
                this._stopPolling();
            }
        } catch (err) {
            console.error("Polling error:", err);

            // Implement exponential backoff for network errors
            if (err.message && err.message.includes("Failed to fetch")) {
                this._consecutiveErrors = (this._consecutiveErrors || 0) + 1;

                if (this._consecutiveErrors >= 3) {
                    this._stopPolling();
                    App.showToast("Connection lost - refresh to continue", "error");
                }
            } else {
                // Reset error counter on non-network errors
                this._consecutiveErrors = 0;
            }
        }
    },
};
