/**
 * Settings view.
 * Output folder, naming pattern, language/genre preferences.
 */
const SettingsView = {
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
        container.innerHTML = `
            <h2 style="margin-bottom: 1.25rem;">Settings</h2>
            <form id="settings-form" onsubmit="SettingsView.onSave(event)">
                <div class="form-group">
                    <label for="output-dir">Output Folder</label>
                    <div style="display: flex; gap: 0.5rem;">
                        <input type="text" id="output-dir" value="${this._esc(settings.output_dir || '')}" placeholder="/path/to/music">
                        <button type="button" class="btn btn-secondary" onclick="SettingsView.onDetectStructure()">Detect</button>
                    </div>
                </div>

                <div class="form-group">
                    <label for="folder-pattern">Folder/File Pattern</label>
                    <input type="text" id="folder-pattern" value="${this._esc(settings.folder_pattern || '')}"
                           placeholder="{artist}/{album}/{number:02d} - {title}.flac">
                    <p class="form-hint">Available: {artist}, {album}, {title}, {number}, {year}, {genre}</p>
                </div>

                <div class="form-group">
                    <label for="pref-language">Preferred Language</label>
                    <input type="text" id="pref-language" value="${this._esc(settings.preferred_language || '')}" placeholder="en">
                </div>

                <div class="form-group">
                    <label for="pref-country">Preferred Country</label>
                    <input type="text" id="pref-country" value="${this._esc(settings.preferred_country || '')}" placeholder="US">
                </div>

                <div class="form-group">
                    <label for="pref-genre">Preferred Genre</label>
                    <input type="text" id="pref-genre" value="${this._esc(settings.preferred_genre || '')}" placeholder="rock">
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
        const settings = {
            output_dir: document.getElementById("output-dir").value,
            folder_pattern: document.getElementById("folder-pattern").value,
            preferred_language: document.getElementById("pref-language").value,
            preferred_country: document.getElementById("pref-country").value,
            preferred_genre: document.getElementById("pref-genre").value,
        };

        try {
            await API.saveSettings(settings);
            App.showToast("Settings saved", "success");
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
