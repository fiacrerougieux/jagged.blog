#!/usr/bin/env python3
"""A caffeine molecule in PDB: readable, the right atoms, a flat ring system, sane bonds."""
import sys
import numpy as np
from _grade import finish

src, out = sys.argv[1], sys.argv[2]
r = {"checks": {}}
from rdkit import Chem, RDLogger
from rdkit.Chem.rdMolDescriptors import CalcMolFormula
RDLogger.DisableLog("rdApp.*")
mol = Chem.MolFromPDBFile(src, removeHs=False, sanitize=False, proximityBonding=True)
r["checks"]["parses"] = mol is not None and mol.GetNumAtoms() > 0
if r["checks"]["parses"]:
    try:
        mol.UpdatePropertyCache(strict=False)
        r["formula"] = CalcMolFormula(mol)
    except Exception as e:
        r["formula"] = f"unavailable: {e}"
    elems = sorted(a.GetSymbol() for a in mol.GetAtoms())
    count = {e: elems.count(e) for e in set(elems)}
    r["atoms"] = count
    r["checks"]["atoms_C8H10N4O2"] = count == {"C": 8, "H": 10, "N": 4, "O": 2}
    conf = mol.GetConformer()
    ring = [i for i, a in enumerate(mol.GetAtoms()) if a.GetSymbol() in "CN" and a.IsInRing()]
    if len(ring) >= 9:
        P = np.array([list(conf.GetAtomPosition(i)) for i in ring]); P -= P.mean(0)
        rms = float(np.linalg.svd(P)[1][-1] / np.sqrt(len(P)))
        r["ring_plane_rms_A"] = round(rms, 3)
        r["checks"]["ring_system_flat"] = rms < 0.1
    else:
        r["checks"]["ring_system_flat"] = False
    heavy = [b for b in mol.GetBonds() if b.GetBeginAtom().GetSymbol() != "H" and b.GetEndAtom().GetSymbol() != "H"]
    L = [(conf.GetAtomPosition(b.GetBeginAtomIdx()) - conf.GetAtomPosition(b.GetEndAtomIdx())).Length() for b in heavy]
    r["heavy_bond_lengths_A"] = [round(min(L), 2), round(max(L), 2)] if L else None
    r["checks"]["bond_lengths_plausible"] = bool(L) and 1.15 < min(L) and max(L) < 1.6 and len(heavy) == 15
finish(r, out)
