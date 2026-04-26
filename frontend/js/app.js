/**
 * Main application logic.
 * Handles view switching and toast notifications.
 */
const App = {
    // Track current view
    currentView: "drives",

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
        restoreRipState() {
            if (this.isRipping && this.ripStatus) {
                RipView.resumePolling(this.ripStatus);
            } else {
                RipView.render();
            }
        }
    },

    init() {
        // Set up nav buttons
        document.querySelectorAll(".nav-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                this.switchView(btn.dataset.view);
            });
        });

        // Load initial view
        DrivesView.render();
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
