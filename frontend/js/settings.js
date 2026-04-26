/**
 * Settings view.
 * Output folder, naming pattern, language/genre preferences.
 */
const SettingsView = {
    // Default settings for fallback
    DEFAULTS: {
        output_dir: "/Users/casey/Music",
        folder_pattern: "{album_artist}/{album}/{number:02d} - {title}.{ext}",
        folder_pattern_multi_disc: "{album_artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}",
        preferred_languages: ["en"],
        preferred_country: "",
        preferred_genre: "",
        // New audio quality settings (replaces rip_speed)
        audio_format: "aiff",
        flac_compression_level: 0,
        quality_preset: "audiophile",
        auto_eject: true,
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
            audio_format: settings.audio_format || this.DEFAULTS.audio_format,
            flac_compression_level: settings.flac_compression_level || this.DEFAULTS.flac_compression_level,
            quality_preset: settings.quality_preset || this.DEFAULTS.quality_preset,
            auto_eject: settings.auto_eject !== undefined ? settings.auto_eject : this.DEFAULTS.auto_eject,
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
                    <p class="form-hint">Used when album has only one CD. Available: {album_artist}, {artist}, {album}, {title}, {number}, {year}, {genre}</p>
                </div>

                <div class="form-group">
                    <label for="folder-pattern-multi">Folder/File Pattern (Multi-Disc)</label>
                    <input type="text" id="folder-pattern-multi" value="${this._esc(displaySettings.folder_pattern_multi_disc)}"
                           placeholder="{artist}/{album}/CD{disc}/{number:02d} - {title}.{ext}">
                    <p class="form-hint">Used when album has multiple CDs. Available: {album_artist}, {artist}, {album}, {title}, {number}, {disc}, {ext}, {year}, {genre}</p>
                </div>

                <div class="form-group" id="audio-quality-section">
                    <label style="font-weight: bold; margin-bottom: 0.5rem; display: block;">Audio Quality</label>

                    <!-- Quality Presets -->
                    <div style="margin-bottom: 1rem;">
                        <label style="font-weight: normal; margin-bottom: 0.25rem; display: block;">Quality Preset</label>
                        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            <button type="button" data-preset="audiophile" class="preset-btn ${displaySettings.quality_preset === 'audiophile' ? 'active' : ''}">Audiophile</button>
                            <button type="button" data-preset="portable" class="preset-btn ${displaySettings.quality_preset === 'portable' ? 'active' : ''}">Portable</button>
                            <button type="button" data-preset="archive" class="preset-btn ${displaySettings.quality_preset === 'archive' ? 'active' : ''}">Archive</button>
                            <button type="button" data-preset="custom" class="preset-btn ${displaySettings.quality_preset === 'custom' ? 'active' : ''}">Custom</button>
                        </div>
                        <div id="preset-description" class="preset-description" style="padding: 0.5rem; background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 4px; margin-top: 0.5rem; font-size: 0.9em; line-height: 1.4;">
                            ${this._getPresetDescription(displaySettings.quality_preset)}
                        </div>
                    </div>

                    <!-- Audio Format Selection -->
                    <div style="margin-bottom: 1rem;">
                        <label for="audio-format" style="font-weight: normal; margin-bottom: 0.25rem; display: block;">Audio Format</label>
                        <select id="audio-format" name="audio_format" style="padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; background-color: white; min-width: 250px;">
                            <option value="aiff" ${displaySettings.audio_format === 'aiff' ? 'selected' : ''}>AIFF (Uncompressed, Professional)</option>
                            <option value="wav" ${displaySettings.audio_format === 'wav' ? 'selected' : ''}>WAV (Uncompressed, Universal)</option>
                            <option value="flac" ${displaySettings.audio_format === 'flac' ? 'selected' : ''}>FLAC (Lossless, Compressed)</option>
                        </select>
                    </div>

                    <!-- FLAC Compression Level (only shown for FLAC format) -->
                    <div id="flac-compression-row" style="margin-bottom: 1rem; display: ${displaySettings.audio_format === 'flac' ? 'block' : 'none'};">
                        <label for="flac-compression" style="font-weight: normal; margin-bottom: 0.25rem; display: block;">FLAC Compression Level</label>
                        <input type="range" id="flac-compression" name="flac_compression_level"
                               min="0" max="12" value="${displaySettings.flac_compression_level}"
                               style="width: 100%; margin: 0.5rem 0;">
                        <span style="font-weight: bold; color: #007bff;">${displaySettings.flac_compression_level} (${this._getCompressionDescription(displaySettings.flac_compression_level)})</span>
                        <p class="form-hint">0 = No compression (fastest), 5 = Balanced, 8 = High compression, 12 = Maximum compression</p>
                    </div>

                    <!-- Format Info Display -->
                    <div id="format-description" class="format-description" style="padding: 0.5rem; background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 4px; margin-top: 0.5rem; font-size: 0.9em; line-height: 1.4;">
                        ${this._getFormatDescription(displaySettings.audio_format)}
                    </div>
                </div>

                <div class="form-group">
                    <label style="font-weight: bold; margin-bottom: 0.5rem; display: block;">Behavior</label>

                    <div style="margin-bottom: 1rem;">
                        <label style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                            <input type="checkbox" id="auto-eject" name="auto_eject" ${displaySettings.auto_eject ? 'checked' : ''} style="margin: 0;">
                            <span>Automatically eject disc after successful rip</span>
                        </label>
                        <p class="form-hint">When enabled, the CD will be automatically ejected after ripping completes successfully</p>
                    </div>
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

        // Set up audio quality event listeners
        this._setupAudioQualityListeners();
    },

    _setupAudioQualityListeners() {
        const formatSelect = document.getElementById('audio-format');
        const flacRow = document.getElementById('flac-compression-row');
        const formatDesc = document.getElementById('format-description');

        // Format selection - critical: controls visibility of compression options
        formatSelect.addEventListener('change', (e) => {
            const format = e.target.value;

            // CRITICAL: Only show compression controls for FLAC format
            // AIFF and WAV are uncompressed, so compression controls are hidden
            if (format === 'flac') {
                flacRow.style.display = 'block';
            } else {
                flacRow.style.display = 'none';
            }

            // Update format description
            formatDesc.innerHTML = this._getFormatDescription(format);

            // Switch to custom preset when manually changing format
            document.querySelector('[data-preset="custom"]').click();
        });

        // FLAC compression slider (only relevant for FLAC format)
        const compressionSlider = document.getElementById('flac-compression');
        compressionSlider.addEventListener('input', (e) => {
            const level = e.target.value;
            const valueDisplay = compressionSlider.nextElementSibling;
            valueDisplay.textContent = `${level} (${this._getCompressionDescription(level)})`;
            document.querySelector('[data-preset="custom"]').click();
        });

        // Preset buttons
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');

                const preset = e.target.dataset.preset;
                if (preset !== 'custom') {
                    this._applyQualityPreset(preset);
                }
            });
        });
    },

    _applyQualityPreset(preset) {
        const settings = {
            audiophile: {
                format: 'aiff',
                flac_level: 5,
                description: 'Slowest, Most Accurate, Uncompressed. 1x rip speed, maximum error recovery, uncompressed AIFF. Best for damaged or rare discs. Includes SHA-256 checksums.'
            },
            portable: {
                format: 'flac',
                flac_level: 5,
                description: 'Fastest, Compressed. Maximum rip speed, standard error correction, FLAC compressed. Good for common discs. Includes SHA-256 checksums.'
            },
            archive: {
                format: 'flac',
                flac_level: 8,
                description: 'Balanced, Compressed. 8x rip speed, high error recovery, FLAC compressed with high compression. Good balance of speed and accuracy. Includes SHA-256 checksums.'
            }
        };

        const config = settings[preset];
        const formatSelect = document.getElementById('audio-format');
        const flacRow = document.getElementById('flac-compression-row');

        // Set format
        formatSelect.value = config.format;

        // CRITICAL: Only set and show compression controls for FLAC format
        if (config.format === 'flac') {
            const compressionSlider = document.getElementById('flac-compression');
            compressionSlider.value = config.flac_level;
            const valueDisplay = compressionSlider.nextElementSibling;
            valueDisplay.textContent = `${config.flac_level} (${this._getCompressionDescription(config.flac_level)})`;
            flacRow.style.display = 'block';
        } else {
            // For AIFF/WAV, hide compression controls entirely
            flacRow.style.display = 'none';
        }

        // Update format description
        const formatDesc = document.getElementById('format-description');
        formatDesc.innerHTML = this._getFormatDescription(config.format);

        // Update preset description
        const presetDesc = document.getElementById('preset-description');
        presetDesc.innerHTML = this._getPresetDescription(preset);
    },

    _getPresetDescription(preset) {
        const descriptions = {
            audiophile: '<strong>Audiophile (Slowest, Most Accurate, Uncompressed):</strong> 1x rip speed, maximum error recovery, uncompressed AIFF. Best for damaged or rare discs. Includes SHA-256 checksums.',
            portable: '<strong>Portable (Fastest, Compressed):</strong> Maximum rip speed, standard error correction, FLAC compressed. Good for common discs. Includes SHA-256 checksums.',
            archive: '<strong>Archive (Balanced, Compressed):</strong> 8x rip speed, high error recovery, FLAC compressed with high compression. Good balance of speed and accuracy. Includes SHA-256 checksums.',
            custom: '<strong>Custom:</strong> Configure all settings manually according to your preferences.'
        };

        return descriptions[preset] || descriptions['custom'];
    },

    _getCompressionDescription(level) {
        if (level == 0) return 'No compression';
        if (level <= 3) return 'Low compression';
        if (level <= 6) return 'Balanced';
        if (level <= 9) return 'High compression';
        return 'Maximum compression';
    },

    _getFormatDescription(format) {
        const descriptions = {
            aiff: '<strong>AIFF:</strong> Uncompressed professional audio format. Largest files, fastest encoding. Professional audio standard.',
            wav: '<strong>WAV:</strong> Uncompressed universal audio format. Largest files, fastest encoding. Maximum compatibility.',
            flac: '<strong>FLAC:</strong> Lossless compressed format. Smaller files than AIFF/WAV, slower encoding. Perfect audio quality with compression.'
        };

        return descriptions[format] || descriptions['aiff'];
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
            preferred_languages: languages,
            preferred_country: document.getElementById("pref-country").value,
            preferred_genre: document.getElementById("pref-genre").value,
            // New audio quality settings
            audio_format: document.getElementById("audio-format").value,
            flac_compression_level: parseInt(document.getElementById("flac-compression").value),
            quality_preset: document.querySelector(".preset-btn.active")?.dataset.preset || "custom",
            auto_eject: document.getElementById("auto-eject").checked,
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
