# kicad-pcb-placement — placement initial d'un PCB via MCP

Methode pour realiser le premier passage de placement d'un board KiCad a
partir d'un schema deja cable, avec des contraintes dures verifiees par
outil (pas a l'oeil) et une repartition du reste par proximite.

Complementaire de **conception-electronique-kicad** (qui pose les
contraintes de placement dans la propriete `Placement` en amont, sur le
schema) et de **kicad** (reference generale des outils MCP). Ce skill ne
traite que la phase de *placement initial* — pas le routage.

## Principe general

Le placement initial n'est pas le placement final. Il n'a que deux
obligations :

1. **Contraintes imposees par l'utilisateur** (emplacement/orientation d'un
   connecteur, d'un module) — dures, a respecter exactement.
2. **Aucun chevauchement de courtyard** — dure, verifiee par outil, jamais
   a l'oeil ni par calcul manuel de bounding box.

Tout le reste (longueur des pistes hors alimentation/GND, respect des
proprietes `Placement` du schema) est une **minimisation**, pas une
contrainte dure : un placement qui les respecte a peu pres est suffisant,
il sera raffine dans des passes d'optimisation ulterieures (orientation
des broches pour le routage, etc.). Ne pas perdre de temps a la perfection
du premier jet.

## Sequence

### 1. Poser les deux questions obligatoires a l'utilisateur

Avant tout outil, demander explicitement :

- **Taille et orientation du board** (largeur x hauteur, paysage/portrait).
  C'est une decision physique (boitier, panel) que seul l'utilisateur peut
  trancher — ne pas la deviner depuis la surface des empreintes.
- **Quels composants ont un emplacement impose** (contrainte dure) et
  lequel. Typiquement les connecteurs de bord (alimentation, RF, nappe) et
  les modules montes sur picots dont l'orientation compte (ex. cote USB/FTDI
  d'un Arduino Pro Mini). Donner a l'utilisateur la liste des connecteurs
  presents sur le schema pour qu'il reponde precisement (ref + bord/coordonnee
  + orientation si pertinent), plutot que de lui faire deviner une reponse
  parmi des options generiques.

Si la reponse est « je precise moi-meme », ce n'est pas un refus de
repondre : attendre la precision exacte (ref par ref) avant de tracer quoi
que ce soit — ne pas improviser des coordonnees a la place de l'utilisateur.

### 2. Tracer le contour et importer la netlist

```
add_board_outline(shape="rectangle", params={x:0,y:0,width:W,height:H,unit:"mm"})
sync_schematic_to_board(schematicPath, boardPath)   # equivalent F8, importe footprints + nets
save_board(force=true)   # le swig backend refuse parfois l'auto-save si le mtime a bouge
                         # entre deux appels (outline puis sync) — c'est notre propre ecriture,
                         # pas une modification externe : force=true est legitime ici.
```

Verifier ensuite `get_component_list` : tous les footprints doivent
apparaitre, empiles a (0,0) — c'est l'etat de depart normal. Un composant
absent (`footprints_skipped`) est normal pour un symbole marque
`on_board: no` (ex. un afficheur deporte en bout de nappe) — ne pas
chercher a le forcer sur le board.

### 3. Placer les composants a emplacement impose — et VERIFIER l'orientation par la mesure, pas par la geometrie du symbole

Convention x/y : origine en haut a gauche, Y croit vers le bas (comme
KiCad). "En haut" = petit Y, "a gauche" = petit X.

**Piege** : quand l'utilisateur impose une orientation relative (« cote USB
a gauche », « connecteur vers le bas »...), ne pas deduire la rotation
necessaire par un raisonnement geometrique sur les coordonnees de pins du
symbole schema — le mapping symbole -> empreinte peut etre miroir ou
decale (numero de pin identique, position locale differente). **Toujours
verifier empiriquement** :

1. Placer le composant avec une rotation candidate (0, 90, 180 ou 270).
2. `get_pad_position(reference, pad)` sur un pad identifiant sans ambiguite
   le cote concerne (ex. le pad du connecteur FTDI/USB d'un Arduino Pro
   Mini).
3. Comparer sa coordonnee X (ou Y) a celle du centre du composant : plus
   petit = a gauche (resp. en haut), plus grand = a droite (resp. en bas).
4. Si ce n'est pas le cote demande, essayer la rotation opposee (+180°) et
   revalider — ne jamais livrer une orientation non revalidee par mesure.

