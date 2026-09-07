# kicad-skills

Trois skills [Claude Code](https://claude.com/claude-code) pour la conception
electronique sous KiCad, du choix des composants jusqu'au routage :

| Dossier | Portee |
|---|---|
| [`conception-electronique-kicad/`](conception-electronique-kicad/) | Intention de conception a documenter sur le schema (role de chaque decouplage, boucles critiques) pour qu'elle survive jusqu'au placement/routage ; verification du stock PartsBox avant de figer une reference. |
| [`kicad-schematic-readability/`](kicad-schematic-readability/) | Regles de mise en page d'un schema lisible : orientation des etiquettes de net, placement des champs Reference/Value par famille de symbole, pieges de connectivite des outils MCP. |
| [`kicad-pcb-placement/`](kicad-pcb-placement/) | Methode de premier placement d'un board a partir d'un schema cable : contraintes dures verifiees par outil, repartition du reste par proximite. |

Chaque dossier est un skill autonome (son propre `SKILL.md`) ; ils se
completent dans l'ordre du tableau mais s'invoquent independamment.

## Installation

Cloner le repo une fois, puis faire pointer chaque skill vers son sous-dossier
dans `~/.claude/skills/` — par lien symbolique sous Linux/macOS, par jonction
sous Windows (`mklink /J`, pas besoin de droits admin, contrairement au lien
symbolique `/D`).

```bash
git clone https://github.com/joseluu/kicad-skills.git ~/hobby_w/kicad-skills
```

**Linux/macOS :**
```bash
for s in conception-electronique-kicad kicad-schematic-readability kicad-pcb-placement; do
  ln -s ~/hobby_w/kicad-skills/$s ~/.claude/skills/$s
done
```

**Windows (cmd, pas admin requis) :**
```cmd
mklink /J "%USERPROFILE%\.claude\skills\conception-electronique-kicad" "%USERPROFILE%\hobby_w\kicad-skills\conception-electronique-kicad"
mklink /J "%USERPROFILE%\.claude\skills\kicad-schematic-readability"   "%USERPROFILE%\hobby_w\kicad-skills\kicad-schematic-readability"
mklink /J "%USERPROFILE%\.claude\skills\kicad-pcb-placement"           "%USERPROFILE%\hobby_w\kicad-skills\kicad-pcb-placement"
```

Chaque skill s'invoque ensuite par son nom, ou automatiquement quand la tache
correspond a sa description.

## Portee et limites

Ces regles refletent les conventions et l'installation KiCad de leur auteur
(verifie sur KiCad 10) ; elles ne pretendent pas etre un standard. Ecrites en
francais et sans accents, pour eviter tout probleme d'encodage. Quelques
chemins references dans les skills sont specifiques a la machine d'origine et
sont a adapter.

## Origine

Extraites au fil de plusieurs projets, en corrigeant a chaque fois une erreur
reelle constatee. Le projet
[ic202-frequency-meter](https://github.com/joseluu/ic202-frequency-meter) en
est une application de bout en bout.
