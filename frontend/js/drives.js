/**
 * Drive selection view.
 * Renders detected drives and handles selection.
 */
const DrivesView = {
    selectedDrive: null,

    async render() {
        const container = document.getElementById("drives-container");
        container.innerHTML = '<p class="loading">Detecting drives...</p>';

        try {
            const data = await API.fetchDrives();
            this.renderDrives(container, data.drives);
        } catch (err) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>Failed to detect drives</h3>
                    <p>${err.message}</p>
                </div>`;
            App.showToast(err.message, "error");
        }
    },

    renderDrives(container, drives) {
        if (drives.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No CD/DVD drives found</h3>
                    <p>Connect a USB or SATA optical drive and click Refresh.</p>
                </div>
                <div class="action-bar">
                    <button class="btn btn-secondary" onclick="DrivesView.render()">Refresh</button>
                </div>`;
            return;
        }

        const listHTML = drives.map((drive, i) => `
            <li class="drive-item" data-index="${i}" onclick="DrivesView.selectDrive(${i})">
                <div class="drive-info">
                    <h3>${this.escapeHTML(drive.name)}</h3>
                    <span class="device-path">${this.escapeHTML(drive.device)}</span>
                    <span style="margin-left: 0.5rem; font-size: 0.75rem; color: #666;">${this.escapeHTML(drive.drive_type)}</span>
                </div>
                <span class="drive-status ${drive.has_disc ? 'disc-in' : 'no-disc'}">
                    ${drive.has_disc ? 'Disc Inserted' : 'No Disc'}
                </span>
            </li>
        `).join("");

        container.innerHTML = `
            <ul class="drive-list">${listHTML}</ul>
            <div class="action-bar">
                <button class="btn btn-secondary" onclick="DrivesView.render()">Refresh</button>
                <button class="btn" id="btn-lookup" disabled onclick="DrivesView.onLookup()">Look Up Disc</button>
                <button class="btn btn-secondary" id="btn-eject" disabled onclick="DrivesView.onEject()">Eject</button>
            </div>`;

        // Store drives data for later use
        this._drives = drives;

        // Auto-select single drive (but don't auto-lookup)
        if (drives.length === 1 && drives[0].has_disc) {
            this.selectDrive(0);
            App.showToast(`Auto-selected drive: ${drives[0].name}`);
            // REMOVED: Auto-lookup after short delay - user must manually click "Look Up Disc"
        }
    },

    selectDrive(index) {
        const drive = this._drives[index];
        this.selectedDrive = drive;

        // Update UI selection
        document.querySelectorAll(".drive-item").forEach((el, i) => {
            el.classList.toggle("selected", i === index);
        });

        // Enable/disable buttons
        document.getElementById("btn-lookup").disabled = !drive.has_disc;
        document.getElementById("btn-eject").disabled = false;
    },

    async onEject() {
        if (!this.selectedDrive) return;
        try {
            await API.ejectDrive(this.selectedDrive.device);
            App.showToast("Disc ejected", "success");
            this.render();
        } catch (err) {
            App.showToast("Eject failed: " + err.message, "error");
        }
    },

    onLookup() {
        if (!this.selectedDrive) return;
        App.switchView("rip");
        RipView.startLookup(this.selectedDrive);
    },

    escapeHTML(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    },
};
