---
name: conception-electronique-kicad
description: Documente les choix de conception electronique qui doivent survivre jusqu'au placement/routage PCB — role de chaque condensateur de decouplage, boucles de courant critiques a minimiser — via l'attribut de composant `Placement`, et rappelle de consulter le stock PartsBox de l'utilisateur avant de figer une reference. Invoquer en choisissant des composants pour un schema KiCad, en ajoutant un decouplage, un snubber, un filtre RC, ou toute boucle a forte di/dt ou dv/dt, ou avant de passer un projet au placement/routage. Complementaire de kicad-schematic-readability (qui traite la lisibilite visuelle, pas l'intention de conception).
---

# conception-electronique-kicad - documenter l'intention de conception pour le placement/routage

## Le probleme que ca resout

Un schema KiCad porte deux choses distinctes : la **connectivite** (ce qui va au
netlist, donc au PCB) et l'**intention de conception** (pourquoi tel
condensateur est la, pourquoi telle boucle doit rester petite). La premiere
survit automatiquement au placement/routage. La seconde ne survit **jamais**
par defaut :

- Une note `add_schematic_text` est un dessin sur la feuille de schema. Elle
  n'existe pas dans le netlist, pas dans le PCB, pas dans l'export BOM/PnP.
  Un outil de placement (`place_component`, `suggest_placement`, autoroute,
  Freerouting) ne la voit pas et ne peut pas la voir.
- Un `Value` allonge ("10R 2W (snubber)") casse le placement standard du
  champ (voir kicad-schematic-readability) et n'est de toute facon lu par
  aucun outil de placement.
- Une propriete de composant, elle, **suit la piece** partout : elle reste
  visible via `get_schematic_component`, elle sort dans un export BOM, et
  elle est la seule forme d'information qui a une chance d'etre lue par un
  agent (ou soi-meme) au moment ou le PCB se dessine.

**Aucun outil de placement/routage ne consulte une propriete personnalisee
automatiquement.** Documenter via `Placement` rend l'information disponible
et interrogeable — ca ne la rend pas appliquee toute seule. Il faut demander
explicitement, au moment du placement, de respecter les proprietes
`Placement` deja posees.

## Le canal retenu : la propriete `Placement`

Convention : un nom de propriete unique, **`Placement`**, sur chaque
composant concerne.

- **Masquee par defaut** (`hide: true`) — c'est une metadonnee de conception,
  pas un texte a lire sur le schema. La note visible (`add_schematic_text`),
  quand elle existe, reste le compagnon "pour un lecteur humain du schema" ;
  la propriete est celle qui persiste au-dela du schema.