Exemple reel (ce projet) : un Arduino Pro Mini monte sur une empreinte de
picots seuls (2x12), demande "paysage, USB a gauche" — l'empreinte avait
son axe long par defaut vertical (rot=0). Test a rot=90 : `get_pad_position`
sur le pad du groupe FTDI (broches TXO/RXI/RST/GND, groupees a une
extremite) a confirme une coordonnee X inferieure au centre du composant
-> rot=90 etait la bonne rotation, valide avant de poursuivre.

**Regle par defaut — connecteurs paralleles au bord le plus proche.** Sauf
si l'utilisateur precise explicitement une autre orientation, tout
connecteur (header, borne a vis, jack...) proche d'un bord de carte se place
avec la rangee de broches **parallele** a ce bord — pas perpendiculaire.
Concretement : un connecteur pres d'un bord horizontal (haut/bas) a ses
broches alignees sur X (meme Y pour toutes) ; pres d'un bord vertical
(gauche/droite), alignees sur Y (meme X). Identifier le bord le plus proche
avant de choisir la rotation, puis verifier par `get_component_pads` que les
coordonnees des broches varient bien dans l'axe attendu (toutes la meme Y
pres d'un bord horizontal, toutes le meme X pres d'un bord vertical) — ne
pas se fier a la rotation "par defaut" du footprint, qui est arbitraire
selon la bibliotheque d'origine.

Exemple reel (ce projet) : `J1` (header 1x04) place pres du bord haut avait
ses broches alignees sur Y (perpendiculaires au bord, rotation 0 du
footprint d'origine) — corrige a rotation 90° pour les aligner sur X.
`J2` (2 pastilles) pres du bord gauche avait ses broches alignees sur X —
corrige a rotation 90° pour les aligner sur Y. Dans les deux cas, le
changement d'orientation modifie aussi la forme de la courtyard (large
devient haute et vice-versa) : revalider les voisins immediats avec
`check_courtyard_overlaps` apres coup, pas seulement l'orientation.

### 4. Valider un brouillon de placement complet AVANT de deplacer quoi que ce soit

`check_courtyard_overlaps` accepte un parametre `positions` — un dict
hypothetique `{ref: [x,y,rotation]}` — qui teste des positions **sans
toucher au board**. Construire le tableau de coordonnees complet (tous les
composants, y compris ceux a emplacement impose deja decides) et
l'envoyer en un seul appel :

```
check_courtyard_overlaps(positions={"J1":[40,6,0], "U1":[22,20,0], ...})
```

C'est bien plus fiable et rapide que de calculer les bounding boxes a la
main composant par composant — l'outil connait la geometrie reelle de
chaque empreinte (y compris le texte de reference/valeur si le fab layer
est inclus). Corriger uniquement les paires signalees, puis relancer le
meme appel jusqu'a `overlap_count: 0` et `boundary_violation_count: 0`.

Ne committer sur le board reel qu'une fois ce brouillon propre :

```
batch_move_components(moves={...})   # transactionnel, tout ou rien, sauvegarde par defaut
```

Puis revalider `check_courtyard_overlaps()` (sans `positions`, sur l'etat
reel du board) pour confirmer.

### 5. Repartir le reste par proximite, guide par les proprietes `Placement`

Avant de choisir les coordonnees des composants restants :

- Relire les proprietes `Placement` posees sur le schema (cf.
  conception-electronique-kicad) : grouper physiquement les composants
  partageant un meme groupe `LOCAL - ...` ou `LOOP CRITIQUE - ...`, les
  placer serres les uns aux autres.
- Pour les groupes `LOOP CRITIQUE`, viser une disposition qui permette
  ensuite un cablage direct et court (typiquement en ligne, dans l'ordre du
  chemin electrique nomme dans la propriete) — la boucle sera dessinee au
  routage, mais un mauvais placement initial la rend impossible a raccourcir
  ensuite.
- Pour les nets ordinaires (hors alimentation/GND), une verification
  `get_ratsnest()` donne une longueur estimee par net — utile pour reperer
  un net anormalement long (composant mal place) sans avoir a router pour
  s'en rendre compte. Ne pas optimiser au-dela d'un ordre de grandeur
  raisonnable a ce stade.
- GND et les rails d'alimentation ne sont PAS a minimiser ici — leur
  longueur est traitee par le routage/plan de masse, pas par le placement
  (sauf contrainte de decouplage local deja capturee par une propriete
  `Placement`, qui elle compte).

Reappliquer la sequence outline-libre du point 4 (brouillon `positions` ->
verification -> `batch_move_components`) pour ce reste, par lots plutot que
composant par composant.

