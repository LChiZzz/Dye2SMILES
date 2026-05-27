from pathlib import Path

import pytest

from lcsmiles.core import Chem, ConversionError, convert_file
from lcsmiles.ocsr import OCSRError


pytestmark = pytest.mark.skipif(Chem is None, reason="RDKit is not installed")


KNOWN_DESKTOP_IMAGES = [
    Path("/Users/l/Desktop/截屏2026-05-26 15.25.44.png"),
    Path("/Users/l/Desktop/截屏2026-05-26 15.31.03.png"),
    Path("/Users/l/Desktop/截屏2026-05-26 16.31.29.png"),
]


@pytest.mark.parametrize("image_path", KNOWN_DESKTOP_IMAGES)
def test_known_dye_screenshots_do_not_return_errors(image_path):
    if not image_path.exists():
        pytest.skip(f"local regression image is not available: {image_path}")

    records = convert_file(image_path)

    assert records
    assert all(record.status != "error" for record in records)
    assert all("手性楔线" in record.message for record in records)


def test_screenshot_results_are_not_marked_as_fully_trusted(tmp_path):
    draw = pytest.importorskip("rdkit.Chem.Draw")
    mol = Chem.MolFromSmiles("C[C@H](O)C(=O)O")
    Chem.rdDepictor.Compute2DCoords(mol)
    Chem.WedgeMolBonds(mol, mol.GetConformer())
    image_path = tmp_path / "chiral_lactic_acid.png"
    draw.MolToFile(mol, str(image_path), size=(700, 420), kekulize=True)

    try:
        records = convert_file(image_path)
    except (ConversionError, OCSRError):
        pytest.skip("OSRA could not read this generated stereo probe")

    assert records
    assert all(record.status == "warning" for record in records)
    assert all("手性楔线" in record.message for record in records)
