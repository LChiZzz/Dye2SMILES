from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .ocsr import recognize_image_smiles

try:
    from rdkit import Chem, rdBase
except ImportError as exc:  # pragma: no cover
    Chem = None
    rdBase = None
    RDKIT_IMPORT_ERROR = exc
else:
    RDKIT_IMPORT_ERROR = None


STRUCTURE_EXTENSIONS = {".cdxml", ".cdx", ".mol", ".sdf", ".smi", ".smiles"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".pdf"}
SUPPORTED_EXTENSIONS = STRUCTURE_EXTENSIONS | IMAGE_EXTENSIONS
IMAGE_INPUT_TYPES = {ext.lstrip(".") for ext in IMAGE_EXTENSIONS} | {"image"}
OSRA_COUNTERION_PATTERN = re.compile(r"(\[[A-Z][a-z]?\+\])\((F|Cl|Br|I)\)")
OSRA_NEUTRAL_N_OXIDE_PATTERN = re.compile(r"\[N\]\(=O\)")
IMAGE_REVIEW_MESSAGE = "图片识别结果需人工核对；手性楔线和双键顺反可能缺失或颠倒"


@dataclass(frozen=True)
class SmilesRecord:
    source: str
    index: int
    smiles: str
    input_type: str
    status: str = "ok"
    message: str = ""


class ConversionError(RuntimeError):
    """Raised when an input file cannot be converted."""


def ensure_rdkit() -> None:
    if Chem is None:
        raise ConversionError(
            "RDKit is not installed. Install with conda: "
            "conda install -c conda-forge rdkit"
        ) from RDKIT_IMPORT_ERROR


def convert_files(
    paths: Iterable[str | Path],
    *,
    canonical: bool = True,
    isomeric: bool = True,
    dummy_replacement_smiles: str | None = None,
    dummy_replacement_label: str | None = None,
) -> list[SmilesRecord]:
    records: list[SmilesRecord] = []
    for path in paths:
        records.extend(
            convert_file(
                path,
                canonical=canonical,
                isomeric=isomeric,
                dummy_replacement_smiles=dummy_replacement_smiles,
                dummy_replacement_label=dummy_replacement_label,
            )
        )
    return records


def convert_file(
    path: str | Path,
    *,
    canonical: bool = True,
    isomeric: bool = True,
    dummy_replacement_smiles: str | None = None,
    dummy_replacement_label: str | None = None,
) -> list[SmilesRecord]:
    ensure_rdkit()
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise ConversionError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ConversionError(f"Unsupported file type: {ext}")

    if ext in IMAGE_EXTENSIONS:
        return _convert_image(
            file_path,
            canonical=canonical,
            isomeric=isomeric,
            dummy_replacement_smiles=dummy_replacement_smiles,
            dummy_replacement_label=dummy_replacement_label,
        )

    mols = _read_molecules(file_path, ext)
    records: list[SmilesRecord] = []
    for i, mol in enumerate(mols, start=1):
        if mol is None:
            records.append(
                SmilesRecord(str(file_path), i, "", ext.lstrip("."), "error", "RDKit returned an empty molecule")
            )
            continue
        smiles = mol_to_smiles(mol, canonical=canonical, isomeric=isomeric)
        records.append(SmilesRecord(str(file_path), i, smiles, ext.lstrip(".")))

    if not records:
        raise ConversionError(f"No molecule was found in: {file_path}")
    return records


def mol_to_smiles(mol, *, canonical: bool = True, isomeric: bool = True) -> str:
    ensure_rdkit()
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        # Some imported molecules are already usable for SMILES even when full
        # sanitization complains. Let MolToSmiles make the final call.
        pass
    return Chem.MolToSmiles(mol, canonical=canonical, isomericSmiles=isomeric)


