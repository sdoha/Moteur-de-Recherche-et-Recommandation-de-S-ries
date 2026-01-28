document.addEventListener("DOMContentLoaded", () => {
  const listBtn = document.getElementById("listBtn");
  const ratingBox = document.getElementById("rating");
  const similarContainer = document.getElementById("similarContainer");
  const synopsis = document.getElementById("synopsis");
  const expandHint = document.getElementById("expandSynopsis");

  const serieId =
    document.body?.dataset?.serieId ||
    listBtn?.dataset?.serieId ||
    similarContainer?.dataset?.serieId ||
    null;

  const serieName =
    listBtn?.dataset?.serieName ||
    ratingBox?.dataset?.serieName ||
    null;

  const getAll = (selector) => Array.from(document.querySelectorAll(selector));

  // Affiche un toast léger
  function showToast(message, type = "success") {
    const host =
      document.getElementById("toast-container") ||
      (() => {
        const elt = document.createElement("div");
        elt.id = "toast-container";
        document.body.appendChild(elt);
        return elt;
      })();

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    host.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  // Met à jour l'état du bouton liste
  function setListButton(inList) {
    if (!listBtn) {
      return;
    }
    listBtn.classList.toggle("in-list", inList);
    listBtn.innerHTML = inList
      ? '<span class="icon">✓</span><span class="label">Dans ma liste</span>'
      : '<span class="icon">+</span><span class="label">Ajouter à ma liste</span>';
  }

  // Notes : envoie /api/rate
  if (ratingBox && serieName) {
    const stars = getAll(".star-btn");
    const initial = parseInt(ratingBox.dataset.userRating || "0", 10);

    const paint = (upto) => {
      stars.forEach((star) => {
        const value = parseInt(star.dataset.value || "0", 10);
        star.classList.toggle("active", value <= upto);
      });
    };

    if (initial > 0) {
      paint(initial);
    }

    stars.forEach((star) => {
      star.addEventListener("click", async () => {
        const rating = parseInt(star.dataset.value || "0", 10);
        try {
          const res = await fetch("/api/rate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ serie_name: serieName, rating }),
          });
          const data = await res.json();
          if (!data.success) {
            const message = data.error || "Erreur lors de la notation.";
            if (message.toLowerCase().includes("connect")) {
              window.location.href = "/login";
              return;
            }
            showToast(message, "error");
            return;
          }
          paint(rating);
          showToast("Votre note a bien été enregistrée !", "warning");
        } catch (err) {
          console.error("rating error:", err);
          showToast("Erreur serveur.", "error");
        }
      });
    });
  }

  // Ma liste : ajoute/retire via /api/toggle_list
  if (listBtn && serieId && serieName) {
    listBtn.addEventListener("click", async () => {
      listBtn.disabled = true;
      try {
        const res = await fetch("/api/toggle_list", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ serie_id: serieId }),
        });
        const data = await res.json();
        if (!data.success) {
          const message = data.error || "Erreur inconnue.";
          if (message.toLowerCase().includes("connect")) {
            window.location.href = "/login";
            return;
          }
          showToast(message, "error");
          return;
        }

        const inList = data.action === "added";
        setListButton(inList);
        showToast(
          inList ? "Ajoutée à votre liste !" : "Série retirée de votre liste",
          inList ? "success" : "error"
        );
      } catch (err) {
        console.error("toggle list error:", err);
        showToast("Erreur serveur.", "error");
      } finally {
        listBtn.disabled = false;
      }
    });
  }

  if (synopsis) {
    const synopsisText = (synopsis.textContent || "").trim();
    if (!expandHint || synopsisText.length <= 220) {
      expandHint?.remove();
      synopsis.parentElement?.classList.add("short");
    } else {
      expandHint.textContent = "Voir plus";
      expandHint.addEventListener("click", () => {
        const expanded = synopsis.parentElement.classList.toggle("expanded");
        expandHint.textContent = expanded ? "Voir moins" : "Voir plus";
      });
    }
  }

  async function loadSimilar() {
    if (!similarContainer || !serieId) {
      return;
    }

    similarContainer.innerHTML = '<p class="loading-similar">Chargement…</p>';

    try {
      // Similaires : appelle /api/similar/<id>
      const response = await fetch(`/api/similar/${serieId}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      const items = Array.isArray(payload.results) ? payload.results : [];

      if (!items.length) {
        similarContainer.innerHTML =
          '<p class="no-similar">Aucune série similaire trouvée.</p>';
        return;
      }

      similarContainer.innerHTML = items
        .map(
          (item) => `
            <a class="series-card fade-in" href="/series/${item.id}">
              <img src="${item.image_url || "/static/images/default_poster.jpg"}" alt="${item.name}">
              <div class="series-overlay">
                <h3 class="series-name">${item.name}</h3>
              </div>
            </a>`
        )
        .join("");
    } catch (err) {
      console.error("similar fetch failed:", err);
      similarContainer.innerHTML =
        '<p class="no-similar">Erreur de chargement des séries similaires.</p>';
    }
  }

  loadSimilar();
});
