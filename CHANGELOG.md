# Changelog

## 0.9.9.4 RC1 UI Polish

- page Système réorganisée sans doublons ;
- compteur ONVIF corrigé ;
- état global et services colorés ;
- journaux configurables sur 20, 50 ou 100 lignes ;
- aucun changement du moteur vidéo.


## 0.9.9.3 RC1

- import `re` ajouté pour les diagnostics ;
- endpoint Diagnostics protégé contre les exceptions ;
- sérialisation JSON rendue plus robuste ;
- onglets réordonnés : Caméras, ONVIF, Disposition, Système, Sécurité, Sauvegarde.


## 0.9.9.2 RC1 Login Fix

- JavaScript de connexion réparé ;
- fragment orphelin supprimé ;
- accolade manquante restaurée ;
- contrôle syntaxique JavaScript ajouté.


## 0.9.9.1 RC1 Fix

### Correctifs

- diagnostics intégrés à l’onglet Système ;
- route `/api/diagnostics` déplacée de POST vers GET ;
- structure HTML ONVIF/Système corrigée ;
- gestion des réponses non JSON améliorée.


## 0.9.9 RC1

### Release Candidate

- gel des fonctionnalités ;
- nouvel onglet Diagnostics en lecture seule ;
- rapport de support copiable ;
- journaux récents des deux services ;
- checklist de stabilité 4 h / 24 h / 72 h ;
- aucun changement volontaire du moteur vidéo.


## 0.9.8.1

### Correctifs UX

- réouverture fiable de l’historique des notifications ;
- notifications temporaires décalées de la cloche ;
- panneau compact des raccourcis clavier ;
- aucun changement fonctionnel du moteur vidéo.


## 0.9.8

### Ergonomie

- historique des cinq dernières notifications ;
- compteur de notifications non consultées ;
- raccourcis clavier Web ;
- aucun changement du moteur vidéo ou des formats de configuration.


## 0.9.7

### Nettoyage

- paquet simplifié ;
- anciens README retirés ;
- caches Python exclus ;
- styles et messages harmonisés.

### Fiabilité

- validation Python et JSON ;
- contrôle des fichiers essentiels ;
- contrôle strict de la version CMake ;
- restauration automatique en cas d'échec ;
- contrôle des services après installation.

### Compatibilité

Aucun changement du format de configuration ni du comportement du moteur
vidéo par rapport à la v0.9.6.
