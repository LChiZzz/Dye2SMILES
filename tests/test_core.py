import pytest

from lcsmiles.abbreviations import ABBREVIATIONS
from lcsmiles.core import Chem, ConversionError, expand_dummy_atom_smiles, smiles_to_record, validate_replacement_fragment


pytestmark = pytest.mark.skipif(Chem is None, reason="RDKit is not installed")


def test_smiles_to_record_canonicalizes():
    record = smiles_to_record("C(C)O", source="inline", index=1, input_type="smiles")
    assert record.smiles == "CCO"
    assert record.status == "ok"


def test_smiles_to_record_repairs_osra_counterion_attachment():
    record = smiles_to_record(
        "C[N+](Br)(C)C",
        source="inline",
        index=1,
        input_type="image",
    )
    assert record.smiles == "C[N+](C)C.[Br-]"
    assert record.status == "warning"
    assert "反离子" in record.message
    assert "手性楔线" in record.message


def test_smiles_to_record_repairs_osra_indoleninium_n_oxide_misread():
    osra_smiles = (
        "O=C(N1CCN(CC1)C(=O)c1ccc2c(c1)C(C)(C)/C(=C\\C=C\\C=C\\C1=[N](=O)"
        "(CCCSSc3ccccn3)c3c(C1(C)C)cccc3)/N2C)OC(C)(C)C"
    )
    record = smiles_to_record(osra_smiles, source="inline", index=1, input_type="image")

    assert record.status == "warning"
    assert "[N+]" in record.smiles
    assert "正电氮" in record.message


@pytest.mark.parametrize(
    ("osra_smiles", "expected_status", "expected_message"),
    [
        (
            "CC(=O)OCCN1c2ccccc2C(/C/1=C\\C=C\\C=C\\C1=[N+](Br)(CCOC(=O)C)c2c(C1(C)C)cccc2)(C)C",
            "warning",
            "反离子",
        ),
        (
            "CCOC(=O)CCC/[N+](=C(\\C=C\\C(=C\\C=C/1\\N(CCCC(=O)OCC)c2c(C1(C)C)cc(cc2)S(=O)(=O)O)\\CCCCn1nnc(c1)CCCC(=O)*)/CC)/c1ccc(cc1CC)S(=O)(=O)O",
            "warning",
            "未知连接点",
        ),
        (
            "O=C(N1CCN(CC1)C(=O)c1ccc2c(c1)C(C)(C)/C(=C\\C=C\\C=C\\C1=[N](=O)(CCCSSc3ccccn3)c3c(C1(C)C)cccc3)/N2C)OC(C)(C)C",
            "warning",
            "正电氮",
        ),
    ],
)
def test_known_dye_osra_outputs_are_rdkit_readable(osra_smiles, expected_status, expected_message):
    record = smiles_to_record(osra_smiles, source="inline", index=1, input_type="image")

    assert record.status == expected_status
    assert record.smiles
    assert expected_message in record.message


def test_smiles_to_record_warns_about_dummy_atoms():
    record = smiles_to_record("*C(=O)C", source="inline", index=1, input_type="image")
    assert record.smiles == "*C(C)=O"
    assert record.status == "warning"
    assert "未知连接点" in record.message


@pytest.mark.parametrize(
    "smiles",
    [
        "C[C@H](O)C(=O)O",
        "N[C@@H](C)C(=O)O",
        "CC[C@H](C)O",
    ],
)
def test_smiles_to_record_preserves_tetrahedral_stereo_by_default(smiles):
    expected = Chem.MolToSmiles(Chem.MolFromSmiles(smiles), canonical=True, isomericSmiles=True)
    record = smiles_to_record(smiles, source="inline", index=1, input_type="smiles")

    assert record.status == "ok"
    assert record.smiles == expected
    assert "@" in record.smiles


def test_smiles_to_record_can_drop_tetrahedral_stereo_when_requested():
    record = smiles_to_record(
        "C[C@H](O)C(=O)O",
        source="inline",
        index=1,
        input_type="smiles",
        isomeric=False,
    )

    assert record.status == "ok"
    assert "@" not in record.smiles


@pytest.mark.parametrize(
    "smiles",
    [
        "F/C=C/F",
        "F/C=C\\F",
        "C/C=C/C",
        "C/C=C\\C",
    ],
)
def test_smiles_to_record_preserves_double_bond_stereo_by_default(smiles):
    expected = Chem.MolToSmiles(Chem.MolFromSmiles(smiles), canonical=True, isomericSmiles=True)
    record = smiles_to_record(smiles, source="inline", index=1, input_type="smiles")

    assert record.status == "ok"
    assert record.smiles == expected
    assert "/" in record.smiles or "\\" in record.smiles


def test_smiles_to_record_can_drop_double_bond_stereo_when_requested():
    record = smiles_to_record(
        "C/C=C\\C",
        source="inline",
        index=1,
        input_type="smiles",
        isomeric=False,
    )

    assert record.status == "ok"
    assert "/" not in record.smiles
    assert "\\" not in record.smiles


def test_image_records_warn_about_unreliable_stereo_recognition():
    record = smiles_to_record("C/C=C/C", source="inline", index=1, input_type="image")

    assert record.status == "warning"
    assert "手性楔线" in record.message
    assert "双键顺反" in record.message


def test_expand_dummy_atom_smiles_uses_replacement_fragment():
    expanded = expand_dummy_atom_smiles("*C(=O)C", "[*:1]NCCO")
    mol = Chem.MolFromSmiles(expanded)
    assert mol is not None
    assert all(atom.GetAtomicNum() != 0 for atom in mol.GetAtoms())
    assert Chem.MolToSmiles(mol) == "CC(=O)NCCO"


def test_smiles_to_record_can_expand_selected_abbreviation():
    dmpe = next(entry for entry in ABBREVIATIONS if entry.short_name == "DMPE")
    record = smiles_to_record(
        "*C(=O)C",
        source="inline",
        index=1,
        input_type="smiles",
        dummy_replacement_smiles=dmpe.replacement_smiles,
        dummy_replacement_label=dmpe.short_name,
    )
    assert record.status == "ok"
    assert "*" not in record.smiles
    assert "DMPE" in record.message
    assert "P(=O)" in record.smiles


def test_validate_replacement_fragment_requires_single_attachment():
    validate_replacement_fragment("[*:1]NCCO")
    with pytest.raises(ConversionError):
        validate_replacement_fragment("NCCO")


def test_dictionary_replacement_fragments_are_valid():
    for entry in ABBREVIATIONS:
        if entry.replacement_smiles:
            validate_replacement_fragment(entry.replacement_smiles)