- Posee via `set_schematic_component_property` (un seul composant) ou
  `batch_edit_schematic_components` avec
  `properties: {"Placement": {"value": "...", "hide": true}}` (plusieurs
  composants d'un coup — a preferer des qu'un groupe ou une boucle entiere
  est concernee, un appel plutot qu'un par composant).
- Verifier apres coup avec `get_schematic_component` : le champ `Placement`
  doit apparaitre dans la liste des proprietes du composant.

## Regle 0 — consulter le stock PartsBox avant de figer une reference

Avant de choisir une reference (MOSFET, diode, driver, regulateur,
comparateur, condensateur, connecteur...), verifier si l'utilisateur l'a deja
en stock via son inventaire **PartsBox** — ca evite un approvisionnement
inutile et ca donne un point de depart concret (avec quantite disponible)
plutot qu'une reference choisie a l'aveugle depuis une doc generique.

**La cle API vit dans la variable d'environnement `PARTSBOX_API_KEY`**
(variable utilisateur Windows permanente, visible en PowerShell comme en Git
Bash). Verifier sa presence avant de demander quoi que ce soit :

```bash
if [ -n "$PARTSBOX_API_KEY" ]; then echo SET; else echo UNSET; fi
```

- Si elle est presente, l'utiliser directement — ne jamais l'afficher en
  clair dans une reponse ou un fichier (echo/print de sa valeur), seule son
  absence/presence s'affiche.
- Si elle est absente (jamais configuree, ou session Claude Code demarree
  avant sa creation — une variable posee par `setx` n'apparait qu'apres
  redemarrage du processus Claude Code, `setx` ne rafraichit pas
  l'environnement deja charge), la demander a l'utilisateur en chat et
  proposer de la sauver en variable d'environnement permanente
  (`setx PARTSBOX_API_KEY "..."` sous Windows) pour ne plus avoir a la
  redemander — **ne jamais l'ecrire en dur** dans un skill ou un fichier
  verse au projet, seulement dans l'environnement.

**Recuperer l'inventaire complet en un appel** :

```bash
curl -s -H "Authorization: APIKey $PARTSBOX_API_KEY" \
  https://api.partsbox.com/api/1/part/all
```
- Reponse JSON : `data[]`, chaque piece porte `part/name`, `part/mpn`,
  `part/description`, `part/footprint`, et `part/stock[]` (une entree par
  emplacement de stockage physique) — **sommer les `stock/quantity` de
  toutes les entrees** de `part/stock[]` pour obtenir la quantite totale
  disponible d'une piece, elle n'est pas forcement stockee a un seul endroit.
- Sauvegarder la reponse dans le scratchpad puis filtrer par categorie
  (regex sur nom/MPN/description : `mosfet`, `diode`, `driver`,
  `regulat`, `comparat`, etc.) plutot que de re-interroger l'API a chaque
  recherche — l'inventaire ne bouge pas au fil d'une session de conception.

**Piege Windows/ASCII** : les descriptions PartsBox contiennent des symboles
non-ASCII (`Ω`, `µ`, `±`...). Sous Windows, un script Python dont la sortie
est redirigee passe en cp1252 et plante (`UnicodeEncodeError`) des le premier
caractere non representable. Forcer
`sys.stdout.reconfigure(encoding='ascii', errors='replace')` avant tout
traitement ou affichage du contenu recupere.

**Ce qu'on y trouve en pratique** (observe sur ce compte, a reverifier par
projet) : l'inventaire est riche en semi-conducteurs (MOSFET, diodes,
regulateurs, drivers, comparateurs, capteurs, MCU) et en condensateurs, mais
quasiment vide en resistances ordinaires et en connectique courante — ces
elements-la viennent du fond de tiroir de l'atelier, inutile de les chercher
dans PartsBox.

## Regle 1 — documenter le role de chaque condensateur de decouplage

Sur un schema, deux condensateurs de valeur voisine sur le meme rail
d'alimentation *semblent* redondants. Ils ne le sont presque jamais : un
electrolytique bulk absorbe l'ondulation basse frequence pendant qu'une
ceramique locale decouple une broche precise en haute frequence — au-dela de
quelques MHz, l'inductance de piste entre un condensateur eloigne et la
broche d'un CI annule son efficacite, donc chaque CI garde son propre
decouplage local meme si le rail dispose deja de capacite ailleurs. Sans
etiquette, un placement ulterieur (ou un lecteur pressé) risque de les
regrouper ou de deplacer le local loin de sa broche.

Formuler le `Placement` de facon a distinguer explicitement :

- **Decouplage general de rail** — proximite du point d'entree
  (fusible/connecteur), pas d'une broche de CI particuliere :
  `"LOCAL - decouplage HF, coller pres de l'entree (J1/F1/D2)"`
- **Decouplage local a une broche** — doit rester colle a une broche precise,
  meme si le rail a deja de la capacite ailleurs :
  `"LOCAL - coller broche 1 (IN) de U3"`
- **Pas du decouplage du tout**, malgre une position sur un rail
  d'alimentation ou un noeud qui y ressemble — un snubber ou un filtre RC
  doit le dire explicitement, sinon un tri automatique ou un lecteur presse
  le confond avec les caps de decouplage :
  `"LOOP CRITIQUE - snubber, pas decouplage : boucle R5-C16-drain Q1 de surface minimale"`
  `"LOOP CRITIQUE - filtre, pas decouplage : coller pres de R16 et de l'entree - de U7"`

Exemples reels (projet `chargeur_pb/desulfateur`) :

| Ref. | Role | `Placement` |
|---|---|---|
| C2 | decouplage general +19V | `LOCAL - decouplage HF, coller pres de l'entree (J1/F1/D2)` |
| C7 | decouplage local | `LOCAL - coller broche 1 (IN) de U3` |
| C9 | decouplage local (noeud partage) | `LOCAL - coller noeud +12V (U3 OUT / U4 IN)` |
| C16 | snubber, pas decouplage | `LOOP CRITIQUE - snubber, pas decouplage : boucle R5-C16-drain Q1 de surface minimale` |
| C17 | filtre, pas decouplage | `LOOP CRITIQUE - filtre, pas decouplage : coller pres de R16 et de l'entree - (broche 2) de U7` |

