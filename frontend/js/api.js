/**
 * API client for SoundBrainz backend.
 * All fetch wrappers for /api/* endpoints.
 */
const API = {
    async get(url) {
        const response = await fetch(url);
        if (!response.ok) {
            const err = await response.json().catch(() => ({ error: response.statusText }));
            throw new Error(err.error || response.statusText);
        }
        return response.json();
    },

    async post(url, data) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({ error: response.statusText }));
            throw new Error(err.error || response.statusText);
        }
        return response.json();
    },

    // Drive endpoints
    fetchDrives() {
        return this.get("/api/drives");
    },

    ejectDrive(device) {
        return this.post("/api/drives/eject", { device });
    },

    // Lookup endpoints (Phase 3)
    lookupDisc(device) {
        return this.get(`/api/lookup?device=${encodeURIComponent(device)}`);
    },

    // Rip endpoints (Phase 2)
    startRip(data) {
        return this.post("/api/rip", data);
    },

    getRipStatus() {
        return this.get("/api/rip/status");
    },

    // Settings endpoints (Phase 4)
    getSettings() {
        return this.get("/api/settings");
    },

    saveSettings(data) {
        return this.post("/api/settings", data);
    },

    detectStructure(outputDir) {
        return this.get(`/api/library/detect-structure?dir=${encodeURIComponent(outputDir)}`);
    },
};
