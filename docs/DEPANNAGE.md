# Dépannage

Commence toujours par **`2_VERIFIER_CONNEXION.bat`** avec le jeu ouvert sur un niveau :
il affiche ce que le bot voit et crée l'image `capture_test_annote.png`.

---

## Le téléphone n'est pas détecté

**Symptôme :** la liste `Appareils : []` est vide, ou une erreur `adb a échoué`.

1. Vérifie que le **débogage USB** est activé (voir README, étape 4).
2. Essaie **un autre câble** : beaucoup de câbles ne font que charger.
3. Essaie un autre port USB du PC (de préférence directement sur le PC, pas sur un hub).
4. Sur le téléphone, déroule les notifications → notification USB →
   **« Transfert de fichiers »**.

## `unauthorized` à côté du téléphone

Le PC voit le téléphone mais n'a pas la permission.
Débranche, rebranche, déverrouille le téléphone et accepte la fenêtre
**« Autoriser le débogage USB ? »** (coche « Toujours autoriser »).
Si la fenêtre n'apparaît plus : *Options de développement → Révoquer les autorisations
de débogage USB*, puis rebranche.

## `python` n'est pas reconnu

Python n'est pas installé ou pas dans le PATH. Relance `1_INSTALLER.bat`
(deux fois si Python vient d'être installé), ou installe Python depuis python.org en
cochant **« Add Python to PATH »**.

## Les glissements ne font rien

- **Xiaomi / Redmi / POCO** : active **« Débogage USB (paramètres de sécurité) »**
  dans les options de développement.
- Le téléphone doit être sous **Android 11 ou plus** (commande `input motionevent`).
- Si le bot affiche `mode input` au démarrage, c'est normal : c'est la méthode qui
  marche sur la plupart des téléphones.

## Une lettre de la roue est mal lue

**Symptôme :** `! lettres mal lues : ['?', ...]`, ou une mauvaise lettre (ex. P lu comme D).

1. Ouvre le niveau concerné et lance `2_VERIFIER_CONNEXION.bat` : la capture est
   enregistrée dans le dossier `captures/`.
2. Ajoute-la aux modèles de lettres :
   ```
   python outils/ajouter_modeles.py
   ```
   Pour chaque image, le script affiche les lettres lues : tape `o` si elles sont justes,
   ou tape les bonnes lettres dans l'ordre affiché (ex. `HERCA`).
3. Relance le bot : cette lettre sera désormais reconnue directement.

Le bot garde aussi une capture tous les 3 niveaux dans `captures/` : tu peux les
ajouter de la même façon de temps en temps pour rendre la lecture encore plus fiable.

## Le bot ne trouve pas un mot évident

- Le mot n'est peut-être pas dans `data/dico_fr.txt` : ajoute-le sur une nouvelle ligne,
  en majuscules et sans accent.
- Le bot finit de toute façon par l'essayer en combinaisons au hasard, mais c'est plus lent.

## La grille est mal détectée

**Symptôme :** le nombre de cases ou les longueurs de mots affichées au début du niveau
ne correspondent pas à l'écran.

Lance `2_VERIFIER_CONNEXION.bat` et regarde `capture_test_annote.png` : chaque case
détectée est encadrée en rouge. Si une case manque ou est en trop, ouvre une *issue*
sur GitHub en joignant la capture brute du dossier `captures/` (pas l'image annotée).

## Le bot ralentit au bout d'un moment

Le téléphone chauffe : les temps `glisser` et `capture` augmentent dans les chronos `⏱`.
Fais une pause (Ctrl + C), enlève la coque, baisse la luminosité.

## Le bot reste bloqué sur une page (pub, récompense, menu)

Au bout de 3 secondes sur une page inconnue, il touche en bas au milieu de l'écran.
Après 4 essais sans effet, il appuie sur RETOUR.
Si le bouton à toucher est ailleurs, change `POS_TAP_INCONNU` en haut de
`automatisation_wow.py` : `(0.5, 0.85)` veut dire « au milieu, à 85 % de la hauteur ».

## Le bot affiche « ! erreur n°… »

Ce n'est pas grave : le bot ne s'arrête plus jamais tout seul. Si le téléphone ne
répond plus (câble qui saute, téléphone qui chauffe, mise en veille…), il attend que
le téléphone revienne, puis reprend la partie. Seul **Ctrl + C** l'arrête.

Le détail de chaque erreur est noté dans le fichier `erreurs.log` : joins-le si tu
ouvres une *issue* sur GitHub.

## Le PC se met en veille pendant la nuit

Le bot empêche Windows de se mettre en veille tout seul tant qu'il tourne (le réglage
normal revient quand tu l'arrêtes). L'écran du PC peut s'éteindre, ce n'est pas gênant.
Sur un **ordinateur portable**, laisse-le **branché** et **ne rabats pas l'écran** :
fermer le capot déclenche la veille quand même, sauf si tu changes ce réglage
(*Panneau de configuration → Options d'alimentation → Choisir l'action qui suit la
fermeture du capot → Ne rien faire*).

## Plusieurs téléphones branchés

Indique lequel utiliser avant de lancer (le numéro est affiché par `adb devices`) :
```
set ADB_SERIAL=RF8NA0XXXXX
4_LANCER_BOT.bat
```
