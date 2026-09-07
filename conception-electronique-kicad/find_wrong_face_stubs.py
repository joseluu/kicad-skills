"""
Trouve les pistes qui arrivent exactement sur une pastille SMD mais sur la
face OPPOSEE a celle de la pastille (donc electriquement non connectees,
malgre une coincidence XY parfaite) -- meme si aucun via n'existe deja a cet
endroit pour ce net.

Usage: python find_wrong_face_stubs.py board.kicad_pcb [--fix]
Sans --fix : liste les cas trouves.
Avec --fix : n'effectue aucune modification (utiliser les tools MCP pour
             ajouter les vias -- ce script sert seulement au diagnostic).
"""
import sys, re, math

def load(path):
    txt = open(path, encoding='utf-8').read()

    # --- footprints / pads ---
    pads = []  # {ref, num, pos:(x,y), net, layers:set}
    for fm in re.finditer(r'\(footprint\s', txt):
        start = fm.start()
        depth = 0
        i = start
        while True:
            if txt[i] == '(':
                depth += 1
            elif txt[i] == ')':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        block = txt[start:i+1]
        m_at = re.search(r'^\(footprint[^\n]*\n\s*\(layer[^\n]*\n\s*(?:\(uuid[^\n]*\n\s*)?\(at ([\-0-9.]+) ([\-0-9.]+)(?: ([\-0-9.]+))?\)', block)
        if not m_at:
            m_at = re.search(r'\(at ([\-0-9.]+) ([\-0-9.]+)(?: ([\-0-9.]+))?\)', block)
        fx, fy, frot = (float(m_at.group(1)), float(m_at.group(2)), float(m_at.group(3) or 0)) if m_at else (0.0, 0.0, 0.0)
        ref_m = re.search(r'\(property "Reference" "([^"]+)"', block)
        ref = ref_m.group(1) if ref_m else '?'
        for pm in re.finditer(r'\(pad "([^"]+)" (\w+) (\w+)\s*\n\s*\(at ([\-0-9.]+) ([\-0-9.]+)(?: ([\-0-9.]+))?\)', block):
            num, pad_type, pad_shape, px, py, prot = pm.groups()
            px, py = float(px), float(py)
            theta = math.radians(frot)
            ct, st = math.cos(theta), math.sin(theta)
            # KiCad footprint rotation: clockwise-positive in board Y-down coords
            ax = fx + px * ct + py * st
            ay = fy - px * st + py * ct
            sub = block[pm.start():pm.start() + 500]
            net_m = re.search(r'\(net "([^"]*)"\)', sub)
            net = net_m.group(1) if net_m else None
            layers_m = re.search(r'\(layers ((?:"[^"]+"\s*)+)\)', sub)
            layers = set(re.findall(r'"([^"]+)"', layers_m.group(1))) if layers_m else set()
            pads.append({'ref': ref, 'num': num, 'pos': (ax, ay), 'net': net,
                         'layers': layers, 'type': pad_type})

    # --- track segments ---
    segments = []
    for m in re.finditer(
        r'\(segment\s*\(start ([\-0-9.]+) ([\-0-9.]+)\)\s*\(end ([\-0-9.]+) ([\-0-9.]+)\)\s*'
        r'\(width ([\-0-9.]+)\)\s*\(layer "([^"]+)"\)\s*\(net "([^"]+)"\)\s*\(uuid "([^"]+)"\)', txt):
        sx, sy, ex, ey, w, layer, net, uuid = m.groups()
        segments.append({'s': (float(sx), float(sy)), 'e': (float(ex), float(ey)),
                          'layer': layer, 'net': net, 'uuid': uuid})

    # --- vias ---
    vias = []
    for m in re.finditer(
        r'\(via\s*\(at ([\-0-9.]+) ([\-0-9.]+)\)\s*\(size ([\-0-9.]+)\)\s*\(drill ([\-0-9.]+)\)\s*'
        r'\(layers ((?:"[^"]+"\s*)+)\)\s*\(net "([^"]+)"\)', txt):
        x, y, size, drill, layers, net = m.groups()
        vias.append({'pos': (float(x), float(y)), 'net': net})

    return pads, segments, vias


def find_wrong_face_stubs(pads, segments, vias, tol=0.01):
    findings = []
    for pad in pads:
        if pad['net'] is None or pad['net'] == '':
            continue
        if pad['type'] == 'thru_hole':
            continue  # plated through-hole: connects on every copper layer
        pad_cu_layers = {l for l in pad['layers'] if l.endswith('.Cu') and l != '*.Cu'}
        if '*.Cu' in pad['layers'] or len(pad_cu_layers) != 1:
            continue  # wildcard/multi-layer pad: any approaching layer connects fine
        pad_layer = next(iter(pad_cu_layers))
        px, py = pad['pos']

        # a via already bridging this exact point for this net? then it's fine
        has_via = any(
            v['net'] == pad['net'] and math.hypot(v['pos'][0]-px, v['pos'][1]-py) < tol
            for v in vias)
        if has_via:
            continue

        # does a segment of this net actually touch the pad's own layer here?
        connected_on_own_layer = any(
            s['net'] == pad['net'] and s['layer'] == pad_layer and
            (math.hypot(s['s'][0]-px, s['s'][1]-py) < tol or
             math.hypot(s['e'][0]-px, s['e'][1]-py) < tol)
            for s in segments)
        if connected_on_own_layer:
            continue  # properly connected, nothing to do

        # is there a segment of this net ending exactly here but on the WRONG layer?
        wrong_layer_segs = [
            s for s in segments
            if s['net'] == pad['net'] and s['layer'] != pad_layer and
            (math.hypot(s['s'][0]-px, s['s'][1]-py) < tol or
             math.hypot(s['e'][0]-px, s['e'][1]-py) < tol)]
        if wrong_layer_segs:
            findings.append({
                'ref': pad['ref'], 'num': pad['num'], 'net': pad['net'],
                'pos': (px, py), 'pad_layer': pad_layer,
                'wrong_layer': wrong_layer_segs[0]['layer'],
                'seg_uuid': wrong_layer_segs[0]['uuid'],
            })
    return findings


if __name__ == '__main__':
    path = sys.argv[1]
    pads, segments, vias = load(path)
    print(f"{len(pads)} pads, {len(segments)} segments, {len(vias)} vias parsed")
    findings = find_wrong_face_stubs(pads, segments, vias)
    print(f"\n{len(findings)} pastille(s) avec une piste arrivant sur la mauvaise face :\n")
    for f in findings:
        print(f"  {f['ref']}.{f['num']:3} net={f['net']:12} pos=({f['pos'][0]:.4f},{f['pos'][1]:.4f}) "
              f"pastille sur {f['pad_layer']}, piste arrive sur {f['wrong_layer']} (seg {f['seg_uuid']})")