def smiles_to_record(
    smiles: str,
    *,
    source: str,
    index: int,
    input_type: str,
    canonical: bool = True,
    isomeric: bool = True,
    dummy_replacement_smiles: str | None = None,
    dummy_replacement_label: str | None = None,
) -> SmilesRecord:
    ensure_rdkit()
    parse_input = _repair_osra_counterions(smiles) or smiles
    messages = []
    if parse_input != smiles:
        messages.append("已修正常见 OSRA 反离子连接误判")
    if _mol_from_smiles(parse_input, quiet=True) is None:
        nitrogen_repaired = _repair_osra_neutral_n_oxide(parse_input)
        if nitrogen_repaired is not None:
            parse_input = nitrogen_repaired
            messages.append("已修正常见 OSRA 正电氮误识别为 N=O")
    expanded_input = parse_input
    expanded_label = dummy_replacement_label or "selected abbreviation"
    if dummy_replacement_smiles and _smiles_has_dummy_atom(parse_input):
        try:
            expanded_input = expand_dummy_atom_smiles(parse_input, dummy_replacement_smiles)
        except ConversionError as exc:
            return SmilesRecord(source, index, smiles, input_type, "error", str(exc))
    mol = _mol_from_smiles(parse_input, quiet=True)
    if expanded_input != parse_input:
        mol = _mol_from_smiles(expanded_input, quiet=True)
    if mol is None:
        return SmilesRecord(source, index, smiles, input_type, "error", "RDKit could not parse this SMILES")
    normalized = mol_to_smiles(mol, canonical=canonical, isomeric=isomeric)
    if expanded_input != parse_input:
        messages.append(f"已用 {expanded_label} 展开未知连接点 *")
    if _has_dummy_atom(mol):
        messages.append("含有未知连接点 *；请展开缩写基团后再最终使用")
    if _is_image_input(input_type):
        messages.append(IMAGE_REVIEW_MESSAGE)
    status = "warning" if _has_dummy_atom(mol) or _is_image_input(input_type) else "ok"
    return SmilesRecord(source, index, normalized, input_type, status=status, message="; ".join(messages))


def expand_dummy_atom_smiles(smiles: str, replacement_smiles: str) -> str:
    ensure_rdkit()
    target = _mol_from_smiles(smiles, quiet=True)
    replacement = _mol_from_smiles(replacement_smiles, quiet=True)
    if target is None:
        raise ConversionError("Cannot expand abbreviation: RDKit could not parse the source SMILES")
    if replacement is None:
        raise ConversionError("Cannot expand abbreviation: replacement fragment is not valid SMILES")

    target_dummy_atoms = [atom for atom in target.GetAtoms() if atom.GetAtomicNum() == 0]
    replacement_dummy_atoms = [atom for atom in replacement.GetAtoms() if atom.GetAtomicNum() == 0]
    if len(target_dummy_atoms) != 1:
        raise ConversionError("Cannot expand abbreviation: source must contain exactly one '*'")
    if len(replacement_dummy_atoms) != 1:
        raise ConversionError("Cannot expand abbreviation: replacement fragment must contain exactly one [*:1]")

    target_dummy = target_dummy_atoms[0]
    replacement_dummy = replacement_dummy_atoms[0]
    target_neighbors = [atom.GetIdx() for atom in target_dummy.GetNeighbors()]
    replacement_neighbors = [atom.GetIdx() for atom in replacement_dummy.GetNeighbors()]
    if len(target_neighbors) != 1 or len(replacement_neighbors) != 1:
        raise ConversionError("Cannot expand abbreviation: '*' must have exactly one attachment bond")

    target_dummy_idx = target_dummy.GetIdx()
    target_neighbor_idx = target_neighbors[0]
    replacement_dummy_idx = replacement_dummy.GetIdx()
    replacement_neighbor_idx = replacement_neighbors[0]
    replacement_offset = target.GetNumAtoms()

    bond = target.GetBondBetweenAtoms(target_dummy_idx, target_neighbor_idx)
    bond_type = bond.GetBondType() if bond is not None else Chem.BondType.SINGLE

    combined = Chem.CombineMols(target, replacement)
    editable = Chem.RWMol(combined)
    editable.AddBond(target_neighbor_idx, replacement_offset + replacement_neighbor_idx, bond_type)

    for atom_idx in sorted((target_dummy_idx, replacement_offset + replacement_dummy_idx), reverse=True):
        editable.RemoveAtom(atom_idx)

    expanded = editable.GetMol()
    try:
        Chem.SanitizeMol(expanded)
    except Exception as exc:
        raise ConversionError(f"Cannot expand abbreviation: expanded molecule is invalid ({exc})") from exc
    return Chem.MolToSmiles(expanded, canonical=False, isomericSmiles=True)


