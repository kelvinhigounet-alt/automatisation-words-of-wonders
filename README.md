# Automatisation Words of Wonders

Un petit programme Python qui **joue tout seul** au jeu mobile *Words of Wonders*
sur un téléphone Android branché en USB à un PC Windows.

Il regarde l'écran du téléphone, lit les lettres de la roue, repère la grille,
trouve les mots dans un dictionnaire de 47 000 mots français, fait glisser le doigt
à ta place, passe au niveau suivant et récupère les récompenses.

```
=== Niveau : lettres E O F C I F | 21 cases, mots de [3, 3, 4, 4, 6, 6]
  ⏱ écran stable 1.18s · analyse 0.11s · lecture grille 0.03s  (total 1.31s)
    ✗ OFFICE   ⏱ glisser 0.34s · attente 0.30s · capture 0.84s · lecture 0.03s  (total 1.50s)
  ✓ COIFFE (dico)  [16 cases restantes]   ⏱ glisser 0.33s · ... (total 1.60s)
  ✓ FOIE (dico)  [10 cases restantes]   ⏱ glisser 0.26s · ... (total 1.49s)
  ...
  ✓ grille complète
→ niveau suivant
```

> ⚠️ **À lire avant d'utiliser.** Automatiser un jeu est généralement contraire à
> ses conditions d'utilisation : ton compte pourrait être sanctionné. Ce projet est
> partagé dans un but d'apprentissage (vision par ordinateur, ADB, Python).
> Tu l'utilises sous ta propre responsabilité.

---

## Sommaire

