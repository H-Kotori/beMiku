"""Local beMiku audio experiment; all generated material stays in ignored local/."""

import argparse
import json
import sys
import uuid
from pathlib import Path

from analysis import ROOT, analyze_file, analyze_session


def emit(data):
    print(json.dumps(data, ensure_ascii=False, allow_nan=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Analyze a local file without uploading audio.")
    source = analyze.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--session", type=Path, help="Analyze only mapped coverage in a capture directory.")
    analyze.add_argument("--start", type=float, default=0)
    analyze.add_argument("--end", type=float)
    analyze.add_argument("--source-offset", type=float, default=0)
    analyze.add_argument("--metadata", type=Path, help="Private JSON identity information, never passed to the model.")
    analyze.add_argument("--output", type=Path)
    commands.add_parser("devices", help="List Windows output loopbacks.")
    capture = commands.add_parser("capture", help="Capture the output mix with bounded lifetime and stdin control.")
    capture.add_argument("--output", type=Path)
    capture.add_argument("--max-seconds", type=float, default=600)
    capture.add_argument("--lease-seconds", type=float, default=60)
    capture.add_argument("--device-index", type=int)
    args = parser.parse_args()
    output = getattr(args, "output", None) or ROOT / "local/audio-listener-sessions" / uuid.uuid4().hex
    try:
        if args.command == "devices":
            from capture import list_devices
            emit(list_devices())
            return 0
        if args.command == "capture":
            from capture import capture_session
            report = capture_session(output, args.max_seconds, args.lease_seconds, args.device_index)
            emit({"event": "capture_finished", "status": report["status"], "reason": report["stop_reason"],
                  "report": str(output.resolve().relative_to(ROOT) / "capture.json"),
                  "duration_seconds": report.get("duration_seconds", 0), "mapped_intervals": len(report["coverage"])})
            return 0 if report["status"] == "complete" else 2
        metadata = json.loads(args.metadata.read_text(encoding="utf-8")) if args.metadata else None
        if args.session:
            if args.start != 0 or args.end is not None or args.source_offset != 0:
                raise ValueError("Capture sessions use their own mapped passage bounds.")
            report = analyze_session(args.session, output, metadata=metadata, progress=emit)
        else:
            report = analyze_file(args.file, output, start=args.start, end=args.end,
                                  source_offset=args.source_offset, metadata=metadata, progress=emit)
        emit({"event": "analysis_complete", "status": report["status"],
              "report": str(output.resolve().relative_to(ROOT) / "report.json"),
              "analyzed_seconds": report.get("analyzed_seconds", 0), "clips": len(report["clips"])})
        return 0 if report["status"] == "complete" else 2
    except KeyboardInterrupt:
        emit({"event": "cancelled"})
        return 130
    except Exception as error:
        emit({"event": "failed", "error_type": type(error).__name__,
              "message": "Local operation failed; inspect the private report and diagnostic file if created."})
        return 1


if __name__ == "__main__":
    sys.exit(main())
