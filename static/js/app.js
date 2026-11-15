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

/* ---------- 5. Zone de dépôt de fichier (ajout étape 6a) ---------- */
(() => {
  "use strict";

  document.querySelectorAll("[data-dropzone]").forEach((zone) => {
    const input = zone.querySelector('input[type="file"]');
    const label = zone.querySelector("[data-dropzone-label]");
    if (!input || !label) return;
    const texteInitial = label.textContent;

    // Affiche le nom et la taille du fichier choisi
    const afficher = () => {
      const fichier = input.files[0];
      label.textContent = fichier
        ? `${fichier.name} · ${(fichier.size / 1024 / 1024).toFixed(1)} Mo`
        : texteInitial;
      zone.classList.toggle("has-file", Boolean(fichier));
    };
    input.addEventListener("change", afficher);

    ["dragenter", "dragover"].forEach((type) =>
      zone.addEventListener(type, (event) => {
        event.preventDefault();   // sinon le navigateur ouvre le fichier au lieu de le déposer
        zone.classList.add("is-dragover");
      })
    );
    ["dragleave", "drop"].forEach((type) =>
      zone.addEventListener(type, (event) => {
        event.preventDefault();
        zone.classList.remove("is-dragover");
      })
    );
    zone.addEventListener("drop", (event) => {
      if (event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;   // le fichier déposé devient celui du formulaire
        afficher();
      }
    });
  });
})();

/* ---------- 6. Confirmation de déconnexion ---------- */
(() => {
  "use strict";

  const form = document.querySelector("form[data-confirm-logout]");
  const dialog = document.getElementById("logout-dialog");
  // Navigateur trop ancien pour <dialog> : on garde la déconnexion directe
  if (!form || !dialog || typeof dialog.showModal !== "function") return;

  let confirme = false;

  form.addEventListener("submit", (event) => {
    if (confirme) return;            // 2e passage : on laisse partir le formulaire
    event.preventDefault();
    dialog.showModal();
  });

  dialog.querySelector("[data-modal-close]").addEventListener("click", () => dialog.close());

  dialog.querySelector("[data-modal-confirm]").addEventListener("click", () => {
    confirme = true;
    dialog.close();
    form.requestSubmit();            // envoie le formulaire (avec son jeton CSRF)
  });

  // Clic sur le fond flouté = annuler (Échap ferme déjà la fenêtre nativement)
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
})();

/* ---------- 7. Dictée vocale (ajout étape 6c) ---------- */
(() => {
  "use strict";

  // Chrome / Edge : webkitSpeechRecognition ; standard : SpeechRecognition ; Firefox : rien
  const Reconnaissance = window.SpeechRecognition || window.webkitSpeechRecognition;

  const MESSAGES_ERREUR = {
    "not-allowed": "Accès au micro refusé : autorise-le dans les réglages du navigateur (icône à gauche de l'adresse).",
    "service-not-allowed": "Accès au micro refusé : autorise-le dans les réglages du navigateur.",
    "audio-capture": "Aucun micro détecté sur cet appareil.",
    "network": "La dictée a besoin d'une connexion internet.",
  };

  // Commandes vocales → ponctuation (« point » seul est ignoré : trop d'ambiguïté, ex. « point de vue »)
  const ponctuer = (texte) =>
    texte
      .replace(/\s*point à la ligne\s*/gi, ".\n")
      .replace(/\s*nouveau paragraphe\s*/gi, "\n\n")
      .replace(/\s*à la ligne\s*/gi, "\n")
      .replace(/\s*point d'interrogation/gi, " ?")
      .replace(/\s*point d'exclamation/gi, " !")
      .replace(/\s*virgule/gi, ",");

  document.querySelectorAll("[data-dictation]").forEach((barre) => {
    const zone = document.getElementById(barre.dataset.dictation);
    const bouton = barre.querySelector("[data-dictation-toggle]");
    const libelle = barre.querySelector("[data-dictation-label]");
    const statut = barre.querySelector("[data-dictation-status]");
    if (!Reconnaissance || !zone || !bouton) return;   // non pris en charge : la barre reste cachée
    barre.hidden = false;

    const reco = new Reconnaissance();
    reco.lang = "fr-FR";
    reco.continuous = true;        // ne s'arrête pas à la première phrase
    reco.interimResults = true;    // aperçu pendant qu'on parle

    let enEcoute = false;
    let veutContinuer = false;     // Chrome coupe seul après un silence : on relance si l'utilisateur n'a pas arrêté
    let erreur = "";

    const afficherEtat = (actif) => {
      enEcoute = actif;
      bouton.classList.toggle("is-listening", actif);
      bouton.setAttribute("aria-pressed", String(actif));
      libelle.textContent = actif ? "Arrêter" : "Dicter";
    };

    // Insère le texte à la position du curseur (ou à la fin)
    const inserer = (texte) => {
      const debut = zone.selectionStart ?? zone.value.length;
      const fin = zone.selectionEnd ?? zone.value.length;
      const avant = zone.value.slice(0, debut);
      const apres = zone.value.slice(fin);
      texte = texte.replace(/^ +/, "");
      const espace = avant && !/\s$/.test(avant) && !/^[\n,.?!]/.test(texte) ? " " : "";
      const morceau = espace + texte;
      zone.value = avant + morceau + apres;
      const position = avant.length + morceau.length;
      zone.setSelectionRange(position, position);
    };

    reco.addEventListener("result", (event) => {
      let apercu = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const resultat = event.results[i];
        if (resultat.isFinal) inserer(ponctuer(resultat[0].transcript));
        else apercu += resultat[0].transcript;
      }
      statut.textContent = apercu ? `… ${apercu}` : "Je t'écoute…";
    });

    reco.addEventListener("error", (event) => {
      if (event.error === "no-speech" || event.error === "aborted") return;   // silence : relance via "end"
      veutContinuer = false;
      erreur = MESSAGES_ERREUR[event.error] || "La dictée s'est arrêtée. Réessaie.";
    });

    reco.addEventListener("end", () => {
      if (veutContinuer) {
        try { reco.start(); return; } catch { /* déjà relancée */ }
      }
      afficherEtat(false);
      statut.textContent = erreur;   // garde le message d'erreur visible, sinon efface
      erreur = "";
    });

    bouton.addEventListener("click", () => {
      if (enEcoute) {
        veutContinuer = false;
        reco.stop();
        return;
      }
      veutContinuer = true;
      erreur = "";
      try {
        reco.start();
        afficherEtat(true);
        statut.textContent = "Je t'écoute…";
        zone.focus();
      } catch { /* un démarrage est déjà en cours */ }
    });

    // On coupe le micro quand on enregistre le formulaire
    zone.form?.addEventListener("submit", () => {
      veutContinuer = false;
      reco.stop();
    });
  });
})();