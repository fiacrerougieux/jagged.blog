#!/usr/bin/env python3
"""Check a SMILES string is perfluorinated caffeine.

Prints a human-readable verdict on stdout (the agent reads this) and writes
a machine-readable verdict as JSON to argv[2].
"""
import json
import sys

TARGET_SMILES = "FC(F)(F)n1cnc2c1c(=O)n(C(F)(F)F)c(=O)n2C(F)(F)F"
# The formula and the N-CF3 count alone pass isomers: 1,3,9-tris(CF3)xanthine
# (fluorinated isocaffeine) has both. Identity is decided by canonical SMILES.
TARGET = "C8HF9N4O2"  # NB: the prompt pack says C8H3F9N4O2, which is wrong.
                       # Caffeine C8H10N4O2 has 9 methyl H + 1 imidazole H;
                       # swapping 3 CH3 for 3 CF3 leaves exactly 1 H.


def main():
    src, out = sys.argv[1], sys.argv[2]
    smiles = open(src).read().strip().splitlines()
    smiles = smiles[0].strip() if smiles else ""
    result = {"pass": False, "checks": {}, "detail": ""}

    if not smiles:
        result["detail"] = "File is empty."
        emit(result, out)
        return

    try:
        from rdkit import Chem
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
    except ImportError as e:
        result["detail"] = f"rdkit unavailable: {e}"
        emit(result, out)
        return

    mol = Chem.MolFromSmiles(smiles)
    result["checks"]["parses"] = mol is not None
    if mol is None:
        result["detail"] = f"RDKit could not parse: {smiles!r}"
        emit(result, out)
        return

    formula = CalcMolFormula(mol)
    result["formula"] = formula
    result["checks"]["formula"] = formula == TARGET

    # Three CF3 groups attached to nitrogen.
    patt = Chem.MolFromSmarts("[#7]C(F)(F)F")
    n_cf3 = len(mol.GetSubstructMatches(patt))
    result["n_cf3_on_n"] = n_cf3
    result["checks"]["three_n_cf3"] = n_cf3 == 3

    # No N-methyl left over.
    methyl = Chem.MolFromSmarts("[#7][CH3]")
    n_me = len(mol.GetSubstructMatches(methyl))
    result["n_methyl_on_n"] = n_me
    result["checks"]["no_n_methyl"] = n_me == 0

    canon = Chem.MolToSmiles(mol)
    result["checks"]["is_target"] = canon == Chem.MolToSmiles(Chem.MolFromSmiles(TARGET_SMILES))

    result["pass"] = all(result["checks"].values())
    if result["pass"]:
        result["detail"] = f"Correct. Formula {formula}, three N-CF3 groups, no N-methyl remaining."
    else:
        problems = []
        if formula != TARGET:
            problems.append(f"formula is {formula}, expected {TARGET}")
        if n_cf3 != 3:
            problems.append(f"found {n_cf3} N-CF3 groups, expected 3")
        if n_me:
            problems.append(f"found {n_me} N-methyl groups still present, expected 0")
        if not result["checks"]["is_target"]:
            problems.append(f"not the caffeine skeleton with CF3 on N1, N3 and N7 (got {canon})")
        result["detail"] = "; ".join(problems)
    emit(result, out)


def emit(result, out):
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    status = "PASS" if result["pass"] else "FAIL"
    print(f"CHECKER {status}: {result['detail']}")


if __name__ == "__main__":
    main()
