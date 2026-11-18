"""
Contenu du compte de démonstration (rédigé à la main, sans IA).
Les indices de cours dans CRENEAUX et EXAMENS renvoient à la liste COURS.
"""


def qcm(question, choix, bonne, explication):
    return {"type": "qcm", "question": question, "choix": choix, "bonne": bonne, "explication": explication}


def courte(question, attendue, explication):
    return {"type": "courte", "question": question, "attendue": attendue, "explication": explication}


COURS = [
    {
        "titre": "Algorithmique et structures de données",
        "description": "Analyse de la complexité et structures de données fondamentales.",
        "plan": "Complexité des algorithmes\nStructures linéaires\nArbres et graphes\nTris avancés",
        "couleur": "indigo",
        "chapitres": [
            {
                "titre": "Complexité des algorithmes",
                "notes": (
                    "La complexité mesure la quantité de ressources (temps ou mémoire) qu'un algorithme consomme "
                    "en fonction de la taille n de ses données. On l'exprime avec la notation O (« grand O »), qui "
                    "décrit le comportement dans le pire des cas quand n devient grand, en ignorant les constantes.\n\n"
                    "Complexités courantes, de la meilleure à la pire : O(1) constante (accéder à une case d'un "
                    "tableau), O(log n) logarithmique (recherche dichotomique), O(n) linéaire (parcourir un tableau), "
                    "O(n log n) (tri fusion), O(n²) quadratique (deux boucles imbriquées, tri à bulles), O(2^n) "
                    "exponentielle.\n\n"
                    "La recherche dichotomique ne fonctionne que sur un tableau trié : à chaque étape, on compare "
                    "l'élément cherché à celui du milieu et on élimine la moitié du tableau. Pour un million "
                    "d'éléments, une vingtaine de comparaisons suffisent, contre un million pour une recherche "
                    "séquentielle.\n\n"
                    "Le tri à bulles compare les éléments voisins et les échange s'ils sont mal placés : O(n²) dans "
                    "le pire des cas. Le tri fusion découpe le tableau en deux, trie chaque moitié récursivement puis "
                    "fusionne les deux moitiés triées : O(n log n) dans tous les cas, au prix d'une mémoire "
                    "supplémentaire."
                ),
                "questions": [
                    qcm("Quelle est la complexité de la recherche dichotomique dans un tableau trié de n éléments ?",
                        ["O(n)", "O(log n)", "O(n log n)", "O(1)"], 1,
                        "Chaque comparaison élimine la moitié des éléments restants : environ log₂(n) étapes."),
                    qcm("Quelle est la complexité du tri fusion dans le pire des cas ?",
                        ["O(n²)", "O(n)", "O(n log n)", "O(log n)"], 2,
                        "log n niveaux de découpage, et une fusion en O(n) à chaque niveau."),
                    qcm("Quelle condition la recherche dichotomique exige-t-elle ?",
                        ["Un tableau trié", "Un tableau de taille paire", "Des éléments tous différents",
                         "Une liste chaînée"], 0,
                        "Sans tri, comparer au milieu ne dit pas de quel côté chercher."),
                    qcm("Quelle est la complexité du tri à bulles dans le pire des cas ?",
                        ["O(n log n)", "O(n²)", "O(n)", "O(2^n)"], 1,
                        "Jusqu'à n passages, chacun comparant jusqu'à n paires de voisins."),
                    courte("Que signifie la notation O(n²) ?",
                           "Le temps d'exécution croît au plus comme le carré de la taille de l'entrée : doubler n "
                           "multiplie le temps par environ quatre (typiquement deux boucles imbriquées).",
                           "La notation O décrit la croissance dans le pire des cas, sans les constantes."),
                ],
            },
            {
                "titre": "Piles, files et listes chaînées",
                "notes": (
                    "Une pile (stack) fonctionne selon le principe LIFO : dernier entré, premier sorti. Opérations : "
                    "empiler (push) ajoute au sommet, dépiler (pop) retire le sommet, toutes deux en O(1). Exemples : "
                    "le bouton « Retour » d'un navigateur, l'annulation (Ctrl+Z), la pile d'appels des fonctions "
                    "récursives.\n\n"
                    "Une file (queue) fonctionne selon le principe FIFO : premier entré, premier sorti. On enfile à la "
                    "fin et on défile au début. Exemples : la file d'attente d'impression, le traitement des requêtes "
                    "d'un serveur.\n\n"
                    "Une liste chaînée est une suite de nœuds ; chaque nœud contient une valeur et un pointeur vers le "
                    "nœud suivant. Le dernier nœud pointe vers rien (NULL). Insérer ou supprimer en tête coûte O(1) : "
                    "on crée un nœud qui pointe vers l'ancienne tête. En revanche, accéder au k-ième élément oblige à "
                    "parcourir les k premiers nœuds : O(k), contre O(1) pour un tableau. Une liste doublement chaînée "
                    "ajoute un pointeur vers le nœud précédent pour parcourir dans les deux sens."
                ),
                "questions": [
                    qcm("Quelle structure suit le principe LIFO (dernier entré, premier sorti) ?",
                        ["La file", "La pile", "Le tableau trié", "L'arbre binaire"], 1,
                        "On retire toujours l'élément ajouté en dernier, au sommet de la pile."),
                    qcm("Le bouton « Retour » d'un navigateur s'implémente naturellement avec…",
                        ["une file", "une pile", "une table de hachage", "un tas"], 1,
                        "La dernière page visitée est la première à laquelle on revient."),
                    qcm("Quel est le coût d'accès au k-ième élément d'une liste simplement chaînée ?",
                        ["O(1)", "O(log n)", "O(k)", "O(k²)"], 2,
                        "Il faut suivre les pointeurs depuis la tête, nœud par nœud."),
                    courte("Quelle est la différence entre une pile et une file ?",
                           "La pile retire le dernier élément ajouté (LIFO) ; la file retire le premier élément "
                           "ajouté (FIFO).",
                           "Pile = pile d'assiettes ; file = file d'attente."),
                    courte("Quel est le coût d'une insertion en tête de liste chaînée, et pourquoi ?",
                           "O(1) : on crée un nœud dont le pointeur vise l'ancienne tête, puis il devient la tête, "
                           "sans parcourir la liste.",
                           "Aucun décalage d'éléments, contrairement à une insertion au début d'un tableau."),
                ],
            },
        ],
    },
    {
        "titre": "Bases de données relationnelles",
        "description": "Modèle relationnel, conception et langage SQL.",
        "plan": "Modèle relationnel\nClés et intégrité\nRequêtes SQL\nNormalisation",
        "couleur": "turquoise",
        "chapitres": [
            {
                "titre": "Modèle relationnel et clés",
                "notes": (
                    "Le modèle relationnel, proposé par Edgar F. Codd en 1970, organise les données en relations "
                    "(tables). Chaque relation a des attributs (colonnes), et chaque ligne est un tuple (ou n-uplet). "
                    "Le domaine d'un attribut est l'ensemble des valeurs qu'il peut prendre.\n\n"
                    "La clé primaire identifie chaque ligne de façon unique : ses valeurs doivent être uniques et "
                    "jamais nulles. Elle peut être composée de plusieurs colonnes (clé composite).\n\n"
                    "Une clé étrangère est une colonne qui fait référence à la clé primaire d'une autre table, par "
                    "exemple inscription.etudiant_id qui référence etudiant.id. L'intégrité référentielle impose que "
                    "toute valeur de clé étrangère corresponde à une clé primaire existante (ou soit NULL si c'est "
                    "autorisé) : on ne peut pas inscrire un étudiant qui n'existe pas.\n\n"
                    "Une association plusieurs-à-plusieurs (un étudiant suit plusieurs cours, un cours a plusieurs "
                    "étudiants) se traduit par une table d'association contenant deux clés étrangères, par exemple "
                    "inscription(etudiant_id, cours_id)."
                ),
                "questions": [
                    qcm("Une clé primaire doit être…",
                        ["unique et non nulle", "obligatoirement numérique", "auto-incrémentée",
                         "composée d'une seule colonne"], 0,
                        "Elle identifie chaque ligne : deux lignes ne peuvent pas partager la même valeur."),
                    qcm("À quoi sert une clé étrangère ?",
                        ["À accélérer toutes les requêtes", "À référencer la clé primaire d'une autre table",
                         "À chiffrer une colonne", "À trier les résultats"], 1,
                        "Elle crée le lien entre deux tables et permet l'intégrité référentielle."),
                    qcm("Dans le modèle relationnel, une ligne d'une table s'appelle aussi…",
                        ["un attribut", "un domaine", "un tuple (n-uplet)", "un schéma"], 2,
                        "Les colonnes sont les attributs ; les lignes sont les tuples."),
                    qcm("Comment traduire l'association plusieurs-à-plusieurs entre ÉTUDIANT et COURS ?",
                        ["Une colonne cours_id dans ÉTUDIANT", "Une table d'association avec deux clés étrangères",
                         "Deux clés primaires dans COURS", "Une vue SQL"], 1,
                        "Par exemple inscription(etudiant_id, cours_id)."),
                    courte("Qu'est-ce que l'intégrité référentielle ?",
                           "La règle qui impose que toute valeur de clé étrangère corresponde à une clé primaire "
                           "existante dans la table référencée (ou soit NULL si c'est permis).",
                           "La base refuse par exemple une inscription pour un étudiant inexistant."),
                ],
            },
            {
                "titre": "Requêtes SQL : sélection, jointures et agrégats",
                "notes": (
                    "SELECT choisit les colonnes, FROM indique la table, WHERE filtre les lignes avant tout "
                    "regroupement, ORDER BY trie le résultat.\n\n"
                    "Les fonctions d'agrégat (COUNT, SUM, AVG, MIN, MAX) résument plusieurs lignes en une valeur. "
                    "GROUP BY regroupe les lignes qui partagent une même valeur, et HAVING filtre ces groupes après le "
                    "regroupement. Exemple : SELECT promotion, COUNT(*) FROM etudiant GROUP BY promotion HAVING "
                    "COUNT(*) > 30; COUNT(*) sur une table vide renvoie 0.\n\n"
                    "Une jointure combine plusieurs tables. INNER JOIN ne garde que les lignes qui ont une "
                    "correspondance dans les deux tables ; LEFT JOIN garde toutes les lignes de la table de gauche, "
                    "avec des NULL quand il n'y a pas de correspondance.\n\n"
                    "Sécurité : ne jamais construire une requête en concaténant des saisies d'utilisateurs. Avec des "
                    "requêtes paramétrées, les valeurs sont envoyées séparément de la requête et ne peuvent pas être "
                    "interprétées comme du code SQL : c'est la protection contre l'injection SQL. L'ORM de Django les "
                    "utilise automatiquement."
                ),
                "questions": [
                    qcm("Quelle clause filtre les groupes après un GROUP BY ?",
                        ["WHERE", "HAVING", "ORDER BY", "LIMIT"], 1,
                        "WHERE filtre les lignes avant le regroupement ; HAVING filtre les groupes après."),
                    qcm("Que renvoie un INNER JOIN ?",
                        ["Toutes les lignes de la table de gauche",
                         "Les lignes qui ont une correspondance dans les deux tables",
                         "Le produit cartésien des deux tables", "Les lignes sans correspondance"], 1,
                        "Pour garder aussi les lignes sans correspondance, on utilise LEFT JOIN."),
                    qcm("Que renvoie COUNT(*) sur une table vide ?",
                        ["NULL", "0", "Une erreur", "1"], 1,
                        "COUNT compte les lignes : zéro ligne donne 0 (SUM, lui, renverrait NULL)."),
                    courte("Écris la requête qui donne le nombre d'étudiants par promotion (table etudiant, "
                           "colonne promotion).",
                           "SELECT promotion, COUNT(*) FROM etudiant GROUP BY promotion;",
                           "GROUP BY crée un groupe par promotion ; COUNT(*) compte les lignes de chaque groupe."),
                    courte("Pourquoi utiliser des requêtes paramétrées plutôt que de concaténer les saisies ?",
                           "Pour empêcher l'injection SQL : les valeurs sont transmises séparément et ne sont jamais "
                           "exécutées comme du code SQL.",
                           "Une saisie comme ' OR '1'='1 ne peut plus modifier la requête."),
                ],
            },
        ],
    },
    {
        "titre": "Économie politique",
        "description": "Fonctionnement des marchés et grands équilibres macroéconomiques.",
        "plan": "Offre et demande\nInflation et monnaie\nCroissance\nCommerce international",
        "couleur": "mangue",
        "chapitres": [
            {
                "titre": "Offre, demande et prix d'équilibre",
                "notes": (
                    "La demande est la quantité d'un bien que les acheteurs souhaitent acquérir à chaque prix. Selon "
                    "la loi de la demande, quand le prix augmente, la quantité demandée diminue (toutes choses égales "
                    "par ailleurs). L'offre est la quantité que les producteurs souhaitent vendre à chaque prix ; elle "
                    "augmente généralement avec le prix.\n\n"
                    "Le prix d'équilibre est le prix pour lequel la quantité offerte est égale à la quantité demandée. "
                    "Si le prix est au-dessus de l'équilibre, il y a un excédent d'offre (des invendus) et le prix "
                    "tend à baisser ; s'il est en dessous, il y a une pénurie et le prix tend à monter.\n\n"
                    "Une variation du prix du bien provoque un mouvement le long de la courbe. Un changement d'un "
                    "autre facteur déplace la courbe entière : une hausse du revenu déplace la demande d'un bien "
                    "normal vers la droite ; une mauvaise récolte (sécheresse, maladie des plantes) déplace l'offre "
                    "vers la gauche, ce qui fait monter le prix d'équilibre, par exemple celui du manioc sur les "
                    "marchés de Kinshasa."
                ),
                "questions": [
                    qcm("Que se passe-t-il si le prix est supérieur au prix d'équilibre ?",
                        ["Une pénurie", "Un excédent d'offre", "La demande augmente", "Rien ne change"], 1,
                        "Les producteurs veulent vendre plus que ce que les acheteurs veulent acheter."),
                    qcm("Que dit la loi de la demande ?",
                        ["Quand le prix monte, la quantité demandée baisse",
                         "Quand le prix monte, la quantité demandée monte",
                         "La demande ne dépend jamais du prix", "L'offre crée toujours sa propre demande"], 0,
                        "Toutes choses égales par ailleurs, un bien plus cher est moins acheté."),
                    qcm("Pour un bien normal, une hausse du revenu des ménages…",
                        ["déplace la courbe de demande vers la droite", "déplace la courbe d'offre vers la gauche",
                         "provoque un mouvement le long de la courbe d'offre", "n'a aucun effet"], 0,
                        "À chaque prix, les ménages veulent acheter davantage."),
                    qcm("Une sécheresse réduit fortement la récolte de manioc. Conséquence probable ?",
                        ["L'offre se déplace vers la gauche et le prix monte",
                         "La demande se déplace vers la droite",
                         "L'offre se déplace vers la droite et le prix baisse", "Aucun effet sur le prix"], 0,
                        "Moins de manioc est disponible à chaque prix : le prix d'équilibre augmente."),
                    courte("Définis le prix d'équilibre.",
                           "Le prix pour lequel la quantité offerte est égale à la quantité demandée.",
                           "À ce prix, il n'y a ni invendus ni pénurie."),
                ],
            },
            {
                "titre": "Inflation et politique monétaire",
                "revise": False,   # jamais révisé : ces questions apparaissent comme « nouvelles » aujourd'hui
                "notes": (
                    "L'inflation est une hausse générale et durable du niveau des prix. Elle réduit le pouvoir "
                    "d'achat : avec la même somme, on achète moins de biens. On la mesure surtout avec l'indice des "
                    "prix à la consommation (IPC), qui suit le prix d'un panier de biens et services représentatif "
                    "des dépenses des ménages.\n\n"
                    "On distingue plusieurs causes. L'inflation par la demande apparaît quand la demande globale "
                    "dépasse ce que l'économie peut produire. L'inflation par les coûts vient de la hausse des coûts "
                    "de production (carburant, matières premières, salaires), répercutée sur les prix de vente. "
                    "L'inflation importée survient quand les produits achetés à l'étranger deviennent plus chers, par "
                    "exemple lorsque la monnaie nationale se déprécie : il faut alors plus de francs congolais pour "
                    "payer les mêmes importations.\n\n"
                    "La banque centrale (en RDC, la Banque centrale du Congo) lutte contre l'inflation par la "
                    "politique monétaire. En relevant son taux directeur, elle rend le crédit plus cher : les ménages "
                    "et les entreprises empruntent et dépensent moins, ce qui freine la hausse des prix. Créer "
                    "massivement de la monnaie a l'effet inverse et alimente l'inflation."
                ),
                "questions": [
                    qcm("Qu'est-ce que l'inflation ?",
                        ["Une hausse générale et durable du niveau des prix", "La hausse du prix d'un seul bien",
                         "Une baisse générale des prix", "Une hausse des salaires"], 0,
                        "Elle touche l'ensemble des prix, et sur la durée."),
                    qcm("Quel indicateur sert principalement à mesurer l'inflation ?",
                        ["Le PIB", "L'indice des prix à la consommation (IPC)", "La balance commerciale",
                         "Le taux de chômage"], 1,
                        "L'IPC suit le prix d'un panier représentatif des dépenses des ménages."),
                    qcm("Pour freiner l'inflation, la banque centrale peut…",
                        ["baisser son taux directeur", "relever son taux directeur",
                         "créer davantage de monnaie", "supprimer les impôts"], 1,
                        "Un crédit plus cher réduit la demande, donc la pression sur les prix."),
                    courte("Pourquoi une dépréciation du franc congolais peut-elle alimenter l'inflation ?",
                           "Les importations coûtent plus de francs congolais, ce qui fait monter les prix intérieurs "
                           "des produits importés et de ceux qui en dépendent (inflation importée).",
                           "La RDC importe une grande partie de ses biens de consommation."),
                    courte("Qu'est-ce que l'inflation par les coûts ?",
                           "Une hausse des prix provoquée par l'augmentation des coûts de production (carburant, "
                           "matières premières, salaires) que les entreprises répercutent sur leurs prix.",
                           "Elle se distingue de l'inflation par la demande."),
                ],
            },
        ],
    },
]

# (indice du cours ou None, intitulé si pas de cours, jour 0=lundi, début, fin)
CRENEAUX = [
    (0, "", 0, "08:00", "12:00"),
    (1, "", 1, "08:00", "10:00"),
    (2, "", 2, "13:00", "17:00"),
    (1, "", 3, "08:00", "12:00"),
    (None, "Anglais technique", 4, "10:00", "12:00"),
    (0, "", 5, "08:00", "10:00"),
]

# (indice du cours, dans combien de jours, intitulé)
EXAMENS = [
    (0, 6, "Interrogation"),
    (1, 15, "Examen final"),
    (2, 24, "Examen final"),
]