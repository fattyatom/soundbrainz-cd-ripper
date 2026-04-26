/**
 * Settings view.
 * Output folder, naming pattern, language/genre preferences.
 */
const SettingsView = {
    // Default settings for fallback
    DEFAULTS: {
        output_dir: "/Users/casey/Music",
        folder_pattern: "{artist}/{album}/{number:02d} - {title}.flac",
        folder_pattern_multi_disc: "{artist}/{album}/CD{disc}/{number:02d} - {title}.flac",
        preferred_languages: ["en"],
        preferred_country: "",
        preferred_genre: "",
        rip_speed: "balanced",
    },

    async render() {
        const container = document.getElementById("settings-container");
        container.innerHTML = '<p class="loading">Loading settings...</p>';

        try {
            const data = await API.getSettings();
            this._renderForm(container, data);
        } catch (err) {
            container.innerHTML = `<p>Failed to load settings: ${err.message}</p>`;
        }
    },

    _renderForm(container, settings) {
        // Use defaults for empty strings
        const displaySettings = {
            output_dir: settings.output_dir || this.DEFAULTS.output_dir,
            folder_pattern: settings.folder_pattern || this.DEFAULTS.folder_pattern,
            folder_pattern_multi_disc: settings.folder_pattern_multi_disc || this.DEFAULTS.folder_pattern_multi_disc,
            preferred_languages: settings.preferred_languages || this.DEFAULTS.preferred_languages,
            preferred_country: settings.preferred_country || this.DEFAULTS.preferred_country,
            preferred_genre: settings.preferred_genre || this.DEFAULTS.preferred_genre,
            rip_speed: settings.rip_speed || this.DEFAULTS.rip_speed,
        };

        const languages = displaySettings.preferred_languages.join(', ');

        container.innerHTML = `
            <h2 style="margin-bottom: 1.25rem;">Settings</h2>
            <form id="settings-form" onsubmit="SettingsView.onSave(event)">
                <div class="form-group">
                    <label for="output-dir">Output Folder</label>
                    <div style="display: flex; gap: 0.5rem;">
                        <input type="text" id="output-dir" value="${this._esc(displaySettings.output_dir)}" placeholder="/path/to/music">
                        <button type="button" class="btn btn-secondary" onclick="SettingsView.onDetectStructure()">Detect</button>
                    </div>
                    <p class="form-hint">Default: ${this.DEFAULTS.output_dir}</p>
                </div>

                <div class="form-group">
                    <label for="folder-pattern">Folder/File Pattern (Single Disc)</label>
                    <input type="text" id="folder-pattern" value="${this._esc(displaySettings.folder_pattern)}"
                           placeholder="{artist}/{album}/{number:02d} - {title}.flac">
                    <p class="form-hint">Used when album has only one CD. Available: {artist}, {album}, {title}, {number}, {year}, {genre}</p>
                </div>

                <div class="form-group">
                    <label for="folder-pattern-multi">Folder/File Pattern (Multi-Disc)</label>
                    <input type="text" id="folder-pattern-multi" value="${this._esc(displaySettings.folder_pattern_multi_disc)}"
                           placeholder="{artist}/{album}/CD{disc}/{number:02d} - {title}.flac">
                    <p class="form-hint">Used when album has multiple CDs. Additional: {disc} for CD number</p>
                </div>

                <div class="form-group">
                    <label for="rip-speed">Rip Speed</label>
                    <select id="rip-speed">
                        <option value="accurate" ${displaySettings.rip_speed === 'accurate' ? 'selected' : ''}>Accurate (Best Quality)</option>
                        <option value="balanced" ${displaySettings.rip_speed === 'balanced' ? 'selected' : ''}>Balanced (Recommended)</option>
                        <option value="fast" ${displaySettings.rip_speed === 'fast' ? 'selected' : ''}>Fast (Maximum Speed)</option>
                    </select>
                    <p class="form-hint">Controls ripping speed vs error recovery. Accurate is slowest but best for damaged discs.</p>
                </div>

                <div class="form-group">
                    <label for="pref-languages">Preferred Languages (comma-separated, priority order)</label>
                    <input type="text" id="pref-languages" value="${this._esc(languages)}"
                           placeholder="en, ja, fr">
                    <p class="form-hint">First language has highest priority. Example: "en, ja" prefers English over Japanese</p>
                </div>

                <div class="form-group">
                    <label for="pref-country">Preferred Country</label>
                    <input type="text" id="pref-country" value="${this._esc(displaySettings.preferred_country)}" placeholder="US">
                </div>

                <div class="form-group">
                    <label for="pref-genre">Preferred Genre</label>
                    <input type="text" id="pref-genre" value="${this._esc(displaySettings.preferred_genre)}" placeholder="rock">
                </div>

                <div class="action-bar">
                    <button type="submit" class="btn">Save Settings</button>
                </div>
            </form>
            <div id="structure-result" style="margin-top: 1rem;"></div>
        `;
    },

    async onSave(event) {
        event.preventDefault();

        // Parse languages from comma-separated string
        const languagesStr = document.getElementById("pref-languages").value;
        const languages = languagesStr.split(',').map(l => l.trim()).filter(l => l);

        const settings = {
            output_dir: document.getElementById("output-dir").value,
            folder_pattern: document.getElementById("folder-pattern").value,
            folder_pattern_multi_disc: document.getElementById("folder-pattern-multi").value,
            rip_speed: document.getElementById("rip-speed").value,
            preferred_languages: languages,
            preferred_country: document.getElementById("pref-country").value,
            preferred_genre: document.getElementById("pref-genre").value,
        };

        try {
            const saved = await API.saveSettings(settings);
            App.showToast(`Settings saved! Output: ${saved.output_dir}`, "success");
        } catch (err) {
            App.showToast("Failed to save: " + err.message, "error");
        }
    },

    async onDetectStructure() {
        const dir = document.getElementById("output-dir").value;
        if (!dir) {
            App.showToast("Enter an output folder first", "error");
            return;
        }

        const resultEl = document.getElementById("structure-result");
        resultEl.innerHTML = '<p class="loading">Analyzing folder structure...</p>';

        try {
            const data = await API.detectStructure(dir);
            if (data.pattern) {
                document.getElementById("folder-pattern").value = data.pattern;
                resultEl.innerHTML = `<p style="color: #4caf50;">Detected pattern: <code>${this._esc(data.pattern)}</code></p>`;
            } else {
                resultEl.innerHTML = '<p>No existing structure detected. Using default pattern.</p>';
            }
        } catch (err) {
            resultEl.innerHTML = `<p style="color: #e94560;">${err.message}</p>`;
        }
    },

    _esc(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    },
};
