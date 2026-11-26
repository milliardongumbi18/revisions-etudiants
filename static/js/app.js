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
  
  // « je je je deviendrai » → « je deviendrai » (sauf « nous nous » et « vous vous », qui sont corrects)
  const sansRepetitions = (texte) =>
    texte.replace(/(^|\s)([\p{L}\p{N}'’-]+)(?:\s+\2)+(?=[\s.,;:!?]|$)/giu,
      (tout, debut, mot) => (/^(nous|vous)$/i.test(mot) ? tout : debut + mot));

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
                if (resultat.isFinal) inserer(sansRepetitions(ponctuer(resultat[0].transcript)));
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
/* ==========================================================================
   Étape 12d : la photo de profil part dès qu'elle est choisie
   ========================================================================== */
(() => {
  document.querySelectorAll("[data-avatar-input]").forEach((input) => {
    input.addEventListener("change", () => {
      if (!input.files.length) return;
      const bouton = input.closest("label");
      if (bouton) {
        bouton.setAttribute("aria-busy", "true");
        bouton.firstChild.textContent = "Envoi en cours… ";
      }
      input.form.requestSubmit();
    });
  });
})();

/* ==========================================================================
   Étape 13c : mise en forme des notes par l'IA (sans recharger la page)
   ========================================================================== */
(() => {
  document.querySelectorAll("[data-format-notes]").forEach((barre) => {
    const zone = document.getElementById(barre.dataset.formatNotes);
    const bouton = barre.querySelector("[data-format-btn]");
    const annuler = barre.querySelector("[data-format-undo]");
    const statut = barre.querySelector("[data-format-status]");
    const jeton = zone?.form?.querySelector("input[name=csrfmiddlewaretoken]");
    if (!zone || !bouton || !jeton) return;

    let texteAvant = "";

    bouton.addEventListener("click", async () => {
      const texte = zone.value.trim();
      if (texte.length < 20) {
        statut.textContent = "Écris ou dicte d'abord quelques phrases.";
        return;
      }
      bouton.disabled = true;
      bouton.setAttribute("aria-busy", "true");
      statut.textContent = "Mise en forme en cours…";

      const donnees = new FormData();
      donnees.append("csrfmiddlewaretoken", jeton.value);   // protection CSRF, comme un formulaire
      donnees.append("texte", texte);

      try {
        const reponse = await fetch(barre.dataset.url, { method: "POST", body: donnees, credentials: "same-origin" });
        const json = (reponse.headers.get("content-type") || "").includes("json") ? await reponse.json() : null;
        if (!json) throw new Error("Session expirée : reconnecte-toi.");
        if (!reponse.ok) throw new Error(json.erreur || "La mise en forme a échoué.");

        texteAvant = zone.value;
        zone.value = json.texte;
        annuler.hidden = false;
        statut.textContent = "Texte mis en forme ✓ Relis-le avant d'enregistrer.";
      } catch (erreur) {
        statut.textContent = erreur.message || "Impossible de joindre le serveur. Réessaie.";
      } finally {
        bouton.disabled = false;
        bouton.removeAttribute("aria-busy");
      }
    });

    annuler.addEventListener("click", () => {
      zone.value = texteAvant;
      annuler.hidden = true;
      statut.textContent = "Texte d'origine rétabli.";
    });
  });
})();

/* ==========================================================================
   Vérification avant l'envoi : évite un rechargement (et la perte du fichier choisi)
   Le serveur revérifie TOUJOURS : ceci n'est qu'un confort, pas une sécurité.
   ========================================================================== */
(() => {
  const blocDe = (champ) => champ.closest(".field") || champ.parentElement;

  const montrer = (champ, message) => {
    let erreur = blocDe(champ).querySelector("[data-client-error]");
    if (!erreur) {
      erreur = document.createElement("p");
      erreur.className = "field-error";
      erreur.dataset.clientError = "";
      blocDe(champ).append(erreur);
    }
    erreur.textContent = message;   // textContent : aucun HTML injecté
    champ.setAttribute("aria-invalid", "true");
  };

  const effacer = (champ) => {
    blocDe(champ).querySelector("[data-client-error]")?.remove();
    champ.removeAttribute("aria-invalid");
  };

  const probleme = (champ) => {
    if (champ.type === "file") {
      const fichier = champ.files[0];
      const max = Number(champ.dataset.maxMo || 0);
      if (champ.required && !fichier) return "Choisis un fichier.";
      if (fichier && max && fichier.size > max * 1024 * 1024) return `Fichier trop lourd : ${max} Mo maximum.`;
      return "";
    }
    const rempli = champ.type === "checkbox" ? champ.checked : champ.value.trim() !== "";
    return champ.required && !rempli ? "Ce champ est obligatoire." : "";
  };

  document.querySelectorAll("form[novalidate]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const fautifs = [];
      form.querySelectorAll("input:not([type=hidden]), select, textarea").forEach((champ) => {
        if (champ.disabled) return;
        const message = probleme(champ);
        if (message) { montrer(champ, message); fautifs.push(champ); } else { effacer(champ); }
      });
      if (fautifs.length) {
        event.preventDefault();             // la page ne part pas : le fichier choisi est conservé
        event.stopImmediatePropagation();   // le micro, les confirmations, etc. ne se déclenchent pas
        fautifs[0].focus();
      }
    }, true);   // true = phase de capture : passe AVANT les autres écouteurs du formulaire

    // Le message disparaît dès que l'étudiant corrige
    ["input", "change"].forEach((type) =>
      form.addEventListener(type, (event) => {
        if (event.target.getAttribute?.("aria-invalid") === "true" && !probleme(event.target)) effacer(event.target);
      })
    );
  });
})();

/* ==========================================================================
   Étape 13g : champ grisé quand un autre est rempli
   (ex. l'intitulé d'un créneau devient inutile dès qu'un cours est choisi)
   ========================================================================== */
(() => {
  document.querySelectorAll("[data-off-when]").forEach((champ) => {
    const source = document.getElementById(champ.dataset.offWhen);
    if (!source) return;
    const bloc = champ.closest(".field");
    const mettreAJour = () => {
      const inutile = Boolean(source.value);
      champ.disabled = inutile;   // un champ désactivé n'est pas envoyé ni vérifié
      bloc?.classList.toggle("is-off", inutile);
    };
    source.addEventListener("change", mettreAJour);
    mettreAJour();   // au chargement (ex. modification d'un créneau qui a déjà un cours)
  });
})();

/* ==========================================================================
   Étape 13h : seuls les chapitres du cours choisi sont proposés
   ========================================================================== */
(() => {
  const cours = document.getElementById("id_course");
  const liste = document.getElementById("id_chapters");
  if (!cours || !liste) return;

  const aucun = document.createElement("p");
  aucun.className = "help";
  aucun.textContent = "Choisis d'abord un cours (ou ce cours n'a pas encore de chapitre).";
  liste.after(aucun);

  const filtrer = () => {
    let visibles = 0;
    liste.querySelectorAll("input[data-course]").forEach((caseACocher) => {
      const garder = caseACocher.dataset.course === cours.value;
      caseACocher.closest("div").hidden = !garder;
      if (!garder) caseACocher.checked = false;   // un chapitre d'un autre cours ne part jamais
      visibles += garder;
    });
    liste.hidden = !visibles;
    aucun.hidden = Boolean(visibles);
  };
  cours.addEventListener("change", filtrer);
  filtrer();
})();