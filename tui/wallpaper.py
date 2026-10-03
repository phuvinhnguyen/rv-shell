#!/usr/bin/env python3
"""rv wallpaper: choose the desktop picture.

    rv wallpaper                 list the pictures it knows about
    rv wallpaper next | prev     step through them
    rv wallpaper random          pick one at random
    rv wallpaper set FILE        use FILE
    rv wallpaper none            plain background colour (uses no memory)
    rv wallpaper fetch           download the repository's wallpapers into
                                 ~/Pictures/WallPapers (they are stored with
                                 Git LFS, so a plain clone only has stubs)

Pictures are found in ~/Pictures (any sub-folder) and the repository's
wallpapers/ folder. The bar applies a change immediately.
"""

from __future__ import annotations

import hashlib
import random
import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402

LFS_MEDIA = "https://media.githubusercontent.com/media/rajchauhan28/hypr-dotfiles/main/stow_base/Pictures/wallpapers/"
DEST = Path.home() / "Pictures" / "WallPapers"
SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def is_image(path: Path) -> bool:
    """Real pictures only — Git LFS stubs carry an image name but are text."""
    try:
        with path.open("rb") as handle:
            head = handle.read(12)
    except OSError:
        return False
    return head.startswith((b"\xff\xd8\xff", b"\x89PNG")) or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")


def pictures() -> list[Path]:
    found: list[Path] = []
    for root in (Path.home() / "Pictures", rvlib.REPO / "wallpapers"):
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.suffix.lower() in SUFFIXES and "Screenshots" not in path.parts and is_image(path):
                    found.append(path)
    return found


def show(path: Path) -> str:
    return str(path).replace(str(Path.home()), "~", 1)


def current() -> str:
    return rvlib.settings().get("wallpaper", {}).get("path", "")


def use(path: Path | None) -> None:
    rvlib.set_setting("wallpaper.path", show(path) if path else "")
    print(f"wallpaper: {show(path) if path else 'none'}")


def step(direction: int) -> None:
    items = pictures()
    if not items:
        sys.exit("rv: no pictures found — `rv wallpaper fetch`, or put some in ~/Pictures/WallPapers")
    paths = [show(p) for p in items]
    index = paths.index(current()) if current() in paths else -1
    use(items[(index + direction) % len(items)])


def fetch() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    stubs = sorted((rvlib.REPO / "wallpapers").glob("*"))
    got = skipped = failed = 0
    for stub in stubs:
        target = DEST / stub.name
        if target.exists() and is_image(target):
            skipped += 1
            continue
        if is_image(stub):  # already a real file in the checkout
            shutil.copy2(stub, target)
            got += 1
            continue
        text = stub.read_text(errors="replace")
        if not text.startswith("version https://git-lfs"):
            continue
        oid = next((l.split(":", 1)[1] for l in text.splitlines() if l.startswith("oid sha256:")), "")
        print(f"  {stub.name} …", end="", flush=True)
        try:
            request = Request(LFS_MEDIA + stub.name.replace(" ", "%20"), headers={"User-Agent": "rv"})
            with urlopen(request, timeout=60) as response:
                data = response.read()
            if oid and hashlib.sha256(data).hexdigest() != oid:
                raise ValueError("checksum mismatch")
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)
            got += 1
            print(f" {len(data) / 1e6:.1f} MB")
        except Exception as error:
            failed += 1
            print(f" failed ({error})")
    print(f"{got} downloaded, {skipped} already there, {failed} failed → {show(DEST)}")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "list"
    if command == "list":
        now = current()
        for path in pictures():
            print(("* " if show(path) == now else "  ") + show(path))
        if not pictures():
            print("No pictures yet: `rv wallpaper fetch`, or copy some into ~/Pictures/WallPapers")
    elif command in ("next", "prev"):
        step(1 if command == "next" else -1)
    elif command == "random":
        items = [p for p in pictures() if show(p) != current()] or pictures()
        if not items:
            sys.exit("rv: no pictures found")
        use(random.choice(items))
    elif command == "none":
        use(None)
    elif command == "set" and len(argv) > 2:
        path = rvlib.expand(argv[2]).resolve()
        if not is_image(path):
            sys.exit(f"rv: {argv[2]} is not a JPEG, PNG or WebP picture")
        use(path)
    elif command == "fetch":
        return fetch()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
