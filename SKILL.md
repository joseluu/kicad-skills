---
name: kicad-schematic-readability
description: Apply the schematic readability directives when designing or reviewing KiCad schematics. Invoke when the user asks to improve schematic layout, readability, label orientation, or signal flow clarity. KiCad est la base de donnees primaire - modifier directement via les outils MCP mcp__kicad__*.
---

# kicad-schematic-readability - directives de lisibilite schematique

Directives de mise en page valables pour **tous** les projets KiCad de cette
machine. Le fichier `.kicad_sch` est la base de donnees primaire : on le modifie
directement via les outils `mcp__kicad__*`, jamais par un script generateur.

Deux parties : les **5 directives de mise en page**, puis les **regles
d'orientation des etiquettes**, qui sont la source d'erreur la plus frequente et
la moins visible.

---

## Les 5 directives de mise en page

### 1. GND independants

Chaque composant a son propre stub GND. Ne pas relier les GND entre eux par des
fils, sauf si deux composants sont vraiment voisins et que le fil direct est
plus court que deux stubs.

**Pourquoi :** un fil GND qui traverse la feuille ajoute des croisements sans
apporter d'information. La connexion est deja garantie par le nom du net.

### 2. Alimentation en haut, GND en bas

- Etiquettes d'alimentation (VCC, +12V, +5V, +3V3) : au-dessus de la broche.
- Etiquettes GND : en dessous.
- Les condensateurs de decouplage ont leur broche positive vers le haut et leur
  broche de masse vers le bas.

