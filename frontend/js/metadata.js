/**
 * MusicBrainz metadata results view.
 * Renders matching releases with cover art and track listings.
 */
const MetadataView = {
    render(container, data, drive) {
        const releases = data.releases || [];

        // Debug: log the releases data to understand what we're working with
        console.log("DEBUG: Releases data:", releases);
        if (releases.length > 0) {
            console.log("DEBUG: First release:", releases[0]);
            console.log("DEBUG: match_reasons:", releases[0].match_reasons);
            console.log("DEBUG: priority_score:", releases[0].priority_score);
            console.log("DEBUG: mbid:", releases[0].mbid);
        }

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

        const releasesHTML = releases.map((rel, i) => {
            // Debug: check each release
            console.log(`DEBUG Release ${i}:`, {
                mbid: rel.mbid,
                priority_score: rel.priority_score,
                match_reasons: rel.match_reasons,
                disc_number: rel.disc_number,
                total_discs: rel.total_discs
            });

            return `
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

                ${((rel.match_reasons && rel.match_reasons.some && rel.match_reasons.some(r => r.includes("Fallback"))) || rel.priority_score === -1 || !rel.mbid || rel.mbid === "") ? `
                    <div class="disc-indicator" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <span>⚠️ Fallback metadata from physical disc</span>
                    </div>
                    <div class="disc-override" style="margin: 1rem 0; padding: 1rem; background: #fff3cd; border-radius: 8px; border: 2px solid #ffc107;">
                        <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                            <label style="display: flex; align-items: center; gap: 0.5rem; font-weight: 600;">
                                <span>This is Disc:</span>
                                <input type="number" min="1" max="10" value="${rel.disc_number}" id="disc-num-${i}" style="width: 60px; padding: 0.4rem; border: 2px solid #ffc107; border-radius: 4px; font-weight: bold;">
                            </label>
                            <span style="font-weight: 600;">of</span>
                            <label style="display: flex; align-items: center; gap: 0.5rem; font-weight: 600;">
                                <input type="number" min="1" max="10" value="${rel.total_discs}" id="total-discs-${i}" style="width: 60px; padding: 0.4rem; border: 2px solid #ffc107; border-radius: 4px; font-weight: bold;">
                            </label>
                            <button class="btn" onclick="MetadataView.updateDiscParams(${i})" style="padding: 0.5rem 1rem; font-size: 0.9rem; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">Update Disc Number</button>
                            <span style="font-size: 0.9rem; color: #856404; font-weight: 500;">(System detected this as disc ${rel.disc_number} - correct if needed)</span>
                        </div>
                    </div>
                ` : ''}
                <table class="track-list">
                    <thead><tr><th><input type="checkbox" ${i === 0 ? 'checked' : ''} onchange="MetadataView.toggleAllTracks(this, ${i})" onclick="event.stopPropagation()"></th><th>#</th><th>Title</th><th>Duration</th></tr></thead>
                    <tbody>
                        ${(rel.tracks || []).map(t => `
                            <tr>
                                <td><input type="checkbox" class="track-checkbox" data-release-index="${i}" data-track-number="${t.number}" ${i === 0 ? 'checked' : ''} onchange="MetadataView.onTrackCheckboxChange(this, ${i})" onclick="event.stopPropagation()"></td>
                                <td>${t.number}</td>
                                <td>${this._esc(t.title)}</td>
                                <td>${this._formatDuration(t.duration_ms)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
        }).join("");

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
        this.updateSelectAllCheckboxState(index);
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

    updateDiscParams(releaseIndex) {
        const discNumInput = document.getElementById(`disc-num-${releaseIndex}`);
        const totalDiscsInput = document.getElementById(`total-discs-${releaseIndex}`);

        const newDiscNum = parseInt(discNumInput.value);
        const newTotalDiscs = parseInt(totalDiscsInput.value);

        if (newDiscNum < 1 || newTotalDiscs < 1 || newDiscNum > newTotalDiscs) {
            App.showToast("Invalid disc numbers. Disc must be between 1 and total discs.", "error");
            return;
        }

        // Update the release object
        this._releases[releaseIndex].disc_number = newDiscNum;
        this._releases[releaseIndex].total_discs = newTotalDiscs;

        // Re-render the view to show updated disc numbers
        this.render(document.getElementById("rip-container"), {
            releases: this._releases
        }, this._drive);

        App.showToast(`Updated to Disc ${newDiscNum} of ${newTotalDiscs}`, "success");
    },

    toggleAllTracks(checkbox, releaseIndex) {
        const checkboxes = document.querySelectorAll(`.track-checkbox[data-release-index="${releaseIndex}"]`);
        checkboxes.forEach(cb => {
            cb.checked = checkbox.checked;
        });
        // Clear indeterminate state when explicitly toggling
        checkbox.indeterminate = false;
    },

    onTrackCheckboxChange(checkbox, releaseIndex) {
        this.updateSelectAllCheckboxState(releaseIndex);
    },

    updateSelectAllCheckboxState(releaseIndex) {
        const allCheckboxes = document.querySelectorAll(`.track-checkbox[data-release-index="${releaseIndex}"]`);
        if (allCheckboxes.length === 0) return;

        const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
        const someChecked = Array.from(allCheckboxes).some(cb => cb.checked);

        const selectAllCheckbox = document.querySelector(`.release-card[data-index="${releaseIndex}"] thead input[type="checkbox"]`);
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = allChecked;
            selectAllCheckbox.indeterminate = someChecked && !allChecked;
        }
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
