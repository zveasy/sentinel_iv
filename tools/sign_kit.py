import argparse
import hashlib
import os


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Generate sha256 for a kit zip.")
    parser.add_argument("zip_path", help="path to kit zip")
    parser.add_argument("--out", default=None, help="output .sha256 path")
    args = parser.parse_args()

    if not os.path.exists(args.zip_path):
        raise FileNotFoundError(args.zip_path)

    digest = _sha256(args.zip_path)
    out_path = args.out or (args.zip_path + ".sha256")
    with open(out_path, "w") as f:
        f.write(f"{digest}  {os.path.basename(args.zip_path)}\n")
    print(f"sha256 written: {out_path}")


if __name__ == "__main__":
    main()
