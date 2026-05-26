from __future__ import annotations

from pathlib import Path

from rdkit import Chem
from rdkit.Chem import Draw, rdDepictor

from lcsmiles.core import ConversionError, convert_file, smiles_to_record


KNOWN_IMAGES = [
    Path("/Users/l/Desktop/截屏2026-05-26 15.25.44.png"),
    Path("/Users/l/Desktop/截屏2026-05-26 15.31.03.png"),
    Path("/Users/l/Desktop/截屏2026-05-26 16.31.29.png"),
]

CORE_STEREO_CASES = {
    "tetrahedral_lactic_acid": "C[C@H](O)C(=O)O",
    "tetrahedral_alanine": "N[C@@H](C)C(=O)O",
    "ez_trans_difluoroethene": "F/C=C/F",
    "ez_cis_difluoroethene": "F/C=C\\F",
    "ez_trans_2_butene": "C/C=C/C",
    "ez_cis_2_butene": "C/C=C\\C",
}

OCR_STEREO_PROBES = {
    "ocr_chiral_lactic_acid": "C[C@H](O)C(=O)O",
    "ocr_chiral_alanine": "N[C@@H](C)C(=O)O",
    "ocr_ez_trans_2_butene": "C/C=C/C",
    "ocr_ez_cis_2_butene": "C/C=C\\C",
}


def main() -> int:
    failures = 0
    print("## Core stereochemistry")
    for name, smiles in CORE_STEREO_CASES.items():
        expected = Chem.MolToSmiles(Chem.MolFromSmiles(smiles), canonical=True, isomericSmiles=True)
        record = smiles_to_record(smiles, source=name, index=1, input_type="smiles")
        ok = record.status == "ok" and record.smiles == expected
        failures += 0 if ok else 1
        print(f"{name}: {'PASS' if ok else 'FAIL'} -> {record.smiles}")

    print("\n## Known dye screenshots")
    for image_path in KNOWN_IMAGES:
        if not image_path.exists():
            print(f"{image_path.name}: SKIP missing")
            continue
        records = convert_file(image_path)
        ok = records and all(record.status != "error" for record in records)
        failures += 0 if ok else 1
        print(f"{image_path.name}: {'PASS' if ok else 'FAIL'}")
        for record in records:
            print(f"  {record.status}: {record.message}")
            print(f"  {record.smiles}")

    print("\n## OCR stereochemistry probes")
    probe_dir = Path("/tmp/lcsmiles_quality_probes")
    probe_dir.mkdir(parents=True, exist_ok=True)
    for name, smiles in OCR_STEREO_PROBES.items():
        mol = Chem.MolFromSmiles(smiles)
        rdDepictor.Compute2DCoords(mol)
        Chem.WedgeMolBonds(mol, mol.GetConformer())
        image_path = probe_dir / f"{name}.png"
        Draw.MolToFile(mol, str(image_path), size=(700, 420), kekulize=True)

        try:
            records = convert_file(image_path)
        except ConversionError as exc:
            print(f"{name}: LIMITATION -> OSRA returned no usable SMILES ({exc})")
            continue

        print(f"{name}: WARNING EXPECTED")
        for record in records:
            marked_untrusted = record.status == "warning" and "手性楔线" in record.message
            failures += 0 if marked_untrusted else 1
            print(f"  {record.status}: {record.message}")
            print(f"  {record.smiles}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
