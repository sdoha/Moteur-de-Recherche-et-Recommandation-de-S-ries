// login.js — page de connexion : splash + POST JSON vers /api/login
const splash = document.getElementById("splash");
const loginWrap = document.getElementById("loginWrap");

const SPLASH_TIME = 2500;
window.addEventListener("load", () => {
  setTimeout(() => {
    splash.classList.add("hide");
    setTimeout(() => {
      splash.style.display = "none";
      loginWrap.classList.add("visible");
      document.getElementById("username").focus();
    }, 500);
  }, SPLASH_TIME);
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && splash && !splash.classList.contains("hide")) {
    splash.classList.add("hide");
    setTimeout(() => {
      splash.style.display = "none";
      loginWrap.classList.add("visible");
      document.getElementById("username").focus();
    }, 300);
  }
});

// Envoie le formulaire en JSON vers /api/login
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("loginForm");
  const errorsBox = document.getElementById("loginErrors");

  const showError = (message) => {
    if (!errorsBox) return;
    errorsBox.style.display = "block";
    errorsBox.innerText = message;
  };

  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries());

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!json.success) {
        showError(json.error || "Nom d'utilisateur ou mot de passe incorrect.");
        return;
      }
      window.location.href = "/";
    } catch (err) {
      console.error("login error:", err);
      showError("Erreur réseau. Réessaie plus tard.");
    }
  });
});
