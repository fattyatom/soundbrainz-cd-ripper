/**
 * MusicBrainz metadata results view.
 * Renders matching releases with cover art and track listings.
 */
const MetadataView = {
    render(container, data, drive) {
        const releases = data.releases || [];
        if (releases.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No matches found</h3>
                    <p>MusicBrainz couldn't identify this disc.</p>
                </div>
                <div class="action-bar">
                    <button class="btn" onclick="RipView.startRipWithoutMetadata('${drive.device}')">Rip Without Metadata</button>
                    <button class="btn btn-secondary" onclick="App.switchView('drives')">Back</button>
                </div>`;
            return;
        }

        const releasesHTML = releases.map((rel, i) => `
            <div class="release-card ${i === 0 ? 'selected' : ''}" data-index="${i}" onclick="MetadataView.selectRelease(${i})">
                ${rel.match_reasons && rel.match_reasons.length > 0 ? `
                    <div class="priority-badge">
                        <span class="priority-star">⭐</span>
                        <span class="priority-reasons">${this._esc(rel.match_reasons.join(" • "))}</span>
                    </div>
                ` : ''}

                <div class="release-header">
                    ${rel.cover_art_url
                        ? `<img class="cover-art" src="${rel.cover_art_url}" alt="Cover" onerror="this.style.display='none'">`
                        : '<div class="cover-art-placeholder"></div>'}
                    <div class="release-info">
                        <h3>${this._esc(rel.album)}</h3>
                        <p>${this._esc(rel.artist)}</p>
                        <p class="release-meta">
                            ${rel.year ? this._esc(String(rel.year)) : 'Unknown year'}
                            ${rel.country ? ' · ' + this._esc(rel.country) : ''}
                            ${rel.label ? ' · ' + this._esc(rel.label) : ''}
                            ${rel.language ? ' · ' + this._esc(rel.language) : ''}
                        </p>
                    </div>
                </div>
                ${rel.medium_format ? `
                    <div class="format-badge">${this._esc(rel.medium_format)}</div>
                ` : ''}
                ${rel.disc_number ? `
                    <div class="disc-indicator">
                        <span class="disc-badge">Disc ${rel.disc_number}</span>
                        <span class="disc-total">of ${rel.total_discs}</span>
                    </div>
                ` : ''}
                ${(rel.match_reasons && rel.match_reasons.includes("Fallback metadata from physical disc")) ? `
                    <div class="disc-indicator" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <span>⚠️ Fallback metadata from physical disc</span>
                    </div>
                ` : ''}
                <table class="track-list">
                    <thead><tr><th><input type="checkbox" ${i === 0 ? 'checked' : ''} onchange="MetadataView.toggleAllTracks(this, ${i})"></th><th>#</th><th>Title</th><th>Duration</th></tr></thead>
                    <tbody>
                        ${(rel.tracks || []).map(t => `
                            <tr>
                                <td><input type="checkbox" class="track-checkbox" data-release-index="${i}" data-track-number="${t.number}" ${i === 0 ? 'checked' : ''}></td>
                                <td>${t.number}</td>
                                <td>${this._esc(t.title)}</td>
                                <td>${this._formatDuration(t.duration_ms)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `).join("");

        container.innerHTML = `
            <h2 style="margin-bottom: 1rem;">Select a Release</h2>
            <div class="releases">${releasesHTML}</div>
            <div class="action-bar">
                <button class="btn" id="btn-rip" onclick="MetadataView.onRip()">Rip Selected</button>
                <button class="btn btn-secondary" onclick="App.switchView('drives')">Back</button>
            </div>`;

        this._releases = releases;
        this._drive = drive;
        this._selectedIndex = 0;
    },

    selectRelease(index) {
        this._selectedIndex = index;
        document.querySelectorAll(".release-card").forEach((el, i) => {
            el.classList.toggle("selected", i === index);
        });

        // Update the "Select All" checkbox state for the newly selected release
        const allCheckboxes = document.querySelectorAll(`.track-checkbox[data-release-index="${index}"]`);
        const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
        const selectAllCheckbox = document.querySelector(`.release-card[data-index="${index}"] thead input[type="checkbox"]`);
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = allChecked && allCheckboxes.length > 0;
        }
    },

    onRip() {
        const release = this._releases[this._selectedIndex];
        const selectedTracks = this.getSelectedTracks();

        if (selectedTracks.length === 0) {
            App.showToast("Please select at least one track", "error");
            return;
        }

        RipView.startRip(this._drive.device, release, selectedTracks);
    },

    getSelectedTracks() {
        const checkboxes = document.querySelectorAll(`.track-checkbox[data-release-index="${this._selectedIndex}"]:checked`);
        return Array.from(checkboxes).map(cb => parseInt(cb.dataset.trackNumber)).sort((a, b) => a - b);
    },

    toggleAllTracks(checkbox, releaseIndex) {
        const checkboxes = document.querySelectorAll(`.track-checkbox[data-release-index="${releaseIndex}"]`);
        checkboxes.forEach(cb => {
            cb.checked = checkbox.checked;
        });
    },

    _esc(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    },

    _formatDuration(ms) {
        if (!ms) return "--:--";
        const totalSec = Math.round(ms / 1000);
        const min = Math.floor(totalSec / 60);
        const sec = totalSec % 60;
        return `${min}:${sec.toString().padStart(2, "0")}`;
    },
};
