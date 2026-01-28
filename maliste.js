// maliste.js — page Ma Liste : retrait via /api/toggle_list + toasts
document.addEventListener("DOMContentLoaded", () => {
  const removeBtns = document.querySelectorAll(".remove-btn");

  // Modal
  const modal = document.getElementById("confirm-modal");
  const cancelBtn = document.getElementById("cancel-btn");
  const confirmBtn = document.getElementById("confirm-btn");
  let serieToRemove = null;

  // Affiche un toast simple
  const showToast = (message, type = "success") => {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  };

  removeBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      serieToRemove = btn;
      modal.style.display = "flex"; // ouvre modal
    });
  });

  cancelBtn.addEventListener("click", () => {
    serieToRemove = null;
    modal.style.display = "none";
  });

  confirmBtn.addEventListener("click", async () => {
    if (!serieToRemove) return;
    const serieId = serieToRemove.dataset.serie;

    try {
      // Retrait via /api/toggle_list
      const response = await fetch("/api/toggle_list", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ serie_id: serieId })
      });

      const data = await response.json();

      if (!data.success) {
        showToast("Erreur lors du retrait", "error");
        modal.style.display = "none";
        return;
      }

      // Supprime la carte
      const card = serieToRemove.closest(".mylist-card");
      if (card) {
        card.style.opacity = "0";
        setTimeout(() => card.remove(), 300);
      }

      // Toast
      showToast("Série retirée de votre liste", "success");

      // Message si vide
      const grid = document.querySelector(".mylist-grid");
      if (grid && grid.children.length === 1) {
        grid.insertAdjacentHTML(
          "afterend",
          `<p class="empty-msg">✨ Votre liste est vide. Ajoutez vos séries préférées depuis la page détail !</p>`
        );
        grid.remove();
      }

    } catch (err) {
      console.error("Erreur suppression :", err);
      showToast("Erreur serveur", "error");
    }

    modal.style.display = "none";
    serieToRemove = null;
  });
});