### 6. Verification finale

```
check_courtyard_overlaps()   # doit rester a 0/0
run_drc()                     # 0 erreur attendu ; des warnings cosmetiques
                               # (ex. silk_over_copper) sont acceptables a ce
                               # stade, a nettoyer lors du raffinement du
                               # placement/de la serigraphie, pas bloquants
get_ratsnest()                 # sanity-check des longueurs, pas une note de passage
get_board_2d_view(layers=["F.Cu","F.SilkS","Edge.Cuts","F.Fab"])
                               # rendu visuel rapide pour confirmer a l'oeil
                               # ce que les outils ont deja valide numeriquement
```

## Piege outil : `check_courtyard_overlaps` et les empreintes a courtyards multiples

Une empreinte peut porter **plusieurs rectangles de courtyard disjoints**
plutot qu'un seul contour — c'est le cas d'une empreinte "picots seuls" pour
un module monte en hauteur (ex. Arduino Pro Mini sur des barrettes, deux
courtyards separes pour les deux rangees, aucun contour au milieu, expres
pour signaler ce volume comme libre — cf. le point "montage sur picots" du
skill `kicad-schematic-readability`/README de projet).

**`check_courtyard_overlaps` (MCP) evalue le chevauchement a partir de la
bounding box globale de l'empreinte, pas des polygones reels.** Pour une
empreinte a courtyards multiples, ca produit des faux positifs des qu'un
autre composant entre dans cette bounding box — y compris pile au centre du
volume qu'elle est censee laisser libre. Verifie experimentalement : une
resistance placee exactement au centre d'un Arduino Pro Mini sur picots
(rotation 90°) est signalee en "chevauchement" par `check_courtyard_overlaps`
avec la meme magnitude qu'aux bords, alors que `run_drc` (kicad-cli, qui lit
les vrais polygones du fichier `.kicad_pcb`) ne signale rien pour cette paire.

**Regle pratique** : pour toute empreinte connue pour porter plusieurs
courtyards disjoints, ne pas se fier a `check_courtyard_overlaps` pour valider
un placement dans son volume libre — l'outil dira toujours qu'il y a
chevauchement. Utiliser `run_drc` comme verification authoritative a la
place (comme le reste du projet le fait deja pour ERC vs les outils
kicad-skip). Pour le reste du board (empreintes a un seul courtyard, la
grande majorite), `check_courtyard_overlaps` reste fiable et plus rapide a
iterer dessus — reserver `run_drc` en verification finale ou quand une
empreinte a courtyards multiples est impliquee.

## A ne pas faire

- Ne pas deviner la taille du board ou les emplacements imposes a la place
  de l'utilisateur, meme si une estimation "raisonnable" est facile a
  calculer depuis la surface des empreintes.
- Ne pas calculer les non-chevauchements a la main composant par composant
  — `check_courtyard_overlaps(positions=...)` le fait pour un brouillon
  entier en un seul appel, avant tout engagement sur le board reel.
- Ne pas faire confiance a un raisonnement geometrique sur les coordonnees
  de pins du symbole schema pour deduire une rotation d'empreinte demandee
  par l'utilisateur — verifier par `get_pad_position` apres coup.
- Ne pas chercher a optimiser la longueur des nets GND/alimentation des le
  placement initial — c'est le role du routage.
- Ne pas bloquer sur des warnings DRC cosmetiques (silkscreen) au premier
  passage de placement.

## Projet de reference

`C:\Users\josel\hobby_w\cricri\IC202_frequency_meter\kicad\ic202-frequencemetre.kicad_pcb`
— premier placement complet (39 footprints, board 80x70mm) realise avec
cette methode : contraintes imposees (J1 haut-centre, J2 bord gauche, J4
bord droit, A1 Arduino sur picots en paysage avec cote USB a gauche,
verifie par `get_pad_position`), reste reparti par proximite en suivant les
groupes `Placement` (LOCAL decouplage, LOOP CRITIQUE chemin RF et chemin de
comptage), 0 chevauchement de courtyard, 0 erreur DRC. Redo ulterieur (49
footprints, board reduit a 80x50mm apres passage de U3/Q1/J1 en CMS) :
`R7`-`R16` places dans le volume libre sous `A1` (cf. section dediee
ci-dessus sur `check_courtyard_overlaps`), `A1` decale de 3mm, 10 cavaliers
`Jumper:SolderJumper_2_Open` inseres devant `J4` — meme resultat, 0 erreur
`run_drc`.
