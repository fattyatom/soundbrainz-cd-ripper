/**
 * Rip controls and progress view.
 * Handles the rip workflow and progress polling.
 */
const RipView = {
    _pollTimer: null,

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

    async startRip(device, release) {
        const container = document.getElementById("rip-container");
        container.innerHTML = `
            <h2 style="margin-bottom: 1rem;">Ripping: ${release ? release.album : 'Unknown Album'}</h2>
            <div class="progress-bar"><div class="progress-fill" id="rip-progress-fill"></div></div>
            <p class="progress-text" id="rip-progress-text">Starting...</p>
        `;

        try {
            await API.startRip({ device, release });
            this._startPolling();
        } catch (err) {
            App.showToast("Failed to start rip: " + err.message, "error");
        }
    },

    startRipWithoutMetadata(device) {
        this.startRip(device, null);
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
        try {
            const status = await API.getRipStatus();
            const fill = document.getElementById("rip-progress-fill");
            const text = document.getElementById("rip-progress-text");

            if (!fill || !text) return;

            fill.style.width = `${status.percent || 0}%`;

            if (status.phase === "ripping") {
                text.textContent = `Ripping track ${status.track} of ${status.total_tracks} (${status.percent}%)`;
            } else if (status.phase === "transcoding") {
                text.textContent = `Transcoding to FLAC (${status.percent}%)`;
            } else if (status.phase === "organizing") {
                text.textContent = "Organizing files...";
            } else if (status.phase === "done") {
                text.textContent = "Complete!";
                fill.style.width = "100%";
                this._stopPolling();
                App.showToast("Rip complete!", "success");
            } else if (status.error) {
                text.textContent = `Error: ${status.error}`;
                this._stopPolling();
                App.showToast(status.error, "error");
            }

            if (!status.active && status.phase !== "done") {
                this._stopPolling();
            }
        } catch (err) {
            // Silently retry on poll failures
        }
    },
};
