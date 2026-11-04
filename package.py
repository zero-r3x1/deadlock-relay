"""Check the Windows bundle and package its complete portable directory."""
from pathlib import Path
import argparse
import shutil
import subprocess

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, default=root / "dist")
    args = parser.parse_args()
    base = args.dist_dir.resolve()
    dest = base / "DeadlockRelay"
    result = subprocess.run([str(dest / "DeadlockRelay.exe"), "--self-check"],
                            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise SystemExit(f"Packaged self-check failed: {result.returncode}")
    print("Packaged self-check passed")
    for name in ["README.md", "THIRD_PARTY.md"]:
        shutil.copy2(root / name, dest)
    for name in ["docs", "licenses"]:
        shutil.copytree(root / name, dest / name, dirs_exist_ok=True)
    archive = shutil.make_archive(str(root / "dist/DeadlockRelay-windows-x64"),
                                  "zip", base, "DeadlockRelay")
    print(f"Ready: {archive} ({Path(archive).stat().st_size:,} bytes)")
