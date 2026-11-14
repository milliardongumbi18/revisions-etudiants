/* Révisions Étudiants — interactions de l'interface
   1. Bouton thème clair / sombre (transition circulaire)
   2. Apparition des sections au défilement
   3. Disparition automatique des messages de succès
*/
(() => {
  "use strict";

  const root = document.documentElement;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

  /* ---------- 1. Thème ---------- */
  const toggle = document.getElementById("theme-toggle");

  const currentTheme = () => (root.dataset.theme === "dark" ? "dark" : "light");

  // Met à jour le texte lu par les lecteurs d'écran
  const syncButton = () => {
    if (!toggle) return;
    const dark = currentTheme() === "dark";
    toggle.setAttribute("aria-pressed", String(dark));
    toggle.setAttribute("aria-label", dark ? "Activer le thème clair" : "Activer le thème sombre");
  };

  const savedTheme = () => {
    try { return localStorage.getItem("theme"); } catch { return null; }
  };

  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch { /* stockage indisponible : pas grave */ }
    syncButton();
  };

  syncButton();

  toggle?.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";

    // Navigateur sans View Transitions, ou animations réduites : changement direct
    if (!document.startViewTransition || reduceMotion.matches) {
      applyTheme(next);
      return;
    }

    // Le cercle part du centre du bouton et grandit jusqu'au coin le plus éloigné
    const rect = toggle.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

    root.classList.add("theme-switching");
    const transition = document.startViewTransition(() => applyTheme(next));

    transition.ready
      .then(() => {
        root.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 650, easing: "cubic-bezier(.2, .8, .2, 1)", pseudoElement: "::view-transition-new(root)" }
        );
      })
      .catch(() => {});

    const cleanup = () => root.classList.remove("theme-switching");
    transition.finished.then(cleanup, cleanup);
  });

  // Si l'utilisateur n'a jamais choisi, on suit les changements du système
  systemDark.addEventListener("change", (event) => {
    if (savedTheme()) return;
    root.dataset.theme = event.matches ? "dark" : "light";
    syncButton();
  });

  /* ---------- 2. Apparition au défilement ---------- */
  const targets = document.querySelectorAll("[data-reveal]");

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target); // une seule fois
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );
    targets.forEach((el) => observer.observe(el));
  } else {
    targets.forEach((el) => el.classList.add("is-visible"));
  }

  /* ---------- 3. Messages ---------- */
  // Les succès disparaissent seuls ; les erreurs restent jusqu'au prochain écran.
  document.querySelectorAll(".toast:not(.error)").forEach((toast) => {
    setTimeout(() => {
      toast.classList.add("is-leaving");
      toast.addEventListener("animationend", () => toast.remove(), { once: true });
    }, 6000);
  });
})();