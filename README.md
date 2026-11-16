# Job Watch — veille d'offres + appli mobile, 100 % gratuit

> **Projet personnel**, public uniquement pour héberger sa web app avec GitHub Pages
> ([tiffado.github.io/job_watch](https://tiffado.github.io/job_watch/)). C'est un outil de veille
> pour mon propre usage, pas un projet vitrine.
>
> Mon projet vitrine en data engineering : **[vlille-data-pipeline](https://github.com/Tiffado/vlille-data-pipeline)**
> (GCS, BigQuery, dbt, Airflow, Kafka).

## Vue d'ensemble

- **GitHub Actions** exécute `job_watch.py` tous les jours (~8 h, heure de Paris).
- Le script interroge les sociétés listées dans `companies.json` et retient les offres dont
  l'intitulé contient « data » ou « données », **hors stages et alternances** (intitulés contenant
  `intern`, `internship`, `stage`, `stagiaire`, `apprenti`, `apprentice`, `alternance`…).
- Il met à jour **`jobs_feed.json`** : toutes les offres jamais vues, chacune avec un statut.
- Une **notification push (ntfy.sh)** est envoyée pour chaque offre nouvellement détectée.
- Une **web app** (dossier `docs/`), hébergée par **GitHub Pages**, affiche les offres à trier.
  Elle s'installe sur l'écran d'accueil d'un téléphone Android comme une appli.

### Statuts d'une offre

| Statut | Signification | Qui le pose |
|---|---|---|
| `new` | détectée, pas encore triée | le script |
| `expired` | n'est plus en ligne alors qu'elle n'était pas triée (redevient `new` si elle revient) | le script |
| `saved` | intéressante | l'appli |
| `applied` | candidature envoyée | l'appli |
| `deleted` | écartée | l'appli |

Le script ne touche jamais aux offres `saved`, `applied` ou `deleted`.

### Analyse d'une offre (optionnel)

Si une clé API Anthropic et un profil sont renseignés dans les réglages, l'appli analyse
automatiquement, une par une, les offres à trier ou sauvegardées qui n'ont pas encore d'analyse :
elle envoie l'URL de l'offre et le profil à l'API Claude et reçoit un avis court. Le bouton
« Analyser avec Claude » relance une analyse à la main.

Chaque carte affiche alors le niveau de match d'un coup d'œil (bordure gauche et pastille) :

| Pastille | Signification |
|---|---|
| vert `●●● Match fort` | profil très proche |
| orange `●●○ Match moyen` | proche, avec des écarts |
| rouge `●○○ Match faible` | écarts importants |
| gris `✕ Hors cible` | stage, alternance, junior ou autre métier |

Les analyses restent **sur le téléphone** (`localStorage`) : elles ne sont jamais écrites dans
`jobs_feed.json`, ce dépôt étant public. Chaque analyse est facturée sur la clé API utilisée.

## Installation

### 1. Activer GitHub Pages

Settings → Pages → Source « Deploy from a branch », branche `main`, dossier **`/docs`**.
L'appli est ensuite servie sur `https://<pseudo>.github.io/job_watch/`.

### 2. Créer un Personal Access Token

Il permet à l'appli de lire et d'écrire `jobs_feed.json`.

1. https://github.com/settings/personal-access-tokens/new
2. **Repository access** : « Only select repositories » → `job_watch`.
3. **Repository permissions** → **Contents** : « Read and write ».
4. Copier le token tout de suite (il ne sera plus affiché).

Le token reste dans le navigateur du téléphone (`localStorage`) et n'est envoyé qu'à GitHub.

### 3. Configurer l'appli

Ouvrir l'URL GitHub Pages sur le téléphone, renseigner le pseudo, le dépôt (`job_watch`), la branche
(`main`) et le token. Pour l'analyse, ajouter une clé API Anthropic et son profil en texte.

### 4. Installer l'appli (Android)

Dans Chrome : menu ⋮ → « Ajouter à l'écran d'accueil ».

### 5. Notifications (ntfy.sh)

1. Installer l'appli **ntfy** (Android) et s'abonner à un topic difficile à deviner.
2. Settings → Secrets and variables → Actions → secret `NTFY_TOPIC` = ce topic.

### 6. Premier run

Onglet **Actions** → workflow « Job Watch » → **Run workflow**.

## Ajouter une société

Dans `companies.json`, ajouter une entrée avec son `type` et son `token` ou son `url` :

| `type` | Champ | Exemple d'URL de la page carrières |
|---|---|---|
| `greenhouse` | `token` | `job-boards.greenhouse.io/<token>` |
| `lever` | `token` | `jobs.lever.co/<token>` |
| `ashby` | `token` | `jobs.ashbyhq.com/<token>` |
| `teamtailor_html` | `url` | page « jobs » d'un site Teamtailor |
| `generic` | `url` | n'importe quelle page carrières |

## Lancer en local

```bash
pip install requests beautifulsoup4
python job_watch.py            # met à jour jobs_feed.json, notifie si NTFY_TOPIC est défini
python job_watch_list.py       # affiche seulement les offres ouvertes, sans rien écrire
```

## Synchronisation entre le script et l'appli

Les deux écrivent `jobs_feed.json` :

- **Le script** ne fait expirer aucune offre d'une société dont la récupération a échoué (API
  indisponible, délai dépassé) : une panne passagère ne vide plus la liste à trier.
- **Le workflow** relance la mise à jour à partir de la dernière version du dépôt si son push est
  refusé parce que l'appli a écrit entre-temps (3 essais). La notification ntfy n'est envoyée
  qu'une fois le feed poussé, pour ne pas annoncer deux fois les mêmes offres.
- **L'appli** envoie ses écritures une par une. Si GitHub refuse une écriture parce que le fichier
  a changé (passage du script, autre appareil), elle relit le fichier, réapplique le changement et
  réessaie une fois.

## Limites connues

- Le mode `generic` ne détecte que la présence d'un mot-clé sur la page, sans lien vers une offre.
- Le filtre porte sur l'intitulé seulement : il ne voit ni le lieu, ni le type de contrat, ni la
  description.
- Le token GitHub donne un accès en écriture à ce dépôt : il doit rester privé.
