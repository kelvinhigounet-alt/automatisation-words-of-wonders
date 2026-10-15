#!/usr/bin/env python3
"""
Automatisation Words of Wonders
================================

Joue tout seul au jeu mobile « Words of Wonders » sur un téléphone Android
branché en USB au PC.

Principe (détaillé dans docs/FONCTIONNEMENT.md) :
  1. capture l'écran du téléphone (ADB)
  2. repère la roue de lettres et la grille (OpenCV)
  3. lit les lettres (modèles de lettres + Tesseract en secours)
  4. cherche les mots possibles dans un dictionnaire, en tenant compte
     des lettres déjà posées dans la grille
  5. fait glisser le doigt virtuellement sur les lettres (ADB)
  6. passe au niveau suivant, récupère les récompenses

Utilisation :
  python automatisation_wow.py               joue en boucle (Ctrl+C pour arrêter)
  python automatisation_wow.py --niveaux 1   joue un seul niveau
  python automatisation_wow.py --verifier    teste la connexion et la détection
  python automatisation_wow.py --test img    analyse une capture, sans téléphone
  python automatisation_wow.py --debug       joue + enregistre des images annotées
"""
import argparse, itertools, json, os, queue, random, shutil, subprocess, sys, threading, time, traceback
from collections import Counter

import cv2
import numpy as np


# =============================================================================
#  RÉGLAGES — tu peux modifier ces valeurs
# =============================================================================

DELAI_APRES_MOT = 0.30          # s : attente après un mot (animation) avant de recapturer
DELAI_ENTRE_LETTRES = 0.012     # s : pause entre deux lettres pendant le glissement
DELAI_FIN_NIVEAU = 3.0          # s : animation de victoire
MAX_ESSAIS_ALEATOIRES = 400     # combinaisons au hasard maximum par niveau
ATTENTE_ECRAN_INCONNU = 3       # s sur un écran inconnu avant de toucher en bas (récompenses)
POS_TAP_INCONNU = (0.5, 0.85)   # où toucher : (x, y) en fraction de l'écran
TAPS_AVANT_RETOUR = 4           # touchers sans effet avant d'appuyer sur RETOUR
MODE_TACTILE = "auto"           # "auto" | "sendevent" (rapide, souvent bloqué) | "input"
CAPTURE_TOUS_LES_N_NIVEAUX = 3  # garde une capture tous les N niveaux (0 = jamais)


# =============================================================================
#  Chemins et outils externes (trouvés automatiquement)
# =============================================================================

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
if not os.path.isdir(DATA):        # ancienne organisation : fichiers à côté du script
    DATA = HERE


def _trouver(env, local, nom, defauts=()):
    """Variable d'env > copie locale (installée par INSTALLER.bat) > PATH > emplacements usuels."""
    if os.environ.get(env):
        return os.environ[env]
    for p in [os.path.join(HERE, *local)] if local else []:
        if os.path.exists(p):
            return p
    if shutil.which(nom):
        return shutil.which(nom)
    for p in defauts:
        if os.path.exists(p):
            return p
    return nom


ADB = _trouver("ADB", ("platform-tools", "adb.exe" if os.name == "nt" else "adb"), "adb")
TESSERACT = _trouver("TESSERACT", None, "tesseract", (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")))
DEVICE = os.environ.get("ADB_SERIAL")      # numéro de série si plusieurs appareils branchés

DICO_FR = os.path.join(DATA, "dico_fr.txt")
DICO_EN = os.path.join(DATA, "dico_en.txt")
MODELES = os.path.join(DATA, "modeles_lettres.npz")
BANQUE = os.path.join(HERE, "mots_appris.json")
DEBUG_DIR = os.path.join(HERE, "debug")
CAPTURES_DIR = os.path.join(HERE, "captures")


# =============================================================================
#  ADB : communication avec le téléphone
# =============================================================================
def adb(*args, binary=False):
    cmd = [ADB] + (["-s", DEVICE] if DEVICE else []) + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"adb ne répond plus : {' '.join(cmd)}")
    if r.returncode != 0:
        raise RuntimeError(f"adb a échoué : {' '.join(cmd)}\n{r.stderr.decode(errors='ignore')}")
    return r.stdout if binary else r.stdout.decode(errors="ignore")


class Shell:
    """Une seule session « adb shell » ouverte en permanence : évite de relancer adb
    à chaque commande (~80 ms gagnées par appel)."""
    def __init__(self):
        cmd = [ADB] + (["-s", DEVICE] if DEVICE else []) + ["shell"]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, bufsize=0)
        self.n = 0
        self.mort = False
        # lecture dans un fil séparé : permet d'abandonner si le téléphone ne répond plus
        self.lignes = queue.Queue()
        threading.Thread(target=self._lire, daemon=True).start()

    def _lire(self):
        for ligne in iter(self.p.stdout.readline, b""):
            self.lignes.put(ligne)
        self.lignes.put(None)                   # session fermée

    def run(self, commande, timeout=30):
        self.n += 1
        fin = f"__FIN{self.n}__"
        self.p.stdin.write(f"{commande}; echo {fin}\n".encode())
        self.p.stdin.flush()
        out = []
        limite = time.time() + timeout
        while True:
            try:
                ligne = self.lignes.get(timeout=max(0.1, limite - time.time()))
            except queue.Empty:
                self.fermer()
                raise RuntimeError("Le téléphone ne répond plus (commande trop longue)")
            if ligne is None:
                self.mort = True
                raise RuntimeError("La session adb s'est fermée (câble débranché ?)")
            ligne = ligne.decode(errors="ignore").rstrip("\r\n")
            if ligne == fin:
                return "\n".join(out)
            out.append(ligne)

    def fermer(self):
        self.mort = True
        try:
            self.p.kill()
            self.p.wait(timeout=5)
        except Exception:
            pass


_SHELL = None


def sh(commande):
    global _SHELL
    if _SHELL is None or _SHELL.mort or _SHELL.p.poll() is not None:
        _SHELL = Shell()
    return _SHELL.run(commande)