### Verification systematique : chaque CI a-t-il son decouplage ?

Documenter le role d'un condensateur ne sert a rien si un CI entier n'en a
**aucun**. Avant de considerer un schema termine, lister tous les circuits
integres (`list_schematic_components` filtre sur le prefixe `U`) et verifier
pour chacun qu'au moins un condensateur est rattache a sa (ses) broche(s)
d'alimentation — pas seulement au meme net que d'autres composants, au net
**de ce CI en particulier** (`get_net_connections` sur son rail, ou
`get_schematic_pin_locations` sur le CI pour reperer ses broches
d'alimentation puis chercher un condensateur au meme point).

Cette verification a un interet reel : sur le projet `chargeur_pb/desulfateur`,
les cinq premiers CI actifs (`U1`, `U3`, `U4`, `U5`, `U8`) avaient chacun leur
decouplage local documente — les deux comparateurs `U6`/`U7`, ajoutes plus
tard dans la conception, n'en avaient **aucun**, sans que rien ne le signale
avant qu'on pose explicitement la question. Rien dans le netlist ni dans
l'ERC ne detecte cet oubli (un CI sans decouplage reste electriquement valide
et passe l'ERC sans avertissement) — seule une relecture volontaire du
schema, CI par CI, le fait apparaitre. A refaire a chaque ajout de CI et
avant tout passage au placement/routage.

## Regle 2 — documenter les boucles critiques hors decouplage, quand il y a lieu

Certaines boucles de courant importent pour une raison qui n'est **pas** le
decouplage : boucle de commutation a fort di/dt (inductance-diode-interrupteur),
boucle d'impulsion vers un connecteur de sortie, boucle de mesure Kelvin,
boucle de snubber. Des qu'une telle boucle existe et que sa surface compte
electriquement (CEM rayonnee, inductance parasite qui degrade un front,
rebond de masse), **taguer chaque composant de la boucle avec la meme
formulation** nommant la boucle entiere et sa contrainte — pas une note
isolee sur un seul composant. Sinon, un placement qui respecte la contrainte
sur une seule piece laisse la boucle grande si une autre piece derive.

Exemple reel : la boucle d'impulsion `L1-D1-F2-J3` (vers la batterie, di/dt
eleve) recoit la meme formulation sur ses 4 composants ; `L1`, pivot entre
cette boucle et celle du decouplage `VCHG` (`C3-C4-C5-C6-L1`), porte les deux :

```jsonc
{
  "L1": {"properties": {"Placement": {"hide": true, "value":
    "LOOP CRITIQUE - pivot de 2 boucles a surface minimale : charge C3-C4-C5-C6-L1-Q1-R6-GND, et decharge L1-D1-F2-J3 (vers batterie)"}}},
  "D1": {"properties": {"Placement": {"hide": true, "value":
    "LOOP CRITIQUE - boucle d'impulsion L1-D1-F2-J3 (vers batterie), surface minimale imperative (di/dt eleve)"}}},
  "F2": {"properties": {"Placement": {"hide": true, "value":
    "LOOP CRITIQUE - boucle d'impulsion L1-D1-F2-J3 (vers batterie), surface minimale imperative (di/dt eleve)"}}},
  "J3": {"properties": {"Placement": {"hide": true, "value":
    "LOOP CRITIQUE - boucle d'impulsion L1-D1-F2-J3 (vers batterie), surface minimale imperative (di/dt eleve)"}}}
}
```

## Regle 3 — verifier qu'aucune broche utile ne repose sur un net anonyme avant de synchroniser vers le PCB

Un fil ou un label reliant deux broches sans qu'aucun `label`/`global_label`
explicite ne soit pose dessus reste electriquement valide dans KiCad — le
schema le nomme automatiquement `Net-(REF-PIN)` (ex. `Net-(U3-IN)`,
`Net-(Q1-B)`). L'ERC ne signale rien : ce n'est pas une erreur de
connectivite.

