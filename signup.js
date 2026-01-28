// signup.js — page d'inscription : POST JSON vers /api/signup puis redirection
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("signupForm");
  const errorsBox = document.createElement("div");
  errorsBox.className = "errors";
  errorsBox.style.display = "none";

  if (form && !form.nextElementSibling?.classList.contains("errors")) {
    form.insertAdjacentElement("afterend", errorsBox);
  }

  async function showError(message) {
    if (!errorsBox) return;
    errorsBox.innerText = message;
    errorsBox.style.display = "block";
  }

  if (!form) return;

  // Envoie le formulaire en JSON vers /api/signup
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries());

    try {
      const res = await fetch("/api/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const json = await res.json();
      if (!json.success) {
        showError(json.error || "Erreur lors de l'inscription.");
        return;
      }

      // Succès : on redirige vers l'accueil (utilisateur déjà logué côté API)
      window.location.href = "/";
    } catch (err) {
      console.error("signup error:", err);
      showError("Erreur réseau. Réessaie plus tard.");
    }
  });
});