def capture():
    """Capture brute (sans compression PNG sur le téléphone) : bien plus rapide que -p."""
    raw = adb("exec-out", "screencap", binary=True)
    if len(raw) > 16:
        w, h = int.from_bytes(raw[0:4], "little"), int.from_bytes(raw[4:8], "little")
        entete = len(raw) - w * h * 4
        if 0 < w < 10000 and 0 < h < 10000 and entete in (12, 16):
            rgba = np.frombuffer(raw, np.uint8, offset=entete).reshape(h, w, 4)
            return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
    png = adb("exec-out", "screencap", "-p", binary=True)          # repli
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("Capture illisible — l'écran est-il verrouillé ?")
    return img


def tap(x, y):
    sh(f"input tap {int(x)} {int(y)}")


def back():
    sh("input keyevent KEYCODE_BACK")


# --- toucher « bas niveau » : on écrit directement dans l'écran tactile (/dev/input).
# Chaque « input motionevent » démarre une machine Java (~250 ms) ; sendevent ~2 ms.
TACTILE = None


def init_tactile():
    global TACTILE
    if MODE_TACTILE == "input":
        TACTILE = None
        return
    try:
        info = sh("getevent -p")
        taille = sh("wm size")
        sw, shh = map(int, taille.strip().splitlines()[-1].split(":")[-1].strip().split("x"))
        blocs = info.split("add device")
        for bloc in blocs:
            if " 0035 " not in bloc or " 0036 " not in bloc:   # ABS_MT_POSITION_X / Y
                continue
            dev = bloc.split(":", 1)[1].strip().splitlines()[0].strip()
            def maxi(code):
                for l in bloc.splitlines():
                    if f" {code} " in l and "max" in l:
                        return int(l.split("max")[1].split(",")[0].strip())
                return None
            mx, my = maxi("0035"), maxi("0036")
            if not mx or not my:
                continue
            if sh(f"test -w {dev} && echo OK").strip() != "OK":
                print(f"  (écran tactile {dev} non accessible en écriture -> mode input)")
                break
            TACTILE = {"dev": dev, "sx": (mx + 1) / sw, "sy": (my + 1) / shh,
                       "pression": " 003a " in bloc, "major": " 0030 " in bloc}
            print(f"Toucher rapide : {dev} (écran {sw}x{shh}, tactile {mx}x{my})")
            return
    except Exception as e:
        print("  (toucher rapide indisponible :", e, ")")
    TACTILE = None
    print("Toucher : mode input (plus lent)")


def _glisser_sendevent(points):
    t = TACTILE
    d = t["dev"]
    ev = lambda a, b, c: f"sendevent {d} {a} {b} {c}"
    pos = lambda x, y: [ev(3, 53, int(x * t["sx"])), ev(3, 54, int(y * t["sy"]))]
    x0, y0 = points[0]
    cmds = [ev(3, 47, 0), ev(3, 57, random.randint(100, 60000))] + pos(x0, y0)
    if t["major"]:
        cmds.append(ev(3, 48, 6))
    if t["pression"]:
        cmds.append(ev(3, 58, 60))
    cmds += [ev(1, 330, 1), ev(0, 0, 0), f"sleep {DELAI_ENTRE_LETTRES * 2}"]
    for x, y in points[1:]:
        cmds += pos(x, y) + [ev(0, 0, 0), f"sleep {DELAI_ENTRE_LETTRES}"]
    cmds += [ev(3, 57, -1), ev(1, 330, 0), ev(0, 0, 0)]
    sh("; ".join(cmds))


def _glisser_input(points):
    (x0, y0), rest = points[0], points[1:]
    cmds = [f"input motionevent DOWN {int(x0)} {int(y0)}"]
    for x, y in rest:
        cmds.append(f"input motionevent MOVE {int(x)} {int(y)}")
    xe, ye = points[-1]
    cmds.append(f"input motionevent UP {int(xe)} {int(ye)}")
    sh("; ".join(cmds))


def glisser(points):
    """Doigt posé sur le 1er point, passe par chaque lettre, relâche sur la dernière."""
    if TACTILE:
        _glisser_sendevent(points)
    else:
        _glisser_input(points)


def passer_en_mode_input():
    global TACTILE
    if TACTILE:
        print("  ! le toucher rapide ne semble pas marcher -> retour au mode input")
        TACTILE = None


