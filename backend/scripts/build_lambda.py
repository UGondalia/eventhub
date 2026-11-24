"""Package the backend for AWS Lambda.

    python scripts/build_lambda.py

Creates build/eventhub-lambda.zip containing only the `eventhub` package. boto3 is already
part of the Lambda Python runtime, so nothing else is bundled. The same zip serves both
functions; they differ only in the handler setting:

    eventhub-api         eventhub.handlers.lambda_handler
    eventhub-reminders   eventhub.reminders.lambda_handler
"""
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "eventhub-lambda.zip"


def main():
    OUT.parent.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "eventhub").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(ROOT).as_posix())
                count += 1
    print(f"Built {OUT.relative_to(ROOT)} ({count} files, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
