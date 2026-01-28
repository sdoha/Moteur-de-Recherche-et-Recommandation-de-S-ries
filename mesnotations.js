document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("ratingsGrid");
  const emptyMsg = document.getElementById("emptyMsg");

  const render = (items) => {
    if (!items.length) {
      emptyMsg.style.display = "block";
      return;
    }
    const html = items.map(item => `
      <div class="mylist-card">
        <img src="${item.image_url || ''}" alt="${item.name}">
        <div class="card-overlay">
          <h3>${item.name}</h3>
          <p style="color:#fff;font-size:0.95rem;margin-bottom:8px;">
            Ta note : <strong>${item.user_rating}/5</strong>
          </p>
          <p style="color:#ccc;font-size:0.9rem;margin-bottom:14px;">
            Moyenne : ${item.avg_rating ?? '–'}/5
          </p>
          <div class="card-actions">
            <a class="view-btn" href="/series/${item.id}">Voir</a>
          </div>
        </div>
      </div>
    `).join("");
    grid.innerHTML = html;
  };

  try {
    const res = await fetch("/api/my_ratings");
    const data = await res.json();
    if (data.error || !data.results) {
      emptyMsg.textContent = "Impossible de charger vos notations.";
      emptyMsg.style.display = "block";
      return;
    }
    render(data.results);
  } catch (e) {
    console.error(e);
    emptyMsg.textContent = "Erreur réseau.";
    emptyMsg.style.display = "block";
  }
});