**Mais `sync_schematic_to_board` (l'outil MCP qui importe le schema dans le
PCB, equivalent F8) echoue silencieusement a resoudre ces noms
auto-generes.** Les broches concernees se retrouvent **sans net du tout**
cote PCB (`net: ""`), invisibles pour le ratsnest, le DRC et l'autorouteur —
sans le moindre avertissement. Une broche sans net n'a par ailleurs aucune
obligation de clearance envers les autres nets pour l'autorouteur : du
cuivre d'un net totalement different peut finir a son contact sans que rien
ne le signale.

Ce bug est resté indetecte pendant tout un projet (`IC202_frequency_meter`) :
4 broches actives de circuits integres (`U3` IN/OUT/~IN, la base de `Q1`,
la broche ADJ de `U2`) sont restees sans aucune piste ni via — dont la
sortie du prescaler, jamais reliee a l'etage suivant — jusqu'a ce qu'une
inspection visuelle du PCB routé révèle une broche visiblement connectée à
trop d'endroits (broches voisines sans clearance).

**Verification a faire avant tout premier `sync_schematic_to_board` (et
apres toute modification touchant des broches de CI) :**

```bash
kicad-cli sch export netlist --output tmp.net le_schema.kicad_sch
```

Puis parser le fichier **en comptant les parentheses** (un `grep`/`find` sur
un nom de net peut capturer par erreur le contenu d'un bloc `(net ...)`
voisin dans ce format S-expression imbrique) pour lister tous les noms de
net commencant par `Net-(` (a l'exclusion de `unconnected-(...)`, qui
designe un NC légitime). Toute broche active d'un composant (CI, transistor,
broche de reglage...) trouvee dans un tel net doit recevoir un label
explicite (`add_schematic_net_label`, snappe sur la broche via
`componentRef`/`pinNumber` — le nom choisi n'a pas d'importance
fonctionnelle, juste le fait qu'il soit explicite). Revalider ensuite que le
scan ne retourne plus aucun `Net-(` sur une broche active, resynchroniser
le PCB, et verifier via `get_component_pads` que les broches concernees ont
bien recu un net (pas `net: ""`).

## Regle 4 — creer le contour du PCB centre sur la feuille, pas cale sur l'origine

Quand un nouveau board est cree depuis le schema (`create_board_from_schematic`)
ou quand un contour est pose/remplace directement (`add_board_outline`,
`replace_board_outline`), le centrer sur la feuille de dessin (la page KiCad,
A4 297x210mm par defaut sauf indication contraire du projet) plutot que de le
caler au coin (0,0) ou de le laisser a un decalage arbitraire issu d'un outil
externe (import DXF, placeur tiers type FD-Autoplacer...).

Calcul : coin bas-gauche du contour = ((largeur_feuille - largeur_board)/2,
(hauteur_feuille - hauteur_board)/2). Ex. board 80x50mm sur feuille A4
297x210mm → coin a (108.5, 80).

Un contour excentre ou colle au bord ne casse rien electriquement, mais rend
`get_board_2d_view`/l'export PDF/SVG moins lisibles (cartouche et cotes mal
places) et oblige a revalider explicitement, a chaque fois, que rien n'est
"hors carte" quand un composant a une coordonnee elevee — verification faite
a plusieurs reprises sur `fd-autoplacer-experiment` (contour importe a
x:17.95-98.05, y:16.95-67.05 au lieu d'etre centre) sans que ce soit jamais
un vrai bug, juste une verification recurrente evitable. Verifier le contour
obtenu via `get_board_info` (`size`) et `check_courtyard_overlaps`
(`board_outline_mm`), et recentrer avec `replace_board_outline` si necessaire.

## Regle 5 — juste avant le routage, verifier si une rotation raccourcit le ratsnest

Pour un composant a 2, 3 ou 4 broches (resistance, condensateur, diode,
transistor, petit connecteur...), l'orientation posee par le placement
initial (manuel ou FD-Autoplacer) n'est pas forcement celle qui minimise la
longueur des fils que l'autorouteur devra tirer. Tourner le composant de
90/180/270 deg peut rapprocher chaque broche du point le plus proche de son
net **sans deplacer le composant ni changer sa connectivite** — un gain
gratuit avant de lancer l'autoroutage.

**Constat verifie sur `fd-autoplacer-experiment`** (session du 2026-09-06) :
23 composants sur ~49 (tous a 2/3/4 broches) gagnaient en longueur de
ratsnest via une simple rotation cardinale, de -0.2mm a -6.5mm. Confirme
noir sur blanc pour 3 exemples cites par l'utilisateur : `R18` (0 deg -> 180
deg, -1.88mm), `R19` (-90 deg -> 0 deg, -0.48mm), `C10` (180 deg -> 270 deg,
-2.01mm).

