"""Fetch and verify the official pinned model. This setup step uploads no audio."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time

MODEL_ID = "Qwen/Qwen2-Audio-7B-Instruct"
REVISION = "0a095220c30b7b31434169c3086508ef3ea5bf0a"
ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_files(destination: Path, sources: dict) -> dict[str, str]:
    """Verify LFS SHA-256 or Git blob SHA-1, then record SHA-256 for every file."""
    if sources["model_id"] != MODEL_ID or sources["revision"] != REVISION:
        raise ValueError("Source manifest identity mismatch")
    hashes = {}
    for item in sources["files"]:
        filename = item["name"]
        path = destination / filename
        if path.resolve().parent != destination.resolve():
            raise ValueError("Unexpected model file location")
        if path.stat().st_size != item["bytes"]:
            raise ValueError("Model file size mismatch")
        sha256 = hashlib.sha256()
        git_blob = hashlib.sha1(usedforsecurity=False)
        git_blob.update(f"blob {item['bytes']}\0".encode())
        with path.open("rb") as handle:
            while chunk := handle.read(8 * 1024 * 1024):
                sha256.update(chunk)
                git_blob.update(chunk)
        digest = sha256.hexdigest()
        if item.get("lfs_sha256"):
            if digest != item["lfs_sha256"]:
                raise ValueError("Model shard checksum mismatch")
        elif git_blob.hexdigest() != item["git_blob_sha1"]:
            raise ValueError("Model metadata checksum mismatch")
        hashes[filename] = digest
        print(json.dumps({"stage": "verified_file", "file": filename, "bytes": item["bytes"]}), flush=True)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "local/models/qwen2-audio")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing files without network access.")
    args = parser.parse_args()
    # Network failures can contain signed URLs. Report only safe exception classes.
    logging.disable(logging.CRITICAL)
    started = time.monotonic()
    try:
        destination = args.destination.resolve()
        private_root = (ROOT / "local").resolve()
        if destination == private_root or not destination.is_relative_to(private_root):
            raise ValueError("Model destination must be a directory inside ignored local storage")
        destination.mkdir(parents=True, exist_ok=True)
        cache = private_root / "audio-listener-cache/huggingface"
        os.environ.update({
            "HF_HOME": str(cache),
            "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_DISABLE_PROGRESS_BARS": "1",
            "HF_HUB_ETAG_TIMEOUT": "60",
            "HF_HUB_DOWNLOAD_TIMEOUT": "120",
            "RUST_LOG": "off",
        })
        source_path = destination.parent / (destination.name + ".source-manifest.json")
        if args.verify_only:
            sources = json.loads(source_path.read_text(encoding="utf-8"))
        else:
            from huggingface_hub import HfApi, snapshot_download

            info = HfApi(token=False).model_info(MODEL_ID, revision=REVISION, files_metadata=True)
            if info.sha != REVISION:
                raise ValueError("Server revision did not match pinned revision")
            files = [item for item in info.siblings if item.rfilename.endswith((".json", ".txt", ".safetensors"))
                     or item.rfilename in {"README.md", "LICENSE"}]
            sources = {
                "model_id": MODEL_ID,
                "revision": REVISION,
                "files": [{"name": item.rfilename, "bytes": item.size,
                           "lfs_sha256": item.lfs.sha256 if item.lfs else None,
                           "git_blob_sha1": item.blob_id} for item in files],
            }
            write_json(source_path, sources)
            print(json.dumps({"stage": "downloading", "revision": REVISION,
                              "files": len(files), "bytes": sum(item.size for item in files)}), flush=True)
            snapshot_download(repo_id=MODEL_ID, revision=REVISION, local_dir=destination,
                              token=False, allow_patterns=[item.rfilename for item in files], max_workers=4)
        hashes = verify_files(destination, sources)
        write_json(destination / "model-manifest.json", {
            "model_id": MODEL_ID, "revision": REVISION, "files": hashes,
            "downloaded": True, "verified": True,
        })
        print(json.dumps({"stage": "complete", "files": len(hashes),
                          "seconds": round(time.monotonic() - started, 1)}), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({"stage": "failed", "error_type": type(error).__name__,
                          "hint": "Rerun to resume; check connectivity and available disk space."}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
