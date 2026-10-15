#!/usr/bin/env python3
"""
Enrichit data/modeles_lettres.npz avec les lettres de la roue trouvées dans
des captures d'écran (par défaut : toutes les images du dossier captures/).

Le bot garde une capture tous les 3 niveaux : plus il y a de vraies lettres du
jeu dans les modèles, plus la lecture est rapide et fiable.

    python outils/ajouter_modeles.py                 # toutes les captures
    python outils/ajouter_modeles.py ma_capture.png  # une image précise

Pour chaque image, le script affiche les lettres lues et demande confirmation :
réponds « o » si elles sont justes, sinon tape les bonnes lettres dans l'ordre
affiché (ex. « HERCA »), ou « n » pour ignorer l'image.
"""
import glob, os, sys

import cv2
import numpy as np

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
import automatisation_wow as bot  # noqa: E402


def main():
    images = sys.argv[1:] or sorted(glob.glob(os.path.join(bot.CAPTURES_DIR, "*.png")))
    if not images:
        print("Aucune capture trouvée dans", bot.CAPTURES_DIR)
        return
    d = np.load(bot.MODELES)
    lettres, masques = list(d["lettres"]), list(d["masques"].astype(np.float32))
    aspects, reels = list(d["aspects"]), list(d["reel"])
    ajouts = 0
    for f in images:
        img = cv2.imread(f)
        if img is None:
            continue
        lab, comps = bot._composantes_lettres(img)
        if len(comps) < 3:
            continue
        crops = [(lab[Y:Y + H, X:X + W] == j).astype(np.uint8) for j, X, Y, W, H in comps]
        lu = "".join(bot.ocr_lettre(m) for m in crops)
        rep = input(f"{os.path.basename(f)} : lettres lues {lu}  -> juste ? [o / n / bonnes lettres] ").strip().upper()
        if rep in ("N", "NON"):
            continue
        if rep not in ("", "O", "OUI"):
            if len(rep) != len(crops):
                print("  nombre de lettres différent, image ignorée")
                continue
            lu = rep
        for l, m in zip(lu, crops):
            n = bot._norm(m)
            a = m.shape[1] / m.shape[0]
            # inutile d'ajouter une lettre quasi identique à un modèle déjà présent
            if any(r and str(x) == l and np.abs(t - n).mean() < 0.02
                   for x, t, r in zip(lettres, masques, reels)):
                continue
            lettres.append(l); masques.append(n); aspects.append(a); reels.append(True)
            ajouts += 1
    np.savez_compressed(bot.MODELES, lettres=np.array(lettres),
                        masques=np.array(masques, dtype=np.float16),
                        aspects=np.array(aspects, dtype=np.float32), reel=np.array(reels))
    print(f"{ajouts} nouveaux modèles ajoutés ({sum(reels)} vraies lettres au total).")


if __name__ == "__main__":
    main()