**Point important pour un net tres connecte (GND, alimentations...) :** le
ratsnest visible a l'ecran relie chaque broche au point le PLUS PROCHE du
meme net, pas a tous les points a la fois. La verification doit donc
raisonner de la meme facon — pour chaque broche, chercher la distance a la
pastille la plus proche portant le meme net (peu importe combien d'autres
points existent ailleurs sur ce net), pas une somme ou une moyenne sur tout
le net. Meme raisonnement pour toute equipotentielle connectee en de
nombreux points (pas seulement GND).

**Outil** : `check_rotation_ratsnest.py`, dans ce meme dossier de skill.
Parse directement le `.kicad_pcb` (aucune dependance a pcbnew/MCP KiCad —
utile si le backend MCP est indisponible), calcule les positions absolues de
pastilles, et teste les 4 orientations cardinales pour chaque composant
2/3/4 broches :

```bash
python ~/.claude/skills/conception-electronique-kicad/check_rotation_ratsnest.py board.kicad_pcb
# ou cible sur quelques refs :
python ~/.claude/skills/conception-electronique-kicad/check_rotation_ratsnest.py board.kicad_pcb --refs R18,R19,C10
```

A lancer **avant** l'autoroutage (ou juste apres avoir efface les pistes
existantes — le script ignore de toute facon les pistes deja posees et ne
regarde que les positions de pastilles + noms de net). Appliquer les
rotations proposees via `rotate_component`/`batch_move_components`, puis
**revalider avec `check_courtyard_overlaps`** avant de router : une rotation
qui raccourcit le ratsnest peut faire chevaucher un voisin, le script ne le
detecte pas.

**Une rotation peut aussi degrader le DRC electrique, pas seulement le
courtyard** : sur `fd-autoplacer-experiment`, appliquer 23 rotations d'un
coup (aucun chevauchement de courtyard) a quand meme fait passer le DRC de
0 a 12 erreurs apres reroutage — pas a cause du deplacement (les composants
ne bougent pas), mais parce qu'une pastille `roundrect` asymetrique (coin
arrondi seulement de certains cotes, typique du marquage broche 1) presente
un profil de cuivre different selon l'orientation : tourner le composant
change quel cote de la pastille fait face au voisin, et peut reduire un
clearance auparavant confortable a moins de 0.2mm sans que rien n'ait
"bouge" au sens courtyard. Chaque cas s'est resolu en devinant/contournant
localement (reroutage manuel autour de la zone signalee), jamais par un
simple nouvel autoroutage (Freerouting reproduit la meme geometrie tendue de
facon deterministe). **Piege verifie deux fois lors de cette correction** :
une piste ajoutee pour contourner un point precis peut elle-meme frôler un
via ou une pastille *au milieu de son trace*, pas seulement a ses extremites
— si un `run_drc` post-fix pointe encore une `shorting_items`/`clearance`
proche (mais pas exactement sur) le point qu'on vient de corriger, chercher
un item d'un autre net au plus proche du **segment entier** nouvellement
trace (distance point-segment sur toute sa longueur), pas seulement pres de
ses deux bouts.

## Regle 6 — detecter systematiquement les pistes arrivant sur la mauvaise face d'une pastille SMD