# =============================================================================
#  VISION : repérer la grille, la roue et lire les lettres
# =============================================================================
def _masque_clair(img, smax=50, vmin=238):
    """Pixels des cases vides : très clairs et peu saturés (blanc, ou blanc teinté par le décor)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return (hsv[..., 2] > vmin) & (hsv[..., 1] < smax)


def _cases_claires(img):
    """Cases vides bien visibles de la grille -> liste de (x, y, w, h)."""
    h, w = img.shape[:2]
    m = _masque_clair(img, 50, 228).astype(np.uint8) * 255
    m[int(h * 0.5):] = 0
    m[: int(h * 0.09)] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cases = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        # le contour externe ignore les trous : une case avec un objet dedans passe aussi
        # remplissage : écarte les lettres blanches creuses (O, Q, U...) des tuiles remplies
        if bw > 0.06 * w and 0.8 < bw / bh < 1.25 and m[y:y + bh, x:x + bw].mean() > 0.45 * 255:
            cases.append((x, y, bw, bh))
    if not cases:
        return []
    med = np.median([c[2] for c in cases])
    return [c for c in cases if 0.85 * med < c[2] < 1.15 * med]


def _cases_remplies(img, modeles):
    """Cases déjà remplies : lettre blanche (de la roue) sur une tuile foncée."""
    if not modeles:
        return []
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blanc = ((hsv[..., 2] > 200) & (hsv[..., 1] < 50)).astype(np.uint8)
    blanc[int(h * 0.55):] = 0
    blanc[: int(h * 0.09)] = 0
    n, lab, st, cen = cv2.connectedComponentsWithStats(blanc)
    centres, hauteurs = [], []
    for j in range(1, n):
        X, Y, W, H, A = st[j]
        if not 0.03 * w < H < 0.12 * w or W > 1.3 * H:
            continue
        pad = max(3, int(H * 0.25))
        zone = hsv[max(0, Y - pad): Y + H + pad, max(0, X - pad): X + W + pad, 2]
        anneau = np.ones(zone.shape, bool)
        anneau[pad: pad + H, pad: pad + W] = False
        if zone[anneau].mean() > 170:           # pas sur une tuile foncée
            continue
        m = (lab[Y:Y + H, X:X + W] == j)
        nm, a = _norm(m), W / H
        if min(float(np.abs(nm - t).mean()) + abs(a - ar) * 0.5 for t, ar in modeles) < 0.2:
            centres.append((X + W / 2, Y + H / 2)); hauteurs.append(H)
    if len(centres) < 2:
        return []
    c = np.array(centres)
    d = []
    for i in range(len(c)):
        for k in range(len(c)):
            dx, dy = abs(c[i] - c[k])
            if i != k and (dx < 0.2 * dy or dy < 0.2 * dx):
                d.append(max(dx, dy))
    pas = min(d) if d else np.median(hauteurs) / 0.55
    t = int(pas * 0.93)
    return [(int(x - t / 2), int(y - t / 2), t, t) for x, y in c]


def detecter_cases(img, modeles=None):
    """Cases de la grille (vides + déjà remplies si modeles fournis) -> liste de (x, y, w, h)."""
    claires = _cases_claires(img)
    remplies = _cases_remplies(img, modeles)
    if claires and remplies:
        tr = np.median([c[2] for c in remplies])
        claires = [c for c in claires if c[2] > 0.8 * tr] or claires
        t = int(np.median([c[2] for c in claires]))
        remplies = [(x + w // 2 - t // 2, y + h // 2 - t // 2, t, t) for x, y, w, h in remplies]
        remplies = [r for r in remplies if all(abs(r[0] - c[0]) > t / 2 or abs(r[1] - c[1]) > t / 2
                                               for c in claires)]
    cases = claires + remplies
    return cases if len(cases) >= 3 else []


def construire_grille(cases, img=None, modeles=None, lettres=None):
    """Cases -> coordonnées (ligne, col) + emplacements de mots (>= 3 cases).
    Avec img : retrouve aussi les cases cassées par un gros objet (papillon...)."""
    if not cases:
        return None
    taille = int(np.median([c[2] for c in cases]))
    def pas_axe(vals):
        v = sorted(set(vals))
        # regroupe les positions presque identiques (petits décalages de détection)
        groupes = [[v[0]]]
        for x in v[1:]:
            if x - groupes[-1][-1] < taille * 0.35:
                groupes[-1].append(x)
            else:
                groupes.append([x])
        centres = [float(np.mean(g)) for g in groupes]
        d = [b - a for a, b in zip(centres, centres[1:]) if taille * 0.85 < b - a < taille * 1.4]
        return float(np.median(d)) if d else taille * 1.05
    px, py = pas_axe(c[0] for c in cases), pas_axe(c[1] for c in cases)
    x0, y0 = min(c[0] for c in cases), min(c[1] for c in cases)
    pos = {}
    for c in cases:
        k = (round((c[1] - y0) / py), round((c[0] - x0) / px))
        if k not in pos:      # deux détections sur la même case : on garde la première
            pos[k] = c
    smax, vmin = 35, 238
    if img is not None:
        # seuils adaptés au décor, calculés sur les vraies cases vides (pas les tuiles remplies)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        bords = [hsv[y + h // 4: y + 3 * h // 4, x + 4: x + w // 6] for x, y, w, h in cases]
        bords = [b for b in bords if b.size and np.median(b[..., 2]) > 225 and np.median(b[..., 1]) < 50]
        if bords:
            smax = max(float(np.median([np.median(b[..., 1]) for b in bords])) + 12, 35)
            vmin = max(222, min(238, float(np.median([np.median(b[..., 2]) for b in bords])) - 18))
        clair = _masque_clair(img, smax, vmin)
        H, W = img.shape[:2]
        rs = [k[0] for k in pos]; cs = [k[1] for k in pos]
        cellules = [(r, c) for _ in range(4)
                    for r in range(min(rs) - 3, max(rs) + 4) for c in range(min(cs) - 3, max(cs) + 4)]
        for r, c in cellules:
            if True:
                if (r, c) in pos:
                    continue
                x, y = int(x0 + c * px), int(y0 + r * py)
                if x < 0 or y < 0 or x + taille > W or y + taille > H * 0.55:
                    continue
                voisins = sum((r + dr, c + dc) in pos for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)))
                # case vide (claire), ou case déjà remplie (tuile colorée avec une lettre)
                if voisins and (clair[y:y + taille, x:x + taille].mean() > 0.25
                                or (modeles and lire_case(img, (x, y, taille, taille), modeles, lettres))):
                    pos[(r, c)] = (x, y, taille, taille)
    slots = []
    for horiz in (True, False):
        lignes = {k[0] if horiz else k[1] for k in pos}
        for l in lignes:
            idx = sorted(k[1] if horiz else k[0] for k in pos if (k[0] if horiz else k[1]) == l)
            run = [idx[0]]
            for v in idx[1:] + [None]:
                if v is not None and v == run[-1] + 1:
                    run.append(v)
                    continue
                if len(run) >= 3:
                    slots.append([(l, r) if horiz else (r, l) for r in run])
                if v is not None:
                    run = [v]
    return {"cases": pos, "slots": slots, "smax": smax, "vmin": vmin}


def cases_vides(img, grille):
    """Case vide = encore majoritairement claire (même avec un objet dessus).
    Une case remplie prend une couleur avec une lettre."""
    clair = _masque_clair(img, grille.get("smax", 50), grille.get("vmin", 238))
    vides = set()
    for k, (x, y, w, h) in grille["cases"].items():
        if clair[y:y + h, x:x + w].mean() > 0.25:
            vides.add(k)
    return vides


def _composantes_lettres(img):
    """Composantes noires de taille « lettre de la roue », entourées de clair."""
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    n, lab, st, cen = cv2.connectedComponentsWithStats((g < 90).astype(np.uint8))
    pad = int(0.03 * w)
    res = []
    for j in range(1, n):
        X, Y, W, H, A = st[j]
        if Y < h * 0.45 or not (0.06 * w < H < 0.14 * w) or W > 1.3 * H:
            continue
        zone = g[max(0, Y - pad): Y + H + pad, max(0, X - pad): X + W + pad]
        anneau = np.ones(zone.shape, bool)
        anneau[pad: pad + H, pad: pad + W] = False
        if zone[anneau].mean() < 215:          # icônes sur fond foncé, pub...
            continue
        res.append((j, X, Y, W, H))
    if len(res) < 3:
        return lab, []
    med = np.median([r[4] for r in res])
    return lab, [r for r in res if 0.85 * med < r[4] < 1.15 * med]


def detecter_roue(img):
    """Centre et rayon de la roue, déduits des lettres -> (cx, cy, r) ou None."""
    _, comps = _composantes_lettres(img)
    if len(comps) < 3:
        return None
    pts = np.array([(X + W / 2, Y + H / 2) for _, X, Y, W, H in comps])
    cx, cy = pts.mean(axis=0)
    r = np.sqrt(((pts - (cx, cy)) ** 2).sum(axis=1)).max() * 1.35
    return cx, cy, r


_MODELES = None


def _modeles_lettres():
    """Modèles de lettres livrés avec le bot : vraies lettres du jeu + polices proches."""
    global _MODELES
    if _MODELES is None:
        try:
            d = np.load(MODELES)
            _MODELES = (list(d["lettres"]), d["masques"].astype(np.float32), d["aspects"], d["reel"])
        except Exception:
            _MODELES = ([], np.zeros((0, 32, 32), np.float32), np.zeros(0), np.zeros(0, bool))
    return _MODELES


def _plus_proche(n, a, filtre):
    lettres, masques, aspects, reel = _modeles_lettres()
    if not lettres:
        return None, 9.0
    sc = np.abs(masques - n).mean(axis=(1, 2)) + np.abs(aspects - a) * 0.5
    sc = np.where(filtre(reel), sc, 9.0)
    k = int(np.argmin(sc))
    return str(lettres[k]), float(sc[k])


def ocr_lettre(binaire):
    ys, xs = np.nonzero(binaire)
    if len(ys) == 0:
        return "?"
    crop = binaire[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    hh, ww = crop.shape
    if ww < hh * 0.35:                       # trait vertical fin : c'est un I
        return "I"
    n, a = _norm(crop), ww / hh
    # 1) comparaison avec de vraies lettres du jeu (même police) : fiable et instantané
    l, sc = _plus_proche(n, a, lambda r: r)
    if l and sc < 0.065:
        return l
    # 2) lettres dessinées dans des polices proches : si une lettre ressort nettement
    lettres, masques, aspects, reel = _modeles_lettres()
    if lettres:
        scs = np.abs(masques - n).mean(axis=(1, 2)) + np.abs(aspects - a) * 0.5
        best = {}
        for x, v, r in zip(lettres, scs, reel):
            if not r:
                best[str(x)] = min(best.get(str(x), 9.0), float(v))
        tri = sorted((v, x) for x, v in best.items())
        if len(tri) > 1 and tri[0][0] < 0.12 and tri[1][0] - tri[0][0] > 0.05:
            return tri[0][1]
    # 3) Tesseract, plusieurs tailles/modes, on vote
    votes = Counter()
    tmp = os.path.join(HERE, "_ocr_tmp.png")
    img = (255 - crop * 255).astype(np.uint8)
    for hauteur in (40, 100, 60, 140):
        f = hauteur / hh
        r = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        r = cv2.copyMakeBorder(r, 25, 25, 25, 25, cv2.BORDER_CONSTANT, value=255)
        cv2.imwrite(tmp, r)
        for psm in ("10", "7"):
            out = subprocess.run([TESSERACT, tmp, "-", "--psm", psm, "-c",
                                  "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ"],
                                 capture_output=True, text=True).stdout.strip()
            if len(out) == 1:
                votes[out] += 1
        if votes and votes.most_common(1)[0][1] >= 3:
            break
    if votes and votes.most_common(1)[0][1] >= 2:
        return votes.most_common(1)[0][0]
    # 4) au pire : lettre de police la plus ressemblante (jamais de « ? »)
    l, sc = _plus_proche(n, a, lambda r: ~r)
    if l and sc < 0.35:
        return l
    return votes.most_common(1)[0][0] if votes else "?"


def _masque_lettre_case(img, rect):
    """Renvoie le masque binaire de la lettre dans la case, ou None."""
    x, y, w, h = rect
    m = int(w * 0.12)
    crop = img[y + m:y + h - m, x + m:x + w - m]
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sat = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[..., 1]
    _, b = cv2.threshold(g, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bord = np.concatenate([b[0], b[-1], b[:, 0], b[:, -1]])
    lettre = (b == (0 if bord.mean() > 0.5 else 1)).astype(np.uint8)   # classe minoritaire au bord
    n, lab, st, cen = cv2.connectedComponentsWithStats(lettre)
    H, W = lettre.shape
    best = None
    for j in range(1, n):
        X, Y, ww, hh, A = st[j]
        if not 0.35 * H < hh < 0.95 * H or ww > 0.95 * W:
            continue
        cx, cy = cen[j]
        if abs(cx - W / 2) > 0.25 * W or abs(cy - H / 2) > 0.25 * H:
            continue
        pix = lab == j
        if sat[pix].mean() > 70:        # objet coloré (feuille, papillon...), pas une lettre
            continue
        if best is None or A > best[1]:
            best = (j, A)
    if best is None:
        return None
    j = best[0]
    X, Y, ww, hh, _ = st[j]
    return (lab[Y:Y + hh, X:X + ww] == j).astype(np.uint8)


def _norm(m):
    return cv2.resize(m.astype(np.float32), (32, 32), interpolation=cv2.INTER_AREA)


def modeles_roue(img):
    """Masques des lettres de la roue : servent de modèles pour lire les lettres de la grille
    (même police, et seules ces lettres peuvent apparaître dans la grille)."""
    lab, comps = _composantes_lettres(img)
    return [(_norm(lab[Y:Y + H, X:X + W] == j), W / H) for j, X, Y, W, H in comps]


def lire_case(img, rect, modeles, lettres_roue):
    """Lettre affichée dans une case de la grille, ou None (case vide / objet).
    Rapide : seules les lettres de la roue sont possibles, on compare donc à leurs
    modèles (roue + modèles livrés) sans jamais lancer Tesseract."""
    m = _masque_lettre_case(img, rect)
    if m is None:
        return None
    ys, xs = np.nonzero(m)
    m = m[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    if m.shape[1] < m.shape[0] * 0.35:
        return "I" if "I" in lettres_roue else None
    n, a = _norm(m), m.shape[1] / m.shape[0]
    best = {}
    for (t, ar), l in zip(modeles, lettres_roue):
        best[l] = min(best.get(l, 9.0), float(np.abs(n - t).mean()) + abs(a - ar) * 0.5)
    lettres, masques, aspects, _ = _modeles_lettres()
    if lettres:
        sc = np.abs(masques - n).mean(axis=(1, 2)) + np.abs(aspects - a) * 0.5
        for l, v in zip(lettres, sc):
            l = str(l)
            if l in best:
                best[l] = min(best[l], float(v))
    if not best:
        return None
    l, v = min(best.items(), key=lambda kv: kv[1])
    return l if v < 0.35 else None


def detecter_lettres(img, roue=None):
    """Lettres noires de la roue -> liste de (lettre, x, y)."""
    lab, comps = _composantes_lettres(img)
    return [(ocr_lettre((lab[Y:Y + H, X:X + W] == j).astype(np.uint8)), X + W / 2, Y + H / 2)
            for j, X, Y, W, H in comps]


def bouton_vert(img):
    """Gros bouton vert « NIVEAU xx » -> centre ou None."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] > 40) & (hsv[..., 0] < 85) & (hsv[..., 1] > 150)
         & (hsv[..., 2] > 130)).astype(np.uint8)
    _, _, st, cen = cv2.connectedComponentsWithStats(m)
    for s, c in zip(st[1:], cen[1:]):
        x, y, bw, bh, a = s
        if a > 0.03 * w * w and bh > 0.08 * w and 2.5 < bw / bh < 7 and y > h * 0.5:
            return c
    return None


