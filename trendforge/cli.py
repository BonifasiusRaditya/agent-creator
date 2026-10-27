import argparse
import os


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Start TrendForge")
    parser.add_argument("--port", type=int, default=int(os.environ.get("TRENDFORGE_PORT", 8765)))
    args = parser.parse_args()
    print(f"\n  TrendForge is opening at http://127.0.0.1:{args.port}\n")
    uvicorn.run("trendforge.app:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()