1. [Ce qu'il te faut](#1-ce-quil-te-faut)
2. [Télécharger le projet](#2-télécharger-le-projet)
3. [Installer les logiciels (PC)](#3-installer-les-logiciels-sur-le-pc)
4. [Préparer le téléphone](#4-préparer-le-téléphone)
5. [Vérifier que tout marche](#5-vérifier-que-tout-marche)
6. [Lancer le bot](#6-lancer-le-bot)
7. [Réglages](#7-réglages)
8. [Problèmes fréquents](#8-problèmes-fréquents)
9. [Comment ça marche](#9-comment-ça-marche)
10. [Contenu du dépôt](#10-contenu-du-dépôt)
11. [Crédits et licence](#11-crédits-et-licence)

---

## 1. Ce qu'il te faut

- un **PC sous Windows 10 ou 11** avec une connexion internet (pour l'installation) ;
- un **téléphone Android 11 ou plus récent** avec *Words of Wonders* installé ;
- un **câble USB de données** (certains câbles ne font que charger : si le PC ne voit
  pas le téléphone, essaie un autre câble).

Testé sur un Samsung Galaxy S20 FE.

## 2. Télécharger le projet

1. En haut de cette page GitHub, clique sur le bouton vert **`<> Code`** puis
   **`Download ZIP`**.
2. Fais un clic droit sur le fichier téléchargé → **Extraire tout…**
3. Place le dossier extrait où tu veux, par exemple sur le Bureau.

(Si tu connais Git : `git clone` fonctionne aussi.)

## 3. Installer les logiciels sur le PC

Dans le dossier du projet, **double-clique sur `1_INSTALLER.bat`**. Il installe tout seul :

| Logiciel | À quoi il sert |
|---|---|
| **Python** | le langage dans lequel le bot est écrit |
| **OpenCV, NumPy** | analyser les images de l'écran |
| **ADB** (outils Android de Google) | parler au téléphone : captures d'écran, gestes |
| **Tesseract OCR** | lire une lettre en secours quand les modèles ne suffisent pas |

À savoir :
- si Python n'était pas installé, le script l'installe puis te demande de
  **fermer la fenêtre et de relancer `1_INSTALLER.bat`** une deuxième fois ;
- pour Tesseract, Windows peut afficher une fenêtre d'autorisation administrateur :
  accepte-la.

<details>
<summary>Installation manuelle (si l'installateur ne marche pas)</summary>

1. Installe Python 3.10 ou plus récent depuis python.org (coche « Add Python to PATH »).
2. Ouvre une invite de commandes dans le dossier du projet et tape :
   `pip install -r requirements.txt`
3. Télécharge les *SDK Platform-Tools* de Google et dézippe le dossier `platform-tools`
   dans le dossier du projet.
4. Installe Tesseract OCR (version « UB Mannheim » pour Windows).
</details>

## 4. Préparer le téléphone

À faire **une seule fois**.

1. **Activer le mode développeur**
   *Paramètres → À propos du téléphone → Informations sur le logiciel* →
   appuie **7 fois** sur **« Numéro de version »** (ton code PIN est demandé).
   Le message « Mode développeur activé » apparaît.
   *(Sur d'autres marques, « Numéro de build » se trouve souvent directement dans
   « À propos du téléphone ».)*

2. **Activer le débogage USB**
   *Paramètres → Options de développement* (tout en bas) :
   - **Débogage USB** : activé
   - **Rester activé** : activé (l'écran ne s'éteint pas pendant la charge)
   - *Xiaomi / Redmi / POCO uniquement* : active aussi **« Débogage USB (paramètres de sécurité) »**,
     sinon les gestes sont bloqués.

3. **Brancher le téléphone au PC** avec le câble USB.
   Sur le téléphone, une fenêtre **« Autoriser le débogage USB ? »** apparaît :
   coche **« Toujours autoriser depuis cet ordinateur »** puis **Autoriser**.
   Si rien n'apparaît : déroule les notifications → notification USB →
   choisis **« Transfert de fichiers »**.

## 5. Vérifier que tout marche

1. Ouvre *Words of Wonders* sur le téléphone, sur un **niveau** (la roue de lettres visible).
2. Double-clique sur **`2_VERIFIER_CONNEXION.bat`**.

Tu dois voir ton téléphone listé avec le mot `device`, puis les lettres lues et le
nombre de cases. L'image **`capture_test_annote.png`** (créée dans le dossier) montre
ce que le bot a détecté : cases encadrées en rouge, roue entourée en bleu, lettres
lues en rouge.

Ensuite, double-clique sur **`3_TESTER_1_NIVEAU.bat`** : le bot joue **un seul niveau**.
C'est le bon moment pour vérifier que les glissements fonctionnent.

## 6. Lancer le bot

Double-clique sur **`4_LANCER_BOT.bat`**. Le bot joue en boucle, niveau après niveau.

- **Pour l'arrêter** : clique dans la fenêtre noire et appuie sur **Ctrl + C**.
  C'est la seule façon de l'arrêter : en cas d'erreur (câble qui saute, téléphone qui
  ne répond plus…), il attend que le téléphone revienne et reprend tout seul.
- Pendant qu'il tourne, **ne touche pas l'écran** du téléphone et laisse le jeu ouvert.
- Il vaut mieux le lancer sur un niveau **pas encore commencé** (il sait reprendre un
  niveau entamé, mais c'est plus fiable au début d'un niveau).

**Compte rendu de session :** quand tu arrêtes le bot avec Ctrl + C, il affiche un
résumé et l'enregistre dans le dossier `rapports/` (un fichier par session, par ex.
`session_2026-10-15_20h52.txt`) : durée, niveaux terminés, rythme par heure, mots
trouvés, taux de réussite, mot le plus long, temps moyens, récompenses, erreurs, et le
détail de chaque niveau. Le fichier est mis à jour après chaque niveau : il reste
utilisable même si la fenêtre est fermée sans Ctrl + C.

```
NIVEAUX
  Terminés                 : 42
  Durée moyenne / niveau   : 0 min 38 s
  Rythme                   : 87.5 niveaux par heure
MOTS
  Mots trouvés             : 318
  Essais au total          : 402  (réussite 79 %)
  Mot le plus long         : COIFFE (6 lettres)
```

**Lire ce qui s'affiche :**

| Ligne | Signification |
|---|---|
| `✓ FOIE (dico) [10 cases restantes]` | mot accepté par le jeu, trouvé dans le dictionnaire |
| `✗ OFFICE` | mot refusé (pas dans la grille), le bot passe au suivant |
| `(banque)` | mot déjà validé avec ce même tirage de lettres |
| `(connu)` | mot déjà accepté dans un autre niveau : essayé avant le reste du dictionnaire |
| `(aléatoire)` | combinaison au hasard, quand le dictionnaire n'a rien donné |
| `⏱ glisser … capture …` | temps de chaque étape |
| `? écran inconnu -> toucher en bas` | page de récompense : le bot touche l'écran pour la fermer |

**Astuces pour les longues sessions :** le téléphone chauffe, et un téléphone chaud
ralentit tout (les temps `glisser` et `capture` augmentent). Enlève la coque, baisse
la luminosité au minimum, et fais une pause si les temps dépassent 2 secondes.

## 7. Réglages

Les réglages sont **en haut du fichier `automatisation_wow.py`** (ouvre-le avec le
Bloc-notes ou VS Code) :

| Réglage | Par défaut | Effet |
|---|---|---|
| `DELAI_APRES_MOT` | `0.25` | attente après chaque mot. Monte à `0.4` si des mots justes ne sont pas comptés |
| `DELAI_FIN_NIVEAU` | `0.8` | pause après un niveau terminé |
| `CAPTURE_PARTIELLE` | `True` | ne transfère que le haut de l'écran pendant un niveau (capture ~2× plus rapide). `False` si ton téléphone pose problème |
| `DELAI_ENTRE_LETTRES` | `0.012` | pause entre deux lettres pendant le glissement |
| `ATTENTE_ECRAN_INCONNU` | `3` | secondes sur une page inconnue avant de toucher l'écran |
| `POS_TAP_INCONNU` | `(0.5, 0.85)` | où toucher sur une page inconnue (milieu, 85 % de la hauteur) |
| `MAX_ESSAIS_ALEATOIRES` | `400` | combinaisons au hasard maximum par niveau |
| `CAPTURE_TOUS_LES_N_NIVEAUX` | `3` | garde une capture d'écran tous les N niveaux (`0` = jamais) |

Options en ligne de commande (dans une invite de commandes ouverte dans le dossier) :

```
python automatisation_wow.py --niveaux 5     # s'arrête après 5 niveaux
python automatisation_wow.py --debug         # enregistre des images annotées dans debug/
python automatisation_wow.py --test img.png  # analyse une capture, sans téléphone
```

## 8. Problèmes fréquents

Voir **[docs/DEPANNAGE.md](docs/DEPANNAGE.md)**. Les plus courants :

- **`unauthorized` à côté du téléphone** → débranche, rebranche, et accepte la fenêtre
  « Autoriser le débogage USB » sur le téléphone.
- **Aucun appareil listé** → change de câble ou de port USB, mode « Transfert de fichiers ».
- **Une lettre mal lue** → lance `2_VERIFIER_CONNEXION.bat` sur ce niveau, regarde
  `capture_test_annote.png`, puis ajoute la capture aux modèles avec
  `python outils/ajouter_modeles.py` (voir le dépannage).

## 9. Comment ça marche

Explication détaillée, étape par étape, dans **[docs/FONCTIONNEMENT.md](docs/FONCTIONNEMENT.md)**.

En bref :

```
 capture d'écran (ADB) ─► repérage roue + grille (OpenCV) ─► lecture des lettres
        ▲                                                            │
        │                                                            ▼
 vérifie les cases ◄── glisse le doigt (ADB) ◄── choisit un mot compatible
 remplies                                         (dictionnaire + lettres déjà posées)
```

## 10. Contenu du dépôt

```
automatisation-words-of-wonders/
├── automatisation_wow.py      le programme principal (tout le code est commenté)
├── 1_INSTALLER.bat            installe Python, les bibliothèques, ADB et Tesseract
├── 2_VERIFIER_CONNEXION.bat   teste la connexion et la détection
├── 3_TESTER_1_NIVEAU.bat      joue un seul niveau
├── 4_LANCER_BOT.bat           joue en boucle
├── installer.ps1              script d'installation utilisé par 1_INSTALLER.bat
├── requirements.txt           bibliothèques Python nécessaires
├── data/
│   ├── dico_fr.txt            47 000 mots français de 3 à 7 lettres, du plus courant au plus rare
│   ├── dico_en.txt            mots anglais courants (le jeu en contient parfois)
│   └── modeles_lettres.npz    modèles de lettres pour lire la roue et la grille
├── outils/
│   ├── ajouter_modeles.py         ajoute des lettres de tes captures aux modèles
│   └── construire_dictionnaire.py reconstruit les dictionnaires (optionnel)
└── docs/
    ├── FONCTIONNEMENT.md      comment marche le bot
    └── DEPANNAGE.md           solutions aux problèmes courants
```

Fichiers créés pendant l'utilisation (non partagés sur GitHub) : `platform-tools/`
(ADB), `mots_appris.json` (mots validés), `erreurs.log`, `rapports/` (comptes rendus
de session), `captures/`, `debug/`.

## 11. Crédits et licence

- Code : licence **MIT** (voir [LICENSE](LICENSE)).
- Mots français : paquet [an-array-of-french-words](https://www.npmjs.com/package/an-array-of-french-words) (MIT).
- Fréquences des mots et mots anglais : [wordfreq](https://github.com/rspeer/wordfreq),
  données sous licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
  Les fichiers `data/dico_fr.txt` et `data/dico_en.txt` en sont dérivés et sont donc
  partagés sous cette même licence.
- Modèles de lettres : lettres extraites de captures du jeu et dessinées avec les polices
  libres FreeSans, Inter et Liberation Sans.
- Outils : [OpenCV](https://opencv.org/), [Tesseract OCR](https://github.com/tesseract-ocr/tesseract),
  [Android Platform-Tools](https://developer.android.com/tools/releases/platform-tools).

*Words of Wonders* est une marque de son éditeur. Ce projet n'est ni affilié ni approuvé
par l'éditeur du jeu.