def validate_replacement_fragment(replacement_smiles: str) -> None:
    ensure_rdkit()
    replacement = _mol_from_smiles(replacement_smiles, quiet=True)
    if replacement is None:
        raise ConversionError("替换片段不是合法 SMILES")
    replacement_dummy_atoms = [atom for atom in replacement.GetAtoms() if atom.GetAtomicNum() == 0]
    if len(replacement_dummy_atoms) != 1:
        raise ConversionError("替换片段必须包含且只包含一个 [*:1] 连接点")
    if len(list(replacement_dummy_atoms[0].GetNeighbors())) != 1:
        raise ConversionError("[*:1] 必须只有一个连接键")


def _repair_osra_counterions(smiles: str) -> str | None:
    counterions: list[str] = []

    def replace_counterion(match: re.Match[str]) -> str:
        counterions.append(f"[{match.group(2)}-]")
        return match.group(1)

    repaired = OSRA_COUNTERION_PATTERN.sub(replace_counterion, smiles)
    if not counterions:
        return None
    return ".".join([*counterions, repaired])


def _repair_osra_neutral_n_oxide(smiles: str) -> str | None:
    repaired = OSRA_NEUTRAL_N_OXIDE_PATTERN.sub("[N+]", smiles)
    return repaired if repaired != smiles else None


def _mol_from_smiles(smiles: str, *, quiet: bool = False):
    if quiet and rdBase is not None:
        with rdBase.BlockLogs():
            return Chem.MolFromSmiles(smiles)
    return Chem.MolFromSmiles(smiles)


def _has_dummy_atom(mol) -> bool:
    return any(atom.GetAtomicNum() == 0 for atom in mol.GetAtoms())


def _smiles_has_dummy_atom(smiles: str) -> bool:
    mol = _mol_from_smiles(smiles, quiet=True)
    return mol is not None and _has_dummy_atom(mol)


def _is_image_input(input_type: str) -> bool:
    return input_type.lower().lstrip(".") in IMAGE_INPUT_TYPES


def write_csv(records: Iterable[SmilesRecord], output_path: str | Path) -> None:
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source", "index", "smiles", "input_type", "status", "message"],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(record.__dict__)


def _read_molecules(file_path: Path, ext: str):
    if ext in {".cdxml", ".cdx"}:
        return list(_read_chemdraw(file_path, ext))
    if ext == ".mol":
        return [Chem.MolFromMolFile(str(file_path), sanitize=True, removeHs=True)]
    if ext == ".sdf":
        supplier = Chem.SDMolSupplier(str(file_path), sanitize=True, removeHs=True)
        return list(supplier)
    if ext in {".smi", ".smiles"}:
        return _read_smiles_file(file_path)
    raise ConversionError(f"Unsupported structure file type: {ext}")


def _read_chemdraw(file_path: Path, ext: str):
    rdmolfiles = Chem.rdmolfiles
    params = None
    if hasattr(rdmolfiles, "CDXMLParserParams") and hasattr(rdmolfiles, "CDXMLFormat"):
        fmt = rdmolfiles.CDXMLFormat.CDX if ext == ".cdx" else rdmolfiles.CDXMLFormat.CDXML
        params = rdmolfiles.CDXMLParserParams(True, True, fmt)

    try:
        if params is not None:
            return rdmolfiles.MolsFromCDXMLFile(str(file_path), params)
        return rdmolfiles.MolsFromCDXMLFile(str(file_path), True, True)
    except Exception as exc:
        raise ConversionError(f"RDKit could not parse ChemDraw file {file_path.name}: {exc}") from exc


def _read_smiles_file(file_path: Path):
    mols = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            smiles = text.split()[0]
            mols.append(Chem.MolFromSmiles(smiles))
    return mols


def _convert_image(
    file_path: Path,
    *,
    canonical: bool,
    isomeric: bool,
    dummy_replacement_smiles: str | None,
    dummy_replacement_label: str | None,
) -> list[SmilesRecord]:
    smiles_values = recognize_image_smiles(file_path)
    if not smiles_values:
        raise ConversionError(f"OSRA did not return any SMILES for: {file_path}")

    records = []
    for i, smiles in enumerate(smiles_values, start=1):
        records.append(
            smiles_to_record(
                smiles,
                source=str(file_path),
                index=i,
                input_type="image",
                canonical=canonical,
                isomeric=isomeric,
                dummy_replacement_smiles=dummy_replacement_smiles,
                dummy_replacement_label=dummy_replacement_label,
            )
        )
    return records