**Connecteurs :** la regle vaut aussi pour l'orientation du symbole lui-meme.
Un connecteur d'alimentation se pose **broche positive en haut, GND en bas**.
Un connecteur de signal dont le retour est une masse (blindage d'un coaxial)
suit la meme regle : la masse descend.

Retourner un connecteur avec un **miroir**, pas avec une rotation : le miroir
inverse l'ordre des broches sans changer le sens dans lequel elles pointent,
donc la broche de signal reste au meme endroit et le cablage existant tient.
Pour un connecteur dont les broches doivent pointer a droite,
`rotate_schematic_component(angle: 0, mirror: "y")` fait l'affaire.

**Piege :** l'outil deplace bien les etiquettes attachees, mais **conserve leur
ancienne orientation**. Apres un miroir, une broche qui pointait vers le haut
pointe vers le bas et son etiquette se lit toujours vers le haut. Recalculer
l'angle et le `justify` de chaque etiquette deplacee (table plus bas). Le script
de controle ne le voit pas : ces etiquettes ne sont pas sur un endpoint de fil.

### 3. Signaux de gauche a droite

Entree a gauche, sortie a droite, traitements successifs alignes sur un bus
horizontal. Les composants shunt (vers GND) sont places sous le bus.

```
RF_IN -> [C_liaison] -> [prescaler] -> [C_liaison] -> [R_base] -> Q1 -> SORTIE
            ^bus                                                  |
         R_terminaison vers GND                              R_base vers GND
```

Aligner les broches concernees sur une meme ordonnee pour obtenir des liaisons
droites : verifier avec `get_schematic_pin_locations` **avant** de cabler, les
broches d'un symbole ne sont pas toujours ou on les croit apres rotation.

### 4. Etiquettes reservees aux signaux utiles

Nommer :
- les rails d'alimentation et GND ;
- les entrees et sorties de bloc ;
- les intermediaires utiles au firmware ou au debug (le point de mesure brut
  avant filtrage, par exemple) ;
- tout signal reliant deux blocs eloignes, qui evite un long fil traversant.

Ne pas nommer les connexions locales deja visibles par un fil direct a
l'interieur d'un bloc.

**Regle de coherence :** a l'interieur d'un bloc on cable par **fils**, entre
blocs on relie par **etiquettes**. Un lecteur voit alors les blocs d'un coup
d'oeil.

### 5. Pas de chevauchement entre symboles

Les corps de deux symboles ne doivent jamais se superposer, meme partiellement.
Deux composants en serie qui partagent un endpoint de fil peuvent se toucher en
un point, c'est acceptable. Tout vrai recouvrement est une erreur.

**Cas typique :** un transistor et sa diode de protection places sur le meme
centre. Deplacer le second a cote, cabler par fils courts horizontaux ou
verticaux.

---

## Orientation des etiquettes de net

C'est le point le plus piegeux : **une etiquette porte deux informations, et
elles doivent etre coherentes entre elles.**

- L'**angle** donne l'axe de lecture. Il sert aussi d'indicateur de direction
  pour `check_label_rotations.py`.
- Le **`justify`** decide de quel cote du point d'ancrage le texte est pose.
  C'est lui seul que KiCad utilise pour placer le texte.

| Angle | `justify` | Le texte se pose |
|---|---|---|
| 0 | `left bottom` | a droite de l'ancrage |
| 90 | `left bottom` | au-dessus |
| 180 | `right bottom` | a gauche |
| 270 | `right bottom` | en dessous |

Le second mot `bottom` decale le texte perpendiculairement pour qu'il ne soit
pas pose sur le fil.

L'angle pointe toujours **a l'oppose** du composant ou du fil, pour que le texte
se lise en s'eloignant du symbole.

### Piege 1 - `justify` absent : texte centre

Sans jeton `justify`, le defaut de KiCad est *centre* : l'etiquette chevauche
son propre point de connexion et le numero de broche.

C'est sournois parce que le symptome est inegal. Une etiquette en bout de stub
a de la place autour d'elle et parait correcte ; la meme etiquette posee
directement sur une broche est visiblement a cheval. Ne pas conclure d'un cas
qui va bien que la convention est bonne.

Corriger en derivant le `justify` de l'angle avec la table ci-dessus :

```python
JUST = {0: "left", 90: "left", 180: "right", 270: "right"}
# pour chaque bloc (label ...) : justify = f"{JUST[angle]} bottom"
```

### Piege 2 - `lint_schematic_cosmetic` passe `orient_labels`

Cette passe du serveur MCP produit une orientation **a 180 degres de la bonne** :
tous les textes se lisent vers l'interieur des symboles. **Ne pas l'utiliser.**

Si elle a ete lancee, ne pas essayer de rattraper en tournant les angles de
180 degres : KiCad normalise l'angle et c'est le `justify` qui decide, donc la
rotation seule ne change rien au rendu. Reappliquer la table.

La passe `hide_pin_names` de ce meme outil est utile et sans danger : elle
masque les noms de broches internes, qui font doublon avec l'etiquette posee
dessus. Penser alors a ajouter la meme directive dans le `.kicad_sym` du projet,
sinon ERC signale un `lib_symbol_mismatch`.

### Piege 3 - broche dont l'extremite tombe dans le corps du symbole

Sur certains symboles (emetteur et collecteur de `Transistor_BJT:Q_NPN_BEC` par
exemple), l'extremite de broche est a l'interieur du rectangle englobant du
corps. Une etiquette posee la se superpose au dessin.

**Fix :** tirer un stub de 5,08 mm vers l'exterieur et poser l'etiquette a son
extremite. C'est aussi la bonne pratique pour une sortie de bloc, qui gagne a
sortir franchement sur le cote.

---

## Placement des champs Reference et Value

`autoplace_schematic_fields` suffit rarement : il empile les champs au meme
decalage, donc ils se superposent des que les composants sont proches, et il ne
tient pas compte de la forme du symbole. Placer a la main selon le type de
symbole, avec les trois regles ci-dessous.

### Symboles rectangulaires a nombreuses broches (U, A, DS...)

**Les deux champs vont au centre du rectangle**, Reference au-dessus du centre,
Value en dessous, decales de 1,27 mm.

Le centre se calcule depuis le rectangle du `lib_symbols`, pas depuis l'origine
du symbole : les deux ne coincident pas toujours. Pour une rotation nulle,
`centre_feuille = (ox + (x1+x2)/2, oy - (y1+y2)/2)` - attention au signe en Y,
la bibliotheque a Y vers le haut et la feuille Y vers le bas.

Prealable : avoir masque les noms de broches (`hide_pin_names`), sinon
l'interieur du rectangle n'est pas libre.

**Ces champs ne doivent porter aucun `justify`** : le defaut centre est
exactement ce qu'on veut. C'est l'inverse des etiquettes de net. Les symboles
KiCad de base arrivent souvent avec un `(justify left)` sur leur `Value` : il
faut le retirer, sinon le texte deborde du rectangle.

### Resistances

**Valeur au centre du corps, repere sur la ligne au-dessus**, les deux suivant
l'orientation du composant. Le corps de `Device:R` fait 2,03 x 5,08 mm centre
sur l'origine, donc la valeur tient dans le rectangle.

| Rotation du symbole | Angle des champs | Valeur | Repere |
|---|---|---|---|
| 0 (verticale) | 90 | a l'origine | origine, `x - 2,54` |
| 90 (horizontale) | 270 | a l'origine | origine, `y - 2,54` |

Pour une resistance verticale le texte se lit de bas en haut : la "ligne
au-dessus" est alors **a gauche**. Pour l'obtenir, faire pivoter mentalement la
page d'un quart de tour dans le sens horaire.

### Condensateurs

**Repere et valeur de part et d'autre du fil du symbole**, a la hauteur juste
en dessous des armatures. Les armatures de `Device:C` s'etendent sur +/-2,03 mm,
d'ou des decalages differents selon l'orientation.

| Rotation | Angle | Valeur | Repere |
|---|---|---|---|
| 0 (vertical) | 0 | `x - 1,27`, `y + 1,905`, `justify right` | `x + 1,27`, `y + 1,905`, `justify left` |
| 90 (horizontal) | 270 | `y + 3,175`, centre | `y - 3,175`, centre |

Le cas vertical **exige** les `justify` : sans eux le texte est centre sur son
ancrage et traverse le fil. Le cas horizontal les refuse, la separation se
faisant par la hauteur.

### Cas general

Quand une serie de composants partage la meme valeur et que la place manque,
masquer les `Value` et reporter l'information dans une note
`add_schematic_text` a cote du bloc. Des que la valeur redevient visible,
penser a alleger la note pour ne pas repeter l'information.

Espacer les composants d'une rangee de **5,08 mm** plutot que 2,54 mm quand
chaque broche recoit une etiquette : a 2,54 mm les textes se touchent.

### Mise en oeuvre

`batch_edit_schematic_components` place les champs mais **n'expose pas
`justify`** : le poser ensuite par edition directe du fichier. Attention, un
bloc `(property ...)` contient `(show_name no)` et `(do_not_autoplace no)`
entre le `(at ...)` et le `(effects ...)` : une regex qui les ignore ne
matchera pas. Utiliser un vrai comptage de parentheses pour isoler le bloc, et
verifier le resultat en relisant le fichier avant de rendre.

Exemple de placement :

```jsonc
{
  "R7": {                                   // resistance horizontale (rot 90)
    "fieldPositions": { "Reference": { "x": 386.08, "y": 157.48, "angle": 270 } },
    "properties":     { "Value": { "value": "220R",
                                   "x": 386.08, "y": 160.02, "angle": 270,
                                   "hide": false } }
  }
}
```

**Regle transverse a ne pas oublier : l'angle d'un champ est relatif a la
rotation du symbole**, pas a la feuille. L'angle rendu vaut
`(angle_champ + rotation_symbole) mod 360`. Sur un symbole place a
`rotation: 90`, il faut donc ecrire **270** pour obtenir un texte horizontal ;
0 donnerait un texte vertical.

---

## Pieges de connectivite des outils MCP

Ces outils peuvent modifier le netlist sans le dire. Toujours verifier apres.

- **`batch_connect` avec `replace: true`** peut creer des **fils parasites** :
  quand il trouve "une etiquette du meme net en vis-a-vis a proximite", il
  trace un fil au lieu de poser une etiquette. Sur des composants alignes a pas
  serre, cela court-circuite des nets voisins. Verifier avec
  `list_schematic_wires` et chercher les segments perpendiculaires inattendus.
- **`move_schematic_component`** deplace les etiquettes posees sur les broches
  ("N net label(s) moved to stay attached") et peut attraper celles du voisin
  quand les composants sont proches. Relire `list_schematic_labels` apres tout
  deplacement, et verifier qu'aucune position ne porte deux etiquettes.
- **`batch_move_components` est un outil PCB**, pas schematique. Sur un schema
  il repond "Component not found". Utiliser `move_schematic_component`, un
  appel par composant.
- **`run_erc`** depasse souvent le delai de 30 s du serveur MCP. Passer par
  `kicad-cli` directement, c'est la meme verite et c'est plus rapide.

---

## Verification obligatoire

Trois controles, dans cet ordre. Les deux premiers ne remplacent pas le
troisieme.

### 1. Les scripts

```bash
python check_label_rotations.py  <chemin>.kicad_sch
python check_symbol_overlap.py   <chemin>.kicad_sch
```

Dans `C:\Users\josel\hobby_w\Batteries\alerteur_batterie\kicad\`. Ils acceptent
un chemin de schema en argument.

**Limite a connaitre :** `check_label_rotations.py` ne lit que l'**angle** et ne
verifie que les etiquettes posees sur un endpoint de fil. Il ne voit ni un
`justify` absent ou incoherent, ni les etiquettes posees directement sur une
broche. Il peut donc annoncer "OK" sur un schema visuellement faux.

### 2. ERC et netlist de reference

```bash
kicad-cli sch erc --output erc.rpt --severity-error --severity-warning f.kicad_sch
kicad-cli sch export netlist --format kicadxml --output net.xml f.kicad_sch
```

Garder un `net.xml` de reference une fois la connectivite validee, puis
rediffer apres chaque retouche cosmetique :

```python
import xml.etree.ElementTree as ET
def nets(f):
    r = ET.parse(f).getroot()
    return {n.get('name'): tuple(sorted(f"{x.get('ref')}.{x.get('pin')}" for x in n))
            for n in r.find('nets')}
a, b = nets('net_ref.xml'), nets('net_now.xml')
print('IDENTIQUE' if a == b else [k for k in set(a) | set(b) if a.get(k) != b.get(k)])
```

Un `lib_symbol_mismatch` sur une bibliotheque locale au projet est cosmetique :
si un diff du symbole montre qu'il est semantiquement identique, ne pas
poursuivre.

### 3. Rendu visuel zoome - non negociable

C'est le seul controle qui voit un `justify` faux. Verifier au moins un cas de
chaque configuration : broche horizontale a gauche du symbole, broche
horizontale a droite, broche verticale en haut, broche verticale en bas,
etiquette en bout de stub.

`cairosvg` ne fonctionne pas sur cette machine (pas de `libcairo`). Passer par
un export PDF puis PyMuPDF :

```python
import pymupdf
p = pymupdf.open("f.pdf")[0]
sx, sy = p.rect.width / 420.0, p.rect.height / 297.0   # A3 : mm -> points
p.get_pixmap(dpi=500,
             clip=pymupdf.Rect(x0*sx, y0*sy, x1*sx, y1*sy)).save("zoom.png")
```

Les coordonnees de decoupe sont alors directement celles du schema, en mm.

---

## Grille

La grille de connexion est fixee a **1,27 mm**. Placer les origines de symboles
sur 2,54 mm. Une seule coordonnee hors grille peut casser le placement des
jonctions de toute la feuille. Controler avec `lint_offgrid` (`fix: true` pour
corriger les ecarts inferieurs a 0,5 mm).

---

## Projet de reference

`C:\Users\josel\hobby_w\Batteries\alerteur_batterie\kicad\output\alerteur_batterie.kicad_sch`

Exemple recent applique de bout en bout, y compris les pieges d'etiquettes :
`C:\Users\josel\hobby_w\cricri\IC202_frequency_meter\kicad\` (voir la section
"Regles de lisibilite appliquees" de son README).
