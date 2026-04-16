/**
 * Main application logic.
 * Handles view switching and toast notifications.
 */
const App = {
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
