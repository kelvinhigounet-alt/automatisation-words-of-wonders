# IA de secours (Claude)

Quand le bot est **vraiment bloqué** sur un niveau, il peut envoyer une capture de
l'écran à Claude (l'IA d'Anthropic), qui lit la roue et la grille et renvoie la liste
des mots à placer. Le bot les essaie ensuite lui-même.

C'est utile la nuit ou pendant une longue session sans surveillance, par exemple quand :
- une lettre de la roue n'est pas reconnue (un `W` jamais vu, un `?`...) ;
- une case de la grille a été mal détectée ;
- le mot manquant n'est pas dans le dictionnaire.

## Quand l'IA est appelée

Seulement en dernier recours, dans cet ordre :
1. le bot essaie tous les mots possibles (banque, mots connus, dictionnaire, hasard) ;
2. il rescanne la grille et retente les mots déjà essayés ;
3. **toujours bloqué → il demande à l'IA** ;
4. si les mots de l'IA ne marchent pas non plus, il essaie sans tenir compte des lettres placées.

L'IA est aussi consultée dès le début d'un niveau si une lettre de la roue est illisible (`?`).

L'IA est appelée **au maximum 2 fois par niveau** (`IA_MAX_APPELS_PAR_NIVEAU`), pour qu'un
niveau impossible ne coûte pas d'argent en boucle.

Dans la fenêtre noire, ça ressemble à :
```
  🤖 niveau bloqué -> on demande à l'IA (claude-sonnet-5-5)...
     réponse en 3.2s : roue A V E W X | mots WAX, AXE
     roue corrigée par l'IA : A V E X V -> A W E X V
  ✓ WAX (ia) — niveau terminé
```
La capture envoyée est gardée dans `captures/ia_....png` : tu peux ensuite l'ajouter aux
modèles de lettres (`python outils/ajouter_modeles.py`) pour que le bot reconnaisse la
lettre tout seul la prochaine fois.

## Mise en place (une seule fois)

L'IA passe par l'**API Anthropic**, qui est un service payant à l'usage, **séparé** de
l'abonnement à l'application Claude.

1. Va sur **platform.claude.com** et crée un compte (les nouveaux comptes reçoivent un
   petit crédit gratuit pour tester).
2. Dans *Billing*, ajoute quelques dollars de crédit si besoin.
3. Dans *API Keys*, clique sur **Create Key** et copie la clé (elle commence par `sk-ant-`).
4. Dans le dossier du bot, crée un fichier texte **`cle_api.txt`** et colle la clé dedans,
   seule sur la première ligne. (Ou définis la variable d'environnement `ANTHROPIC_API_KEY`.)

C'est tout : au prochain blocage, le bot l'utilisera.

> 🔒 **Ne partage jamais ta clé.** `cle_api.txt` est exclu de GitHub par le `.gitignore`,
> mais ne l'envoie à personne et ne la colle pas dans une capture. Si elle fuite, supprime-la
> sur platform.claude.com et crée-en une autre.

## Combien ça coûte

Chaque appel envoie une capture réduite (environ 1 500 « jetons ») et un court texte.
Avec le modèle par défaut **Claude Sonnet 5.5** (2 $ par million de jetons en entrée,
10 $ en sortie), un appel coûte **moins d'un centime** (≈ 0,6 centime).
Même avec 100 niveaux bloqués, ça reste autour de 1 €.

Pour payer encore moins, mets `IA_MODELE = "claude-haiku-5-5"` en haut du script
(environ 20 fois moins cher, mais un peu moins fiable pour lire une grille).
Tarifs à jour : https://platform.claude.com/docs/en/about-claude/pricing

## Désactiver

En haut de `automatisation_wow.py` : `IA_SECOURS = False`.
Sans fichier `cle_api.txt`, l'IA est simplement ignorée (le bot l'indique une fois).

## Confidentialité

Seule la **capture d'écran du jeu** est envoyée à Anthropic, au moment du blocage.
Aucune autre donnée de ton PC ou de ton téléphone n'est transmise.
