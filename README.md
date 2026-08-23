# Job Watch — veille + appli mobile, 100% gratuit

## Vue d'ensemble

- **GitHub Actions** exécute `job_watch.py` tous les jours dans le cloud.
- Le script écrit dans **`jobs_feed.json`** : la liste de toutes les offres
  détectées, avec un statut (`new` / `saved` / `deleted` / `expired`).
- Une **notification push (ntfy.sh)** t'est envoyée à chaque offre
  nouvellement détectée.
- Une **web app** (dossier `docs/`), hébergée gratuitement par **GitHub
  Pages**, affiche les offres à trier avec deux boutons : Sauvegarder /
  Supprimer. Tu l'ajoutes à l'écran d'accueil de ton téléphone Android,
  elle se comporte comme une vraie appli (icône, plein écran).

Ce fichier remplace la version précédente du README (l'ancienne architecture
basée sur `snapshot.json` + email est abandonnée au profit de
`jobs_feed.json` + notifications ntfy + web app).

## Étape 1 — Mettre à jour ton repo

Dans ton repo `Job_Watch` existant, remplace/ajoute ces fichiers :

```
Job_Watch/
├── job_watch.py              (remplacé)
├── companies.json            (inchangé)
├── jobs_feed.json            (nouveau — contenu initial : [])
├── docs/
│   ├── index.html            (nouveau — la web app)
│   ├── manifest.json         (nouveau)
│   └── icon.png              (nouveau)
└── .github/
    └── workflows/
        └── daily.yml         (remplacé)
```

Tu peux supprimer `snapshot.json` s'il existe, il n'est plus utilisé.

## Étape 2 — Activer GitHub Pages

1. Dans ton repo → **Settings** → **Pages**.
2. Source : "Deploy from a branch".
3. Branch : `main`, dossier : **`/docs`**.
4. Enregistrer. GitHub te donne une URL du type
   `https://TON-PSEUDO.github.io/Job_Watch/`.
5. Attends 1-2 minutes puis ouvre cette URL — tu devrais voir l'écran de
   configuration de l'app (tant que tu n'as pas encore mis ton token,
   c'est normal).

## Étape 3 — Créer un Personal Access Token (PAT)

Ce token permet à la web app de lire/écrire `jobs_feed.json` dans ton
repo quand tu appuies sur Sauvegarder/Supprimer.

1. Va sur https://github.com/settings/personal-access-tokens/new
2. Nom : `job-watch-app` (ou ce que tu veux).
3. **Repository access** : "Only select repositories" → choisis `Job_Watch`.
4. **Permissions** → **Repository permissions** → **Contents** : "Read and write".
5. Génère le token et **copie-le tout de suite** (il ne sera plus affiché
   ensuite).

⚠️ Ce token donne accès en écriture à ce repo précis, uniquement depuis
l'appareil où tu l'utilises. Il reste stocké uniquement dans le navigateur
de ton téléphone (localStorage), jamais transmis ailleurs qu'à GitHub.

## Étape 4 — Configurer la web app

1. Ouvre `https://TON-PSEUDO.github.io/Job_Watch/` sur ton téléphone.
2. Renseigne : ton pseudo GitHub, le nom du repo (`Job_Watch`), la branche
   (`main`), et colle le token créé à l'étape 3.
3. "Enregistrer" — la liste des offres doit se charger (vide au départ,
   tant que le script n'a pas encore tourné une première fois).

## Étape 5 — Ajouter l'app à l'écran d'accueil (Android)

1. Ouvre la page dans **Chrome** sur ton téléphone.
2. Menu (⋮) → **"Ajouter à l'écran d'accueil"** (ou "Installer l'application").
3. Une icône "Job Watch" apparaît sur ton téléphone, comme une vraie app.

## Étape 6 — Notifications (ntfy.sh)

Comme précédemment :
1. Installe l'appli **ntfy** sur Android (Play Store, gratuite).
2. Abonne-toi à un topic unique et difficile à deviner (ex.
   `lionel-jw-8f2k1q`).
3. Dans ton repo GitHub → Settings → Secrets and variables → Actions →
   New repository secret : nom `NTFY_TOPIC`, valeur = ton topic.

## Étape 7 — Premier run

Onglet **Actions** de ton repo → workflow "Job Watch" → **Run workflow**.
Ça peuple `jobs_feed.json` pour la première fois. Rafraîchis ensuite
l'app mobile : les offres détectées apparaissent dans l'onglet "À trier".

## Utilisation au quotidien

- Le script tourne seul, tous les jours (~8h).
- Nouvelle offre → notification ntfy sur ton téléphone.
- Tu ouvres l'app (icône sur ton écran d'accueil) → tu vois les offres à
  trier → tu appuies sur **Sauvegarder** (tu comptes postuler) ou
  **Supprimer** (pas intéressé) → ça met à jour `jobs_feed.json` sur
  GitHub directement.
- Les offres "Sauvegardées" restent consultables dans le deuxième onglet.
- Une offre qui disparaît du site avant que tu l'aies triée passe
  automatiquement en `expired` et n'encombre plus la liste — sans jamais
  toucher aux offres que tu as toi-même sauvegardées ou supprimées.

## Compléter `companies.json`

Inchangé par rapport à avant : ajoute une société avec son `type`
(`greenhouse` / `lever` / `ashby` / `teamtailor_html` / `generic`) et son
`token` ou son `url`. Pour identifier la plateforme d'une nouvelle
société, regarde l'URL de sa page "voir les offres".

## Limites à connaître

- Le mode `generic` reste une détection grossière par mot-clé (Shift
  Technology, PayFit actuellement).
- Le token GitHub donne un accès en écriture à ce repo — garde-le privé,
  ne le partage pas.
- Pas de mécanisme de "conflit" si tu utilises l'app sur deux appareils en
  même temps sur la même offre (cas très improbable ici, mais la logique
  est "dernier écrit gagne").
