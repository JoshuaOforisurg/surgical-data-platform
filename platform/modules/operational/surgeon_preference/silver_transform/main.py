# main.py
from pathlib import Path
from silver_transformer import SilverTransformer

def main():
    # Example: Process all files in a directory
    file_paths = list(Path("data/raw_files").glob("*"))  # Get all files in a directory
    transformer = SilverTransformer()
    cleaned_data = transformer.transform_files(file_paths)
    print(f"Processed {len(cleaned_data)} files.")

if __name__ == "__main__":
    main()
