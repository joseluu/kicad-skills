# kicad-schematic-readability

Skill [Claude Code](https://claude.com/claude-code) regroupant les regles de
mise en page qui rendent un schema KiCad lisible, et surtout les pieges qui
font qu'un schema parait correct alors qu'il ne l'est pas.

Le contenu est dans [`SKILL.md`](SKILL.md).

## Ce que couvre le skill

- **5 directives de mise en page** : masses independantes, alimentation en haut
  et masse en bas, signaux de gauche a droite, etiquettes reservees aux signaux
  utiles, aucun chevauchement de symboles.
- **Orientation des etiquettes de net.** Une etiquette porte un angle *et* un
  `justify`, et les deux doivent etre coherents. C'est la source d'erreur la
  plus frequente : sans `justify`, KiCad centre le texte sur le point de
  connexion, ou il chevauche le numero de broche.
- **Placement des champs Reference et Value**, avec une regle par famille de
  symbole : boitiers rectangulaires, resistances, condensateurs.
- **Pieges de connectivite des outils MCP**, qui peuvent modifier le netlist
  sans le signaler.
- **Une procedure de verification en trois temps**, dont le point important est
  qu'aucun script ne remplace un rendu visuel zoome.

## Installation

Ce dossier fait partie du repo [kicad-skills](https://github.com/joseluu/kicad-skills) —
voir son [README](../README.md) pour l'installation (clone + lien symbolique
ou jonction vers `~/.claude/skills/kicad-schematic-readability`).

Le skill s'invoque ensuite par son nom, ou automatiquement quand la tache porte
sur la lisibilite d'un schema.

## Portee et limites

Ces regles ont ete etablies sur les projets de leur auteur et refletent ses
conventions ; elles ne pretendent pas etre un standard. Le skill est ecrit en
francais et sans accents, pour eviter tout probleme d'encodage.

Quelques elements sont specifiques a la machine d'origine et sont a adapter :

- les chemins absolus vers les deux scripts de validation
  `check_label_rotations.py` et `check_symbol_overlap.py`, qui vivent dans un
  autre projet ;
- la methode de rendu, qui contourne l'absence de `libcairo` en passant par un
  export PDF puis PyMuPDF ;
- les chemins des projets cites en reference.

Les regles de fond, elles, valent pour n'importe quelle installation KiCad.
Verifie sur KiCad 10.

## Origine

Ces regles ont ete extraites au fil de deux projets, en corrigeant a chaque
fois une erreur reelle constatee sur un rendu. Le projet
[ic202-frequency-meter](https://github.com/joseluu/ic202-frequency-meter) en est
une application de bout en bout.
