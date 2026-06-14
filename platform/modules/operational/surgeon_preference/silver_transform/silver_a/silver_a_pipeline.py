import logging
from pathlib import Path
from silver_transform.silver_a.silver_a_transformer import SilverTransformer
from config.paths import BRONZE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(input_dir=None):
    # Single source of truth
    input_path = Path(input_dir) if input_dir else BRONZE_DIR

    if not input_path.exists():
        logger.error(f"Input directory does not exist: {input_path}")
        return

    # Only actual files (not directories)
    file_paths = [f for f in input_path.glob("*") if f.is_file()]

    if not file_paths:
        logger.error(f"No files found in {input_path}")
        return

    logger.info(f"Found {len(file_paths)} files.")

    transformer = SilverTransformer()
    cleaned_data = transformer.transform_files(file_paths)

    logger.info(f"Processed {len(cleaned_data)} files.")
    logger.info(f"Output written to {transformer.silver_a_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Override bronze directory"
    )

    args = parser.parse_args()
    main(args.input_dir)
