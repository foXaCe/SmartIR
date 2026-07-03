# Contribuer à SmartIR

Merci de votre intérêt pour SmartIR !

## Signaler un bug

Utilisez le [modèle de bug report](.github/ISSUE_TEMPLATE/bug_report.yml).

## Proposer une fonctionnalité

Utilisez le [modèle de feature request](.github/ISSUE_TEMPLATE/feature_request.yml).

## Pull requests

1. Créez une branche dédiée : `git checkout -b feat/ma-fonctionnalite`
2. Installez l'environnement de dev : `scripts/setup`
3. Codez et ajoutez des tests
4. Lancez la qualité : `scripts/lint` puis `scripts/test`
5. Committez en [Conventional Commits](https://www.conventionalcommits.org/) : `feat: …`, `fix: …`
6. Poussez et ouvrez une PR vers `main`

## Configuration de l'environnement local

```bash
pipx install prek   # runner pre-commit en Rust (drop-in)
scripts/setup       # installe les dépendances de dev + les hooks
```

Voir aussi le dossier [.devcontainer/](.devcontainer/) pour un environnement prêt à l'emploi.

## Gestion des dépendances

Ce dépôt utilise **Renovate** (et non Dependabot). Les PR de mise à jour sont ouvertes
par `@renovate[bot]`. Voir le [dashboard Renovate](../../issues?q=is:issue+author:app/renovate).

## Ajouter des codes d'appareils

Les codes IR se trouvent dans `custom_components/smartir/codes/`. Pour ajouter un
nouvel appareil, créez le fichier JSON correspondant et ouvrez une PR.
