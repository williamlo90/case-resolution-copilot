import argparse
from pathlib import Path

from app.evaluation.sop_replay import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
