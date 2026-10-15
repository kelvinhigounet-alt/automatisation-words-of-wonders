# Comment fonctionne le bot

Ce document explique, étape par étape, ce que fait `automatisation_wow.py`.
Chaque étape correspond à une section du code (repérable par les grands titres
`# ====` dans le fichier).

---

## Vue d'ensemble

```
┌─────────────┐   capture   ┌──────────────┐  lettres + grille  ┌───────────────┐
│  Téléphone  │ ──────────► │    Vision     │ ─────────────────► │     Mots      │
│  (le jeu)   │             │ (OpenCV)      │                    │ (dictionnaire)│
└─────────────┘             └──────────────┘                    └───────┬───────┘
       ▲                                                                │ un mot
       │                 glissement du doigt (ADB)                      │
       └────────────────────────────────────────────────────────────────┘
```

Le PC et le téléphone communiquent avec **ADB** (Android Debug Bridge), l'outil
officiel de Google pour les développeurs Android. C'est pour ça qu'il faut activer
le « débogage USB ».

---

## 1. Parler au téléphone (section ADB)

| Action | Commande ADB utilisée |
|---|---|
| Capture d'écran | `adb exec-out screencap` (image brute, plus rapide qu'un PNG) |
| Toucher l'écran | `input tap x y` |
| Glisser le doigt sur plusieurs lettres | `input motionevent DOWN` → `MOVE` sur chaque lettre → `UP` |
| Bouton retour | `input keyevent KEYCODE_BACK` |

Une seule session `adb shell` reste ouverte pendant toute la partie (classe `Shell`),
ce qui évite de relancer ADB à chaque commande.

Le bot essaie d'abord une méthode de toucher plus rapide (`sendevent`, qui écrit
directement dans l'écran tactile). La plupart des téléphones la bloquent : il revient
alors automatiquement à `input motionevent`.

---

## 2. Comprendre l'écran (section VISION)

### La roue de lettres
Les lettres de la roue sont **noires sur fond clair**. Le bot cherche les taches
sombres de la bonne taille entourées de clair (`_composantes_lettres`). Le centre de
la roue est la moyenne de leurs positions.

### Lire une lettre
`ocr_lettre` essaie, dans l'ordre :
1. **les vraies lettres du jeu** stockées dans `data/modeles_lettres.npz` : la lettre
   est réduite à une image de 32 × 32 pixels et comparée à chaque modèle. C'est
   instantané et très fiable, car c'est la même police que le jeu ;
2. **des lettres dessinées avec des polices proches**, si l'une ressort nettement ;
3. **Tesseract** (logiciel de reconnaissance de texte), lancé plusieurs fois avec
   des tailles différentes : on garde la réponse majoritaire ;
4. en dernier recours, la lettre de police la plus ressemblante.

### La grille
- Les **cases vides** sont des carrés clairs (`_cases_claires`). Le seuil de clarté
  s'adapte au décor du niveau, parce que les cases sont un peu transparentes.
- Les **cases déjà remplies** sont des tuiles foncées avec une lettre blanche
  (`_cases_remplies`) : on les reconnaît en comparant la lettre aux lettres de la roue.
- `construire_grille` aligne toutes les cases sur un quadrillage (lignes / colonnes),
  retrouve les cases cachées par un objet (feuille, papillon, soleil…), puis repère
  les **emplacements de mots** : toute suite de 3 cases ou plus, à l'horizontale ou
  à la verticale.

### Lire les lettres déjà posées
`lire_case` lit la lettre d'une case remplie. Comme seules les lettres de la roue
peuvent apparaître dans la grille, il suffit de comparer avec ces 5 à 7 lettres :
quelques millisecondes pour toute la grille.

---

## 3. Choisir les mots (section MOTS)

Pour chaque emplacement encore incomplet, le bot construit un **motif**, par exemple
`J _ _ R` si le J et le R sont déjà posés par des mots qui se croisent.

`candidats` propose ensuite des mots dans cet ordre :
1. la **banque** `mots_appris.json` : mots déjà validés pour ce même tirage de lettres ;
2. le **dictionnaire français** (`data/dico_fr.txt`), trié du mot le plus courant
   au plus rare, puis le dictionnaire anglais ;
3. des **combinaisons au hasard** (400 maximum).

Un mot n'est proposé que s'il :
- s'écrit avec les lettres de la roue (en respectant le nombre de chaque lettre) ;
- a la longueur d'un emplacement encore incomplet ;
- respecte les lettres déjà posées dans cet emplacement ;
- n'est pas déjà dans la grille.

Les mots les plus longs sont essayés en premier, car ils remplissent plus de cases.

---

## 4. Jouer un niveau (section JEU)

`jouer_niveau` répète :
1. glisser le mot sur la roue ;
2. attendre la fin de l'animation, refaire une capture ;
3. compter les cases vides : si elles ont diminué, le mot était bon. Le bot lit alors
   les nouvelles lettres posées et note le mot dans la banque.

**Quand plus rien ne colle**, le bot ne s'acharne pas à l'aveugle :
1. il **rescanne toute la grille** sur une nouvelle capture (une erreur de lecture est
   possible) et **retente les mots déjà essayés** (un glissement a pu rater, par exemple
   si le téléphone chauffe) ;
2. si ça ne suffit toujours pas, il essaie **sans tenir compte des lettres posées** ;
3. il relit aussi la roue après 25 échecs d'affilée, au cas où elle aurait été mal lue.

La **fin du niveau** est détectée quand la roue disparaît (vérifié deux fois, à une
seconde d'intervalle, pour ne pas se tromper pendant une animation).

### La boucle principale (`boucle`)
| Ce que le bot voit | Ce qu'il fait |
|---|---|
| une roue + une grille | attend que l'écran soit stable, puis joue le niveau |
| le gros bouton vert « NIVEAU xx » | appuie dessus |
| autre chose pendant 3 s | touche en bas au milieu (récompenses) |
| toujours bloqué après 4 touchers | appuie sur RETOUR (ferme une pub) |

---

## 5. Les fichiers de données

| Fichier | Contenu | Modifiable ? |
|---|---|---|
| `data/dico_fr.txt` | un mot par ligne, en majuscules, sans accents | oui, ajoute des mots où tu veux |
| `data/dico_en.txt` | mots anglais courants | oui |
| `data/modeles_lettres.npz` | modèles de lettres (images 32×32) | via `outils/ajouter_modeles.py` |
| `mots_appris.json` | mots validés, par tirage de lettres | créé automatiquement |
