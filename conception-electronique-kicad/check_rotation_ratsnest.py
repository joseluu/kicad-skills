#!/usr/bin/env python3
"""
check_rotation_ratsnest.py - detecte, avant routage, les composants a 2/3/4
broches dont une rotation a 90/180/270 raccourcirait le ratsnest.

Lit directement le fichier .kicad_pcb (parsing S-expression maison, pas
besoin de pcbnew/MCP KiCad) : pour chaque footprint de 2, 3 ou 4 pastilles,
calcule la position absolue de chaque broche, puis la distance a la
pastille la PLUS PROCHE portant le meme net ailleurs sur le board (peu
importe le nombre total de points sur ce net — pour un net tres connecte
comme GND, c'est cette distance au point le plus proche qui correspond a la
ligne de ratsnest visible a l'ecran, pas une somme sur tous les points).
Compare la longueur totale (somme sur les broches du composant) a ce
qu'elle serait apres rotation de +90/+180/+270 par rapport a l'orientation
actuelle, et rapporte les composants ou une rotation gagne au moins
`--min-gain` mm.

Usage:
    python check_rotation_ratsnest.py board.kicad_pcb [--min-gain 0.1] [--refs R18,R19,C10]

Limites connues :
- Ignore les pistes deja posees : le ratsnest est recalcule a partir des
  positions de pastilles et des noms de net uniquement, comme si rien
  n'etait encore routé. A utiliser AVANT de lancer l'autoroutage (ou apres
  avoir efface les pistes), pas pour re-optimiser un routage existant.
- Ne teste que des quarts de tour (0/90/180/270) — suffisant pour les
  empreintes generees par KiCad (résistances, condensateurs, connecteurs,
  transistors a 3 broches...), qui sont presque toujours posees a un multiple
  de 90 deg au depart.
- Ne verifie aucun DRC/chevauchement : une rotation qui gagne en longueur de
  ratsnest peut faire chevaucher un composant voisin. Toujours repasser
  check_courtyard_overlaps / run_drc apres application.
"""
import sys
import math
import argparse
from collections import defaultdict


def tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in '()':
            tokens.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == '\\' and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(('str', ''.join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def parse(tokens):
    pos = [0]

    def rd():
        tok = tokens[pos[0]]
        pos[0] += 1
        if tok == '(':
            lst = []
            while tokens[pos[0]] != ')':
                lst.append(rd())
            pos[0] += 1
            return lst
        elif isinstance(tok, tuple):
            return tok[1]
        else:
            return tok

    exprs = []
    while pos[0] < len(tokens):
        exprs.append(rd())
    return exprs


def find_all(node, tag):
    out = []

    def walk(n):
        if isinstance(n, list) and n:
            if n[0] == tag:
                out.append(n)
                return
            for c in n:
                walk(c)

    walk(node)
    return out


def find_first(node, tag):
    if isinstance(node, list):
        for c in node:
            if isinstance(c, list) and c and c[0] == tag:
                return c
    return None


def load_footprints(pcb_path):
    text = open(pcb_path, encoding='utf-8').read()
    tree = parse(tokenize(text))
    root = tree[0]
    comps = []
    for fp in find_all(root, 'footprint'):
        at = find_first(fp, 'at')
        fx, fy, frot = 0.0, 0.0, 0.0
        if at:
            fx, fy = float(at[1]), float(at[2])
            frot = float(at[3]) if len(at) > 3 else 0.0
        ref = None
        for prop in fp:
            if isinstance(prop, list) and prop and prop[0] == 'property' \
                    and len(prop) > 2 and prop[1] == 'Reference':
                ref = prop[2]
        if ref is None:
            for t in fp:
                if isinstance(t, list) and t and t[0] == 'fp_text' \
                        and len(t) > 2 and t[1] == 'reference':
                    ref = t[2]
        pads = []
        for pad in fp:
            if isinstance(pad, list) and pad and pad[0] == 'pad':
                padat = find_first(pad, 'at')
                px, py = (float(padat[1]), float(padat[2])) if padat else (0.0, 0.0)
                netnode = find_first(pad, 'net')
                netname = netnode[1] if netnode and len(netnode) > 1 else None
                pads.append({'num': pad[1], 'lx': px, 'ly': py, 'net': netname})
        comps.append({'ref': ref, 'x': fx, 'y': fy, 'rot': frot, 'pads': pads})
    return comps


def abs_pad_pos(comp, pad, rot_override=None):
    rot = comp['rot'] if rot_override is None else rot_override
    theta = math.radians(rot)
    ct, st = math.cos(theta), math.sin(theta)
    lx, ly = pad['lx'], pad['ly']
    # KiCad footprint rotation: clockwise-positive in board Y-down coords
    return (comp['x'] + lx * ct + ly * st,
            comp['y'] - lx * st + ly * ct)


def build_net_index(comps):
    net_pads = defaultdict(list)
    for ci, comp in enumerate(comps):
        for pi, pad in enumerate(comp['pads']):
            if not pad['net']:
                continue
            ax, ay = abs_pad_pos(comp, pad)
            net_pads[pad['net']].append((ci, ax, ay))
    return net_pads


def nearest_dist(net_pads, net, ci, ax, ay):
    best = None
    for (oci, ox, oy) in net_pads[net]:
        if oci == ci:
            continue
        d = math.hypot(ax - ox, ay - oy)
        if best is None or d < best:
            best = d
    return best


def total_len(comps, net_index, ci, rot_override=None):
    comp = comps[ci]
    total, n = 0.0, 0
    for pad in comp['pads']:
        if not pad['net']:
            continue
        ax, ay = abs_pad_pos(comp, pad, rot_override=rot_override)
        d = nearest_dist(net_index, pad['net'], ci, ax, ay)
        if d is not None:
            total += d
            n += 1
    return total, n


def analyze(pcb_path, refs=None, min_gain=0.1):
    comps = load_footprints(pcb_path)
    net_index = build_net_index(comps)
    results = []
    for ci, comp in enumerate(comps):
        if len(comp['pads']) not in (2, 3, 4):
            continue
        if refs and comp['ref'] not in refs:
            continue
        cur_total, n_connected = total_len(comps, net_index, ci)
        if n_connected == 0:
            continue
        best_rot, best_total = comp['rot'], cur_total
        for delta in (90, 180, 270):
            test_rot = (comp['rot'] + delta) % 360
            t, _ = total_len(comps, net_index, ci, rot_override=test_rot)
            if t < best_total - 1e-6:
                best_total, best_rot = t, test_rot
        gain = cur_total - best_total
        if best_rot != comp['rot'] and gain >= min_gain:
            results.append({
                'ref': comp['ref'], 'rot_cur': comp['rot'], 'rot_best': best_rot,
                'len_cur': cur_total, 'len_best': best_total, 'gain_mm': gain,
            })
    results.sort(key=lambda r: -r['gain_mm'])
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board', help='chemin du .kicad_pcb')
    ap.add_argument('--refs', help='limiter a ces references, separees par des virgules')
    ap.add_argument('--min-gain', type=float, default=0.1,
                     help='gain minimal en mm pour etre rapporte (defaut 0.1)')
    args = ap.parse_args()
    refs = args.refs.split(',') if args.refs else None
    results = analyze(args.board, refs=refs, min_gain=args.min_gain)
    print(f"{'ref':8} {'rot_cur':>8} {'rot_best':>9} {'len_cur':>9} {'len_best':>9} {'gain_mm':>9}")
    for r in results:
        print(f"{r['ref']:8} {r['rot_cur']:8.1f} {r['rot_best']:9.1f} "
              f"{r['len_cur']:9.3f} {r['len_best']:9.3f} {r['gain_mm']:9.3f}")
    if not results:
        print("(aucune rotation utile trouvee au-dessus du seuil)")


if __name__ == '__main__':
    main()