# =============================================================================
#  MOTS : dictionnaire, mots appris, recherche des candidats
# =============================================================================
def charger(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [l.strip().upper() for l in f if l.strip()]


DICO = None


def dico():
    global DICO
    if DICO is None:
        DICO = charger(DICO_FR) + charger(DICO_EN)
    return DICO


def banque():
    try:
        with open(BANQUE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def apprendre(cle, mot):
    b = banque()
    if mot not in b.setdefault(cle, []):
        b[cle].append(mot)
        with open(BANQUE, "w", encoding="utf-8") as f:
            json.dump(b, f, ensure_ascii=False, indent=1, sort_keys=True)


def compatible(mot, motifs):
    """Le mot rentre-t-il dans au moins un emplacement encore incomplet ?
    motifs : liste de motifs, ex. ['J', None, None, 'R'] = J _ _ R (None = lettre inconnue)."""
    return any(len(mot) == len(m) and all(p is None or p == c for p, c in zip(m, mot))
               for m in motifs)


def candidats(lettres, motifs, deja):
    """Générateur : banque apprise -> dictionnaire FR/EN (fréquents d'abord) -> aléatoire.
    Seuls les mots compatibles avec les lettres déjà posées dans la grille sont proposés."""
    stock = Counter(lettres)
    cle = "".join(sorted(lettres))
    longueurs = {len(m) for m in motifs}
    ok = lambda m: m not in deja and compatible(m, motifs) and not Counter(m) - stock
    vus = set()
    for m in banque().get(cle, []):
        if ok(m):
            vus.add(m); yield m, "banque"
    # les mots longs remplissent plus de cases : on les essaie en premier
    for L in sorted(longueurs, reverse=True):
        for m in dico():
            if len(m) == L and m not in vus and ok(m):
                vus.add(m); yield m, "dico"
    essais = 0
    for L in sorted(longueurs, reverse=True):
        perms = list(set(itertools.permutations(lettres, L)))
        random.shuffle(perms)
        for p in perms:
            m = "".join(p)
            if m in vus or m in deja or not compatible(m, motifs):
                continue
            essais += 1
            if essais > MAX_ESSAIS_ALEATOIRES:
                return
            vus.add(m); yield m, "aléatoire"


def chemin(mot, lettres_pos):
    utilises, pts = set(), []
    for ch in mot:
        i = next(i for i, (l, _, _) in enumerate(lettres_pos) if l == ch and i not in utilises)
        utilises.add(i)
        pts.append(lettres_pos[i][1:])
    return pts


# =============================================================================
#  DEBUG : images annotées
# =============================================================================
def annoter(img, grille, roue, lettres, chemin_fichier):
    out = img.copy()
    if grille:
        for (r, c), (x, y, w, h) in grille["cases"].items():
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), 3)
            cv2.putText(out, f"{r},{c}", (x + 5, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    if roue:
        cv2.circle(out, (int(roue[0]), int(roue[1])), int(roue[2]), (255, 0, 0), 4)
    for l, x, y in lettres or []:
        cv2.putText(out, l, (int(x) + 40, int(y)), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
    cv2.imwrite(chemin_fichier, out)


def analyser(img):
    roue = detecter_roue(img)
    lettres = detecter_lettres(img, roue) if roue else []
    modeles = modeles_roue(img) if lettres else None
    grille = construire_grille(detecter_cases(img, modeles), img, modeles, [l for l, _, _ in lettres])
    return grille, roue, lettres



# =============================================================================
#  COMPTE RENDU DE SESSION
# =============================================================================

RAPPORTS_DIR = os.path.join(HERE, "rapports")


def _duree(sec):
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h} h {m:02d} min {s:02d} s" if h else f"{m} min {s:02d} s"


class Session:
    """Statistiques de la session en cours. Le compte rendu est réécrit après chaque
    niveau (il reste à jour même si la fenêtre est fermée brutalement) et une
    dernière fois à l'arrêt avec Ctrl+C."""

    def __init__(self):
        self.debut = time.time()
        self.fichier = os.path.join(RAPPORTS_DIR, time.strftime("session_%Y-%m-%d_%Hh%M.txt"))
        self.niveaux = []                 # un dict par niveau terminé
        self.abandons = 0
        self.essais = 0
        self.mots = 0
        self.sources = Counter()
        self.plus_long = ""
        self.t_glisser = self.t_capture = 0.0
        self.rescans = self.recompenses = self.retours = self.erreurs = 0
        self.mode_tactile = "?"
        self._niveau = None

    # --- appelé par le bot
    def debut_niveau(self, lettres, nb_cases):
        self._niveau = {"lettres": "".join(lettres), "cases": nb_cases, "debut": time.time(),
                        "mots": 0, "essais": 0}

    def essai(self, glisser, capture):
        self.essais += 1
        self.t_glisser += glisser
        self.t_capture += capture
        if self._niveau:
            self._niveau["essais"] += 1

    def mot_trouve(self, mot, source):
        self.mots += 1
        self.sources[source] += 1
        if len(mot) > len(self.plus_long):
            self.plus_long = mot
        if self._niveau:
            self._niveau["mots"] += 1

    def fin_niveau(self, reussi):
        if self._niveau:
            n = self._niveau
            n["duree"] = time.time() - n["debut"]
            if reussi:
                self.niveaux.append(n)
            else:
                self.abandons += 1
            self._niveau = None
        self.ecrire()

    # --- compte rendu
    def texte(self):
        duree = time.time() - self.debut
        nb = len(self.niveaux)
        L = []
        L.append("COMPTE RENDU DE SESSION — Automatisation Words of Wonders")
        L.append("=" * 58)
        L.append(f"Début            : {time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(self.debut))}")
        L.append(f"Fin              : {time.strftime('%d/%m/%Y %H:%M:%S')}")
        L.append(f"Durée            : {_duree(duree)}")
        L.append(f"Mode de toucher  : {self.mode_tactile}")
        L.append("")
        L.append("NIVEAUX")
        L.append(f"  Terminés                 : {nb}")
        L.append(f"  Abandonnés / relancés    : {self.abandons}")
        if nb:
            durees = [n["duree"] for n in self.niveaux]
            L.append(f"  Durée moyenne / niveau   : {_duree(sum(durees) / nb)}")
            L.append(f"  Plus rapide / plus long  : {_duree(min(durees))} / {_duree(max(durees))}")
            L.append(f"  Rythme                   : {nb / (duree / 3600):.1f} niveaux par heure")
        L.append("")
        L.append("MOTS")
        L.append(f"  Mots trouvés             : {self.mots}")
        L.append(f"  Essais au total          : {self.essais}"
                 + (f"  (réussite {100 * self.mots / self.essais:.0f} %)" if self.essais else ""))
        if self.sources:
            L.append("  Trouvés grâce à          : " + ", ".join(
                f"{n} {s}" for s, n in self.sources.most_common()))
        if self.plus_long:
            L.append(f"  Mot le plus long         : {self.plus_long} ({len(self.plus_long)} lettres)")
        if self.essais:
            L.append(f"  Temps moyen par essai    : glisser {self.t_glisser / self.essais:.2f} s"
                     f" · capture {self.t_capture / self.essais:.2f} s")
        L.append("")
        L.append("ÉVÉNEMENTS")
        L.append(f"  Pages de récompense touchées : {self.recompenses}")
        L.append(f"  Appuis sur RETOUR            : {self.retours}")
        L.append(f"  Nouveaux scans de grille     : {self.rescans}")
        L.append(f"  Erreurs (reprise auto)       : {self.erreurs}"
                 + ("  -> détail dans erreurs.log" if self.erreurs else ""))
        if self.niveaux:
            L.append("")
            L.append("DÉTAIL DES NIVEAUX")
            L.append("   n°  lettres   cases  mots  essais  durée")
            for i, n in enumerate(self.niveaux, 1):
                L.append(f"  {i:3d}  {n['lettres']:<8}  {n['cases']:5d}  {n['mots']:4d}  {n['essais']:6d}"
                         f"  {_duree(n['duree'])}")
        return "\n".join(L) + "\n"

    def ecrire(self):
        try:
            os.makedirs(RAPPORTS_DIR, exist_ok=True)
            with open(self.fichier, "w", encoding="utf-8") as f:
                f.write(self.texte())
        except Exception as e:
            print("  (compte rendu non écrit :", e, ")")


SESSION = Session()

# =============================================================================
#  JEU : résolution d'un niveau et boucle principale
# =============================================================================
SUCCES_TACTILE = False


def jouer_niveau(img, debug=False, chrono=None):
    global SUCCES_TACTILE
    chrono = chrono or Chrono()
    grille, roue, lettres = analyser(img)
    chrono.etape("analyse")
    lettres_txt = [l for l, _, _ in lettres]
    if "?" in lettres_txt or len(lettres) < 3:
        print(f"  ! lettres mal lues : {lettres_txt}")
        if debug:
            annoter(img, grille, roue, lettres, os.path.join(DEBUG_DIR, f"echec_{int(time.time())}.png"))
        return False
    cle = "".join(sorted(lettres_txt))
    SESSION.debut_niveau(lettres_txt, len(grille["cases"]))
    print(f"\n=== Niveau : lettres {' '.join(lettres_txt)} | "
          f"{len(grille['cases'])} cases, mots de {sorted(len(s) for s in grille['slots'])}")
    if debug:
        annoter(img, grille, roue, lettres, os.path.join(DEBUG_DIR, f"niveau_{int(time.time())}.png"))

    vides = cases_vides(img, grille)
    deja = set()
    modeles = modeles_roue(img)
    lu = {}             # case -> lettre lue à l'écran (lettres révélées, mots trouvés)
    gen = None
    cle_motifs = None
    contraintes = True
    echecs = 0
    etape = 0           # 0 = normal, 1 = après nouveau scan, 2 = sans contraintes

    def lire_cases(img, cases):
        for c in cases:
            if c not in lu:
                l = lire_case(img, grille["cases"][c], modeles, lettres_txt)
                if l:
                    lu[c] = l

    def motifs_restants():
        res = []
        for slot in grille["slots"]:
            if any(c in vides and c not in lu for c in slot):
                res.append(tuple(lu.get(c) if contraintes else None for c in slot))
        if not res:   # cases isolées non couvertes par un emplacement détecté
            res = [(None,) * L for L in range(3, len(lettres_txt) + 1)]
        return sorted(set(res), key=lambda m: (len(m), str(m)))

    lire_cases(img, grille["cases"])
    vides -= set(lu)

    def mots_deja_places():
        """Mots déjà complets dans la grille : inutile de les retenter."""
        for sl in grille["slots"]:
            if all(c in lu for c in sl):
                deja.add("".join(lu[c] for c in sl))

    mots_deja_places()
    chrono.etape("lecture grille")
    if lu:
        print("  lettres déjà dans la grille :", " ".join(sorted(lu.values())))
    print("  ⏱", chrono)

    while vides:
        motifs = motifs_restants()
        if motifs != cle_motifs:
            gen, cle_motifs = candidats(lettres_txt, motifs, deja), motifs
        try:
            mot, source = next(gen)
        except StopIteration:
            if etape == 0:
                # 1) on a tout essayé : on rescanne la grille (erreur de lecture possible)
                #    puis on rejoue aussi les mots déjà tentés (un glissement a pu être raté)
                print("  ? rien ne colle avec", ["".join(c or "_" for c in m) for m in motifs],
                      "-> nouveau scan de la grille, puis on retente les mots déjà essayés")
                SESSION.rescans += 1
                img = attendre_ecran_stable(capture())
                try:
                    os.makedirs(CAPTURES_DIR, exist_ok=True)
                    cv2.imwrite(os.path.join(CAPTURES_DIR, time.strftime("rescan_%H%M%S.png")), img)
                except Exception:
                    pass
                g2, _, l2 = analyser(img)
                if detecter_roue(img) is None:
                    return True
                if sorted(l for l, _, _ in l2) != sorted(lettres_txt):
                    print("  ! les lettres de la roue ont changé -> on recommence le niveau")
                    return False
                if g2:
                    grille = g2
                lettres = l2
                modeles[:] = modeles_roue(img)
                lu.clear()
                lire_cases(img, grille["cases"])
                vides = cases_vides(img, grille) - set(lu)
                print(f"    {len(grille['cases'])} cases, mots de {sorted(len(s) for s in grille['slots'])},"
                      f" restants : {['' .join(c or '_' for c in m) for m in motifs_restants()]}")
                deja.clear()
                mots_deja_places()
                etape, cle_motifs = 1, None
                continue
            if etape == 1:
                # 2) toujours rien : on oublie les lettres placées
                print("  ? toujours rien -> on réessaie sans tenir compte des lettres placées")
                contraintes, cle_motifs, etape = False, None, 2
                continue
            print("  ! plus de candidats — niveau abandonné (utilise un indice à la main)")
            return False
        if echecs and echecs % 25 == 0:
            # beaucoup d'échecs d'affilée : on vérifie que les lettres lues sont toujours les bonnes
            relu = sorted(l for l, _, _ in detecter_lettres(capture()))
            if relu != sorted(lettres_txt):
                print(f"  ! lettres relues différentes ({' '.join(relu)}) -> on recommence le niveau")
                return False
        deja.add(mot)
        cm = Chrono()
        glisser(chemin(mot, lettres))
        cm.etape("glisser")
        time.sleep(DELAI_APRES_MOT)
        cm.etape("attente")
        img = capture()
        cm.etape("capture")
        if detecter_roue(img) is None:          # écran de fin de niveau ? on confirme
            time.sleep(1.0)
            img = capture()
            cm.etape("confirmation")
        SESSION.essai(dict(cm.etapes).get("glisser", 0), dict(cm.etapes).get("capture", 0))
        if detecter_roue(img) is None:
            SESSION.mot_trouve(mot, source)
            print(f"  ✓ {mot} ({source}) — niveau terminé   ⏱ {cm}")
            apprendre(cle, mot)
            return True
        nv = cases_vides(img, grille) - set(lu)
        if TACTILE and not SUCCES_TACTILE and len(deja) >= 12 and len(nv) == len(vides) == len(grille["cases"]):
            passer_en_mode_input()     # 12 mots sans qu'aucune case ne bouge
            deja.clear(); gen = None; cle_motifs = None
        echecs = 0 if len(nv) < len(vides) else echecs + 1
        if len(nv) < len(vides):
            SUCCES_TACTILE = True
            if etape:
                etape, contraintes, cle_motifs = 0, True, None
            nouvelles = vides - nv
            lire_cases(img, nouvelles)
            # cases que la lecture n'a pas su lire : on déduit depuis l'emplacement rempli
            places = [sl for sl in grille["slots"]
                      if len(sl) == len(mot) and not any(c in nv for c in sl)
                      and any(c in nouvelles for c in sl)
                      and all(lu.get(c, ch) == ch for c, ch in zip(sl, mot))]
            if len(places) == 1:
                for c, ch in zip(places[0], mot):
                    lu.setdefault(c, ch)
            cm.etape("lecture")
            SESSION.mot_trouve(mot, source)
            print(f"  ✓ {mot} ({source})  [{len(nv)} cases restantes]   ⏱ {cm}")
            apprendre(cle, mot)
        else:
            cm.etape("lecture")
            print(f"    ✗ {mot:<8} ⏱ {cm}")
        vides = nv
    print("  ✓ grille complète")
    return True


def _signature(img):
    """Position des lettres de la roue + des cases vides (insensible au décor animé)."""
    _, comps = _composantes_lettres(img)
    lettres = sorted((X // 8, Y // 8, W // 8, H // 8) for _, X, Y, W, H in comps)
    cases = sorted((x // 8, y // 8) for x, y, w, h in _cases_claires(img))
    return lettres, cases


def attendre_ecran_stable(img, essais=4):
    """Recapture jusqu'à ce que les lettres et les cases ne bougent plus
    (sinon on lit des lettres à moitié apparues : H lu comme F...)."""
    s0 = _signature(img)
    for _ in range(essais):
        time.sleep(0.25)
        img = capture()
        s1 = _signature(img)
        if s1 == s0:
            return img
        s0 = s1
    return img


class Chrono:
    """Mesure le temps de chaque étape : c.etape('capture') ... str(c)."""
    def __init__(self):
        self.t0 = self.t = time.time()
        self.etapes = []

    def etape(self, nom):
        now = time.time()
        self.etapes.append((nom, now - self.t))
        self.t = now

    def total(self):
        return time.time() - self.t0

    def __str__(self):
        return " · ".join(f"{n} {d:.2f}s" for n, d in self.etapes) + f"  (total {self.total():.2f}s)"


NIVEAUX_FAITS = 0


def jouer_sans_fin(debug=False, niveaux_max=None):
    """Lance la boucle de jeu et la relance automatiquement après n'importe quelle
    erreur (téléphone qui ne répond plus, câble qui saute, écran bizarre...).
    Seul Ctrl+C arrête vraiment le bot."""
    global _SHELL
    erreurs = 0
    while True:
        try:
            boucle(debug, niveaux_max)
            return                                   # --niveaux atteint
        except KeyboardInterrupt:
            raise
        except Exception as e:
            erreurs += 1
            SESSION.erreurs += 1
            print(f"\n  ! erreur n°{erreurs} : {e}")
            try:
                with open(os.path.join(HERE, "erreurs.log"), "a", encoding="utf-8") as f:
                    f.write(time.strftime("\n=== %Y-%m-%d %H:%M:%S ===\n") + traceback.format_exc())
            except Exception:
                pass
            if _SHELL is not None:
                _SHELL.fermer()
                _SHELL = None
            print("  -> on attend le téléphone puis on reprend (Ctrl+C pour arrêter)")
            try:
                subprocess.run([ADB] + (["-s", DEVICE] if DEVICE else []) + ["wait-for-device"],
                               timeout=120, capture_output=True)
            except Exception:
                pass
            time.sleep(5)


def boucle(debug=False, niveaux_max=None):
    if debug:
        os.makedirs(DEBUG_DIR, exist_ok=True)
    print("Appareils :", adb("devices").strip().splitlines()[1:])
    init_tactile()
    SESSION.mode_tactile = "sendevent (rapide)" if TACTILE else "input"
    global NIVEAUX_FAITS
    faits, inconnu_depuis, taps_inconnu = NIVEAUX_FAITS, None, 0
    while niveaux_max is None or faits < niveaux_max:
        img = capture()
        bouton = bouton_vert(img)
        roue = detecter_roue(img)
        if roue and detecter_cases(img, modeles_roue(img)):
            inconnu_depuis = None
            ch = Chrono()
            img = attendre_ecran_stable(img)     # l'animation d'arrivée du niveau doit être finie
            ch.etape("écran stable")
            if CAPTURE_TOUS_LES_N_NIVEAUX and faits % CAPTURE_TOUS_LES_N_NIVEAUX == 0:
                try:
                    os.makedirs(CAPTURES_DIR, exist_ok=True)
                    cv2.imwrite(os.path.join(CAPTURES_DIR, time.strftime("niveau_%m%d_%H%M%S.png")), img)
                except Exception:
                    pass
                ch.etape("sauvegarde capture")
            ok = jouer_niveau(img, debug, ch)
            SESSION.fin_niveau(ok)
            if ok:
                faits += 1
                NIVEAUX_FAITS = faits
                time.sleep(DELAI_FIN_NIVEAU)
            else:
                time.sleep(2)
        elif bouton is not None:
            inconnu_depuis = None
            print("→ niveau suivant")
            tap(*bouton)
            time.sleep(2.5)
        else:
            inconnu_depuis = inconnu_depuis or time.time()
            if time.time() - inconnu_depuis > ATTENTE_ECRAN_INCONNU:
                if debug:
                    cv2.imwrite(os.path.join(DEBUG_DIR, f"inconnu_{int(time.time())}.png"), img)
                if taps_inconnu < TAPS_AVANT_RETOUR:
                    h, w = img.shape[:2]
                    print("  ? écran inconnu -> toucher en bas au milieu (récompense ?)")
                    tap(w * POS_TAP_INCONNU[0], h * POS_TAP_INCONNU[1])
                    SESSION.recompenses += 1
                    taps_inconnu += 1
                else:
                    print("  ? toujours bloqué -> RETOUR")
                    back()
                    SESSION.retours += 1
                    taps_inconnu = 0
                inconnu_depuis = None
            time.sleep(1)
            continue
        taps_inconnu = 0
    print(f"Terminé : {faits} niveaux.")


def tester(fichier, out=None):
    img = cv2.imread(fichier)
    grille, roue, lettres = analyser(img)
    print(fichier)
    print("  roue   :", roue and tuple(round(v) for v in roue))
    print("  lettres:", [l for l, _, _ in lettres])
    if grille:
        print("  cases  :", len(grille["cases"]), "| vides :", len(cases_vides(img, grille)))
        print("  mots   :", sorted(len(s) for s in grille["slots"]))
        if lettres:
            motifs = sorted({(None,) * len(sl) for sl in grille["slots"]})
            print("  candidats:", [m for m, src in itertools.islice(
                candidats([l for l, _, _ in lettres], motifs, set()), 20) if src != "aléatoire"])
    print("  bouton vert:", bouton_vert(img))
    out = out or os.path.splitext(fichier)[0] + "_annote.png"
    annoter(img, grille, roue, lettres, out)
    print("  ->", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", nargs="+", help="analyser des captures sans téléphone")
    ap.add_argument("--debug", action="store_true", help="enregistre des images annotées dans debug/")
    ap.add_argument("--niveaux", type=int, help="s'arrêter après N niveaux")
    ap.add_argument("--verifier", action="store_true",
                    help="teste la connexion : capture l'écran du téléphone et l'analyse")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        if a.verifier:
            print("adb       :", ADB)
            print("tesseract :", TESSERACT)
            print(adb("devices").strip())
            img = capture()
            os.makedirs(CAPTURES_DIR, exist_ok=True)
            f = os.path.join(CAPTURES_DIR, time.strftime("capture_%H%M%S.png"))
            cv2.imwrite(f, img)
            print(f"Capture OK ({img.shape[1]}x{img.shape[0]})")
            tester(f, os.path.join(HERE, "capture_test_annote.png"))
        elif a.test:
            for f in a.test:
                tester(f)
        else:
            try:
                jouer_sans_fin(a.debug, a.niveaux)
            finally:
                SESSION._niveau = None             # niveau interrompu : non compté
                SESSION.ecrire()
                print("\n" + SESSION.texte())
                print("Compte rendu enregistré dans :", SESSION.fichier)
    except KeyboardInterrupt:
        print("\nArrêt.")
