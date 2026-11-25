# JCF Portable

Carnet de trafic d'**activation portable** pour **Linux Mint** (et Ubuntu/Debian) et **Windows 10/11**, dans l'esprit de
[Ham2K PoLo](https://polo.ham2k.com/) : saisie ultra-rapide au clavier, programmes « On The Air »,
spots, CAT Hamlib et exports ADIF prêts à envoyer.

Programmes gérés : **POTA, WWFF, SOTA, GMA, WWBOTA**.

## Installation (rien à compiler, rien à installer en Python)

Téléchargez la dernière version dans l'onglet **Releases** (ou **Actions → dernier build → Artifacts**) :

* **`jcfportable_x.y.z_amd64.deb`** (conseillé) : double-clic → *Installer le paquet*.
  Hamlib est installé automatiquement et votre compte est ajouté au groupe `dialout` (accès au port série
  de la radio ; fermez puis rouvrez votre session une fois). Le logiciel apparaît dans le menu, rubrique
  *Radioamateur*.
* **`JCFPortable-x.y.z-x86_64.AppImage`** : un seul fichier, Hamlib inclus. Clic droit → *Propriétés* →
  *Permissions* → cocher *Autoriser l'exécution*, puis double-clic.

### Windows 10 / 11

* **`JCFPortable-x.y.z-windows-installation.exe`** (conseillé) : double-clic, puis *Suivant*. Aucun droit
  administrateur nécessaire. Hamlib est inclus. Au premier lancement, Windows SmartScreen peut afficher
  « Windows a protégé votre ordinateur » (logiciel non signé) : *Informations complémentaires* →
  *Exécuter quand même*.
* **`JCFPortable-x.y.z-windows.exe`** : un seul fichier, rien à installer — double-clic et c'est parti
  (démarrage un peu plus lent : quelques secondes).
* **`JCFPortable-x.y.z-windows-portable.zip`** : à décompresser (par ex. sur une clé USB), puis lancer
  `jcfportable.exe`.
* Pour le CAT, installez le pilote USB de votre radio (Silicon Labs CP210x pour les Yaesu FT-991A,
  FT-710…) et choisissez le port `COMx` indiqué dans le Gestionnaire de périphériques.

## Prise en main

1. **Réglages** : indicatif, locator, préfixes de saisie courte (FR, FFF…), CAT, recherche d'indicatif.
2. **Données hors ligne** : téléchargez les listes de références à la maison (une fois par mois).
3. **Ctrl+N** : nouvelle opération, ajoutez votre référence (recherche par numéro, nom ou « autour de moi »).
4. Tapez la bande ou la fréquence (`20m`, `14.285`), puis les indicatifs et ⏎.
5. **Exporter ADIF** : un fichier par référence (`F4JCF-P@FR-0123-20261125.adi`) à envoyer au programme,
   plus un fichier « complet » à importer dans JCFLog / QLog.

### Commandes dans le champ indicatif

| Saisie | Effet |
|---|---|
| `20m`, `40m`… | change de bande |
| `CW`, `SSB`, `FT8`… | change de mode |
| `14.070` ou `14070` | change de fréquence |
| `.247` | change les derniers chiffres (14.245 → 14.247) |
| `5W` | puissance |
| `OP/F4XXX` | change d'opérateur |
| `14:30`, `05-09`, `+15m`, `-1h` | heure/date fixée (saisie d'un log papier) ; `NOW` pour revenir |
| `QRV`, `QSY`, `QRT`, `SPME` | self-spot (avec `/commentaire` en option) |

Raccourcis : **Espace** = champ suivant · **⏎** = enregistrer · **Échap** = effacer ·
`F4ABC, EA3XYZ` = plusieurs QSO · `.` remplace `/` · dans « Réf. P2P », tapez juste `2518`.

### CAT

Toutes les radios Hamlib (Yaesu, Icom, Kenwood, Elecraft, Xiegu…) : choisissez la radio, le port
(`/dev/ttyUSB0`…) et la vitesse, puis *Tester la liaison*. La fréquence et le mode sont lus en continu ;
un double-clic sur un spot cale la radio. Un `rigctld` déjà lancé ailleurs (Raspberry, autre logiciel)
peut aussi être utilisé.

### Spots

* Lecture : POTA, WWFF, SOTA, GMA, WWBOTA (actualisation automatique, filtres bande/mode).
* Self-spot : POTA, WWFF, GMA, WWBOTA, avec auto-spot toutes les 10 minutes.
* SOTA : l'envoi de spots demande un compte SOTA (SSO), pas encore géré — utilisez SOTAwatch.
* GMA : depuis l'API v2, la lecture des spots demande une clé personnelle `GMA-…` et l'envoi une clé
  `GMS-…` (à demander sur cqgma.org). Renseignez-les dans *Réglages → Spots et exports* ; sans clé,
  les spots GMA sont simplement ignorés.

## Données

Rien de personnel n'est inclus dans le logiciel.

| | Linux | Windows |
|---|---|---|
| Carnet (QSO, références) | `~/.local/share/jcfportable/` | `%LOCALAPPDATA%\jcfportable\` |
| Réglages (dont mot de passe QRZ/HamQTH) | `~/.config/jcfportable/` | `%APPDATA%\jcfportable\` |
| Exports ADIF | `~/JCFPortable/exports` | `Documents\JCFPortable\exports` |

## Construction

GitHub Actions (`.github/workflows/build.yml`) construit l'AppImage, le `.deb`, l'installateur Windows
et la version portable Windows à chaque envoi sur `main` ; une étiquette `v0.1.0` publie une *Release*. Pour développer : `pip install -r requirements.txt`
puis `python -m jcfportable`.

## Licence

GPL v3 — F4JCF. Idées et sources de données reprises de Ham2K PoLo (MPL-2.0, Sebastián Delmont KI2D) ;
le code est entièrement réécrit. Drapeaux : projet flag-icons (licence MIT).