L'autorouteur (et une reroute manuelle un peu rapide) peut dessiner une piste
qui se termine exactement aux bonnes coordonnees X/Y d'une pastille SMD mais
sur la face de cuivre OPPOSEE a celle ou la pastille existe reellement (une
pastille SMD n'a du cuivre que sur une seule face). Visuellement/en
coordonnees ca a l'air connecte ; electriquement, non — il manque un via pour
franchir l'epaisseur du board. Ce cas ne se voit pas au premier coup d'oeil
sur `run_drc` : il ressort seulement comme un `track_dangling`
("Track has unconnected end") au milieu d'une quinzaine d'autres avertissements
sans gravite apparente, jamais comme une erreur bloquante.

**Constat verifie sur `fd-autoplacer-experiment`** (session du 2026-09-06) :
l'utilisateur a repere le motif a l'oeil sur `C11` et `R19` ("la trace est au
bon endroit mais sur l'autre face"). Un script systematique sur tout le board
a trouve **15 pastilles** dans ce cas (`R19`x2, `C7`x2, `R14`x2, `R2`, `R13`x2,
`C5`x2, `R3`, `U1`, `C11`x2) — corrigees en une seule passe par simple ajout
d'un via a chaque emplacement signale (`add_via` a la position exacte de la
pastille, sur le net concerne). Resultat : DRC passe de plusieurs `track_dangling`
non-diagnostiques a 0 erreur et 1 seul warning residuel.

**Outil** : `find_wrong_face_stubs.py`, dans ce meme dossier de skill. Parse
le `.kicad_pcb` (pastilles avec position absolue + face de montage, pistes,
vias existants) et rapporte toute pastille SMD dont le net a une piste qui
arrive exactement a ses coordonnees mais sur la face opposee, sans qu'un via
ne comble deja l'ecart :

```bash
python ~/.claude/skills/conception-electronique-kicad/find_wrong_face_stubs.py board.kicad_pcb
```

A lancer **apres tout autoroutage ou reroutage manuel**, avant de considerer
le routage termine — en complement de `run_drc`, pas a sa place (ce script ne
detecte que ce motif precis, pas les vrais court-circuits/clearances).

**Piege de calcul rencontre en ecrivant ce script** : la rotation d'une
empreinte KiCad se compose avec les coordonnees locales des pastilles selon
`x' = x*cos(theta) + y*sin(theta)`, `y' = y_compo - x*sin(theta) + y*cos(theta)`
(rotation horaire dans le repere Y-vers-le-bas du PCB) — **pas** la formule
trigonometrique standard `x' = x*cos - y*sin`, `y' = x*sin + y*cos` (sens
anti-horaire, repere Y-vers-le-haut). Utiliser la mauvaise formule permute
silencieusement les positions calculees de deux broches d'un composant tourne
a 90/270 deg (confirme sur `C11`, `R2`, `R3`, `R13` : leurs pastilles
n'apparaissaient pas dans les resultats avant correction de la formule, alors
qu'elles y sont bien apres). `check_rotation_ratsnest.py` (Regle 5) contenait
la meme erreur — sans consequence pratique pour son usage (les deux broches
d'un composant symetrique sont sommees, l'inversion de leurs positions ne
change pas le total), mais corrigee par coherence.

## Prefixe de tri

Prefixer systematiquement la valeur par un mot-cle constant pour pouvoir
retrouver toutes les contraintes d'un type donne sans relire tout le schema :

- `LOCAL - ...` : proximite d'une broche ou d'un point d'entree precis.
- `LOOP CRITIQUE - ...` : surface de boucle a minimiser sur plusieurs
  composants lies.

## A ne pas oublier au moment du placement/routage

Poser les proprietes ne fait rien tout seul. Quand le meme agent (ou un
autre) passe au placement/routage du PCB, **demander explicitement** de
respecter les proprietes `Placement` deja posees — sans quoi le placement se
fera selon les regles habituelles (connectivite, encombrement des
empreintes) sans savoir qu'une contrainte de conception existe. Un moyen
simple de les relire en bloc : `list_schematic_components` puis
`get_schematic_component` sur chaque reference d'interet, ou un filtrage
direct du texte du `.kicad_sch` sur `(property "Placement"`.

## Articulation avec kicad-schematic-readability

Les deux competences sont complementaires, pas redondantes :

- **kicad-schematic-readability** traite ce qu'un lecteur voit sur la feuille
  de schema — orientation des etiquettes, position des champs Reference/
  Value, absence de chevauchement.
- **conception-electronique-kicad** (celle-ci) traite ce qui doit survivre
  au-dela de la feuille de schema, jusqu'au placement et au routage — via
  une propriete, pas un dessin.

Une note `add_schematic_text` relève de la premiere (elle doit rester lisible
et ne pas chevaucher) ; la propriete `Placement` relève de la seconde (elle
doit exister et etre correcte, sa position dans le fichier n'a pas
d'importance visuelle).

## Projet de reference

`C:\Users\josel\hobby_w\Batteries\chargeur_pb\desulfateur\kicad\desulfateur.kicad_sch`
— toutes les proprietes `Placement` citees ci-dessus y sont posees.
