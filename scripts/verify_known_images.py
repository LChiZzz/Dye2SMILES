from __future__ import annotations

from pathlib import Path

from lcsmiles.core import convert_file
from lcsmiles.ocsr import recognize_image_smiles


KNOWN_IMAGES = [
    Path("/Users/l/Desktop/截屏2026-05-26 15.25.44.png"),
    Path("/Users/l/Desktop/截屏2026-05-26 15.31.03.png"),
    Path("/Users/l/Desktop/截屏2026-05-26 16.31.29.png"),
]


def main() -> int:
    failed = 0
    for image_path in KNOWN_IMAGES:
        print(f"\n## {image_path.name}")
        if not image_path.exists():
            print(f"missing: {image_path}")
            failed += 1
            continue

        raw_smiles = recognize_image_smiles(image_path)
        print(f"osra_count={len(raw_smiles)}")
        for smiles in raw_smiles:
            print(f"raw={smiles}")

        records = convert_file(image_path)
        for record in records:
            print(f"status={record.status}")
            print(f"message={record.message}")
            print(f"smiles={record.smiles}")
            if record.status == "error":
                failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
