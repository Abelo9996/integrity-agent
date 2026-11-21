"""Prepare, predict or score a local blinded validation packet; never send it automatically."""

import argparse
import json
from pathlib import Path

from integrity_agent.validation import build_packet, predict_packet, score_packet

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=["prepare", "predict", "score"])
parser.add_argument("destination", type=Path)
parser.add_argument("--corpus", type=Path)
parser.add_argument("--labels", type=Path)
parser.add_argument("--experimental-compression", action="store_true")
args = parser.parse_args()
if args.action == "prepare":
    if not args.corpus:
        parser.error("prepare requires --corpus")
    result = build_packet(args.corpus, args.destination)
    print(f"Prepared {len(result['cases'])} cases; all human labels pending.")
elif args.action == "predict":
    result = predict_packet(args.destination, compression=args.experimental_compression)
    print(f"Recorded {len(result['predictions'])} predictions in coordinator directory.")
else:
    result = score_packet(args.destination, args.labels)
    (args.destination / "coordinator/score.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
