# Job Watch — veille quotidienne des offres data, 100% gratuit

Architecture : **GitHub Actions** exécute le script tous les jours dans le
cloud (gratuit, ne dépend ni de ton PC ni de ton téléphone) → il compare
avec la veille → s'il y a du nouveau, il t'envoie une **notification push**
via **ntfy.sh** (gratuit, appli Android) → tu peux aussi déclencher un
check manuel à tout moment depuis l'appli GitHub mobile.

---

## Étape 1 — Créer un compte GitHub

1. Va sur https://github.com/signup et crée un compte (gratuit).
2. Une fois connecté, clique sur le "+" en haut à droite → "New repository".
3. Nom du repo : `job-watch` (ou ce que tu veux).
4. Mets-le en **Private** (recommandé, même si le contenu n'est pas sensible).
5. Clique "Create repository".

## Étape 2 — Ajouter les fichiers

Dans ton nouveau repo (vide), utilise le bouton "uploading an existing
file" (ou "Add file" → "Upload files") et dépose ces 4 fichiers en
respectant la structure de dossiers :

```
job-watch/
├── job_watch.py
├── companies.json
└── .github/
    └── workflows/
        └── daily.yml
```

⚠️ Point d'attention : l'interface web de GitHub permet de recréer les
sous-dossiers en tapant `.github/workflows/daily.yml` comme nom de fichier
au moment de l'upload — pas besoin de les créer à part.

## Étape 3 — Installer l'appli ntfy sur ton téléphone

1. Installe l'appli **ntfy** depuis le Play Store (gratuite, open-source).
2. Ouvre l'appli, appuie sur "+" pour t'abonner à un topic.
3. Choisis un nom de topic **unique et difficile à deviner** (n'importe
   qui connaissant ce nom peut voir tes notifications, il n'y a pas de
   compte/mot de passe sur ntfy.sh) — par exemple `lionel-jw-8f2k1q`.
4. Abonne-toi à ce topic dans l'appli.

## Étape 4 — Configurer le secret dans GitHub

1. Dans ton repo GitHub → Settings → Secrets and variables → Actions.
2. "New repository secret".
3. Nom : `NTFY_TOPIC`, valeur : le topic choisi à l'étape 3 (ex.
   `lionel-jw-8f2k1q`).
4. Enregistrer.

## Étape 5 — Vérifier que ça tourne

1. Dans ton repo → onglet "Actions".
2. Tu devrois voir le workflow "Job Watch". Clique dessus.
3. Bouton "Run workflow" (à droite) → lance un premier essai manuel.
4. Regarde les logs : ça doit dire "Aucune nouvelle offre aujourd'hui"
   (normal, c'est la toute première exécution, il n'y a pas encore de
   "veille" à comparer).
5. Ensuite, ça tournera automatiquement tous les jours à 8h (heure de
   Paris environ) — et tu peux aussi relancer un check manuel à tout
   moment depuis l'appli **GitHub** sur ton téléphone (Play Store) :
   ouvre ton repo → Actions → Job Watch → Run workflow.

---

## Compléter `companies.json`

C'est le seul fichier que tu dois modifier pour ajouter/retirer des
sociétés. Chaque entrée ressemble à ça :

```json
{
  "name": "Nom de la société",
  "type": "greenhouse",
  "token": "identifiant-de-la-societe"
}
```

Pour trouver le bon `type` et `token` :

1. Va sur la page carrières de la société.
2. Clique sur "Voir les offres" / "See open positions".
3. Regarde l'URL dans la barre d'adresse une fois redirigé :
   - `boards.greenhouse.io/XXX` → `"type": "greenhouse", "token": "XXX"`
   - `jobs.lever.co/XXX` → `"type": "lever", "token": "XXX"`
   - `jobs.ashbyhq.com/XXX` → `"type": "ashby", "token": "XXX"`
   - autre chose → utilise `"type": "generic", "url": "URL-de-la-page"`
     (détection basique par mot-clé, moins précise)

Envoie-moi la liste des URLs trouvées et je te prépare le fichier
`companies.json` complet et prêt à copier-coller.

---

## Limites à connaître

- Le mode `"generic"` ne fait que détecter la présence du mot "data" sur
  la page, sans lien précis vers l'offre — à n'utiliser qu'en dernier
  recours.
- Certains sites affichent leurs offres en JavaScript pur (rien dans le
  HTML brut) : ni le mode générique ni les appels API ne fonctionneront
  dans ce cas précis. Dis-le moi si tu identifies un site comme ça, ça se
  contourne autrement.
- GitHub Actions gratuit : largement suffisant pour ce volume (quelques
  secondes d'exécution par jour, sur un repo privé ou public).
- ntfy.sh gratuit : pas de compte requis, mais la contrepartie est que
  n'importe qui connaissant ton nom de topic peut voir tes notifications
  — d'où l'importance de choisir un nom peu devinable.
