#!/usr/bin/env python3
"""
Reconstruit les dictionnaires data/dico_fr.txt et data/dico_en.txt.

Tu n'en as PAS besoin pour utiliser le bot : les fichiers sont déjà fournis.
Utile seulement si tu veux changer les règles (longueurs, mots anglais...).

    pip install wordfreq
    python outils/construire_dictionnaire.py

Sources :
  - mots français : paquet npm « an-array-of-french-words » (licence MIT)
  - fréquences et mots anglais : bibliothèque « wordfreq » (données CC BY-SA 4.0)
"""
import io, json, os, re, tarfile, unicodedata, urllib.request

from wordfreq import top_n_list, zipf_frequency

URL = "https://registry.npmjs.org/an-array-of-french-words/-/an-array-of-french-words-2.0.0.tgz"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
LONGUEUR_MIN, LONGUEUR_MAX = 3, 7


def sans_accents(mot):
    """« forêt » -> « FORET » : le jeu n'affiche pas d'accents."""
    return "".join(c for c in unicodedata.normalize("NFD", mot)
                   if unicodedata.category(c) != "Mn").upper()


def mots_francais():
    print("Téléchargement de la liste de mots français...")
    with urllib.request.urlopen(URL) as r:
        archive = tarfile.open(fileobj=io.BytesIO(r.read()), mode="r:gz")
    return json.load(archive.extractfile("package/index.json"))


def main():
    # Français : on garde les mots de 3 à 7 lettres, sans tiret ni apostrophe,
    # triés du plus courant au plus rare (le bot essaie les plus courants d'abord).
    frequence = {}
    for mot in mots_francais():
        if not re.fullmatch(r"[a-zàâäçéèêëîïôöùûüÿ]+", mot):
            continue
        if not LONGUEUR_MIN <= len(mot) <= LONGUEUR_MAX:
            continue
        cle = sans_accents(mot)
        frequence[cle] = max(frequence.get(cle, -1), zipf_frequency(mot, "fr"))
    fr = sorted(frequence, key=lambda m: -frequence[m])

    # Anglais : quelques mots courants, essayés après le français
    deja = set(fr)
    en = [w.upper() for w in top_n_list("en", 60000)
          if re.fullmatch(r"[a-z]{%d,%d}" % (LONGUEUR_MIN, LONGUEUR_MAX), w)
          and w.upper() not in deja and zipf_frequency(w, "en") > 3.0]

    os.makedirs(DATA, exist_ok=True)
    for nom, mots in (("dico_fr.txt", fr), ("dico_en.txt", en)):
        with open(os.path.join(DATA, nom), "w", encoding="utf-8") as f:
            f.write("\n".join(mots) + "\n")
        print(f"{nom} : {len(mots)} mots")


if __name__ == "__main__":
    main()
