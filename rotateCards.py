import os
import json
import random
import time
from PIL import Image
from tqdm import tqdm

# ------------------ Configuration ------------------

# Source folders for card images
MTG_FOLDER = "mtg_cards"
YGO_FOLDER = "ygo_cards"

# Output root folder (on drive F:)
OUTPUT_ROOT = r"F:\trading_card_training_data"

# Pre-rotation sizes (pre-rotation size: before any rotation)
MTG_SIZE = (672, 936)  # (width, height) for MTG cards
YGO_SIZE = (479, 700)  # (width, height) for YGO cards

# Rotation settings (Scenario 2: 10 random rotations)
NUM_SMALL = 5  # number of rotations drawn from the small range
NUM_LARGE = 5  # number of rotations drawn from the large range
SMALL_RANGE = (-5, 5)           # small range in degrees
LARGE_RANGE = (-185, -175)      # large range (near 180°); using negative values here

# Cap maximum processed images per category
MTG_MAX_COUNT = 1000
YGO_MAX_COUNT = 1000  # cap for regular YGO cards; pendulum cards usually are fewer

# JSONL metadata files
MTG_JSONL = "mtg_card_set.jsonl"
YGO_JSONL = "ygo_card_set.jsonl"

# Database JSON files (full databases to check for an exact match)
MTG_DATABASE = "mtg_database.json"
YGO_DATABASE = "ygo_database.json"

# Allowed image extensions (case-insensitive)
IMG_EXTS = {".jpg", ".jpeg", ".png"}

# ------------------ Helper Functions ------------------

def load_jsonl_as_dict(jsonl_file, key_field="set_code"):
    """
    Loads a JSONL file (one JSON record per line) and returns a dictionary mapping
    the normalized key_field to the record.
    """
    records = {}
    with open(jsonl_file, encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                key = record.get(key_field, "").strip().upper()
                if key:
                    records[key] = record
            except Exception as e:
                print(f"Error parsing line in {jsonl_file}: {e}")
    return records

def load_mtg_database(db_file):
    """
    Loads the MTG database JSON file (assumed to be a list of card objects).
    Builds and returns a dictionary mapping an exact set code to a card record.
    The key is built from the card's set abbreviation (uppercase) and collector number,
    joined by a dash. For example, a card with "set": "blb" and "collector_number": "280"
    will have key "BLB-280".
    """
    mtg_db = {}
    with open(db_file, encoding="utf-8") as f:
        cards = json.load(f)
        for card in cards:
            set_abbrev = card.get("set", "").upper().strip()
            collector_number = str(card.get("collector_number", "")).strip()
            if set_abbrev and collector_number:
                key = f"{set_abbrev}-{collector_number}"
                mtg_db[key] = card
    return mtg_db

def load_ygo_database(db_file):
    """
    Loads the Yu‐Gi‐Oh! database JSON file (assumed to be a dict with a "data" key holding a list).
    For each card, look at its "card_sets" list and add each set_code (as uppercase) to a dictionary.
    Returns a dictionary mapping set codes to the card record.
    """
    ygo_db = {}
    with open(db_file, encoding="utf-8") as f:
        data = json.load(f)
        for card in data.get("data", []):
            for cs in card.get("card_sets", []):
                code = cs.get("set_code", "").upper().strip()
                if code:
                    ygo_db[code] = card
    return ygo_db

def extract_actual_set_code(full_code):
    """
    Given a full set code string from the filename (e.g. "PLST-C17-98" or "BLB-280"),
    ignore any extra letters before the real set code.
    For example:
      - "PLST-C17-98" becomes "C17-98" (i.e. ignore the part before the first dash)
      - If there are exactly two parts (e.g. "BLB-280"), return as-is.
    """
    parts = full_code.split("-")
    if len(parts) >= 2:
        return "-".join(parts[-2:]).upper()
    return full_code.upper()

def get_clean_basename(filename):
    """
    Removes any trailing " - Front" or " - Back" (case-insensitive) from the base filename (without extension).
    Returns a tuple: (base_name, side_suffix, extension)
    For example: "SOI-225 - Back.jpg" becomes ("SOI-225", "back", ".jpg")
    """
    base, ext = os.path.splitext(filename)
    suffix = ""
    lower = base.lower()
    if " - front" in lower:
        idx = lower.find(" - front")
        suffix = "front"
        base = base[:idx]
    elif " - back" in lower:
        idx = lower.find(" - back")
        suffix = "back"
        base = base[:idx]
    return base.strip(), suffix.strip(), ext

def random_angles():
    """
    Returns a list of 10 random rotation angles:
    NUM_SMALL from SMALL_RANGE and NUM_LARGE from LARGE_RANGE.
    """
    angles_small = [random.uniform(*SMALL_RANGE) for _ in range(NUM_SMALL)]
    angles_large = [random.uniform(*LARGE_RANGE) for _ in range(NUM_LARGE)]
    return angles_small + angles_large

def process_image(filepath, card_type, target_size, dest_category, processed_counts, max_count):
    """
    Process a single image:
      - Resize to target_size.
      - Generate 10 rotated copies (using random angles from our scenario 2) and save as PNG files.
      - The new filename is based on the original base name plus a rotation label.
      - For files with a side suffix (e.g. "front" or "back"), append that after the rotation label.
      - Only process if the count for dest_category is below max_count.
    Updates processed_counts.
    """
    if processed_counts.get(dest_category, 0) >= max_count:
        return

    try:
        with Image.open(filepath) as img:
            img = img.resize(target_size, Image.Resampling.LANCZOS)
            filename = os.path.basename(filepath)
            base_name, side_suffix, _ = get_clean_basename(filename)
            angles = random_angles()

            for angle in angles:
                rotated = img.rotate(angle, resample=Image.BICUBIC, expand=True)
                angle_label = f"{'+' if angle >= 0 else ''}{int(round(angle))}"
                new_filename = f"{base_name}{angle_label}"
                if side_suffix:
                    new_filename += f"-{side_suffix}"
                new_filename += ".png"
                out_path = os.path.join(OUTPUT_ROOT, "images", dest_category, new_filename)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                rotated.save(out_path, "PNG")
            processed_counts[dest_category] = processed_counts.get(dest_category, 0) + 1
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def process_folder(source_folder, card_type, jsonl_records, database, max_count, category_func):
    """
    Processes all image files in a source folder (either MTG or YGO).
    For each image:
      - Extract the base set code from the filename (ignoring " - Front/Back").
      - Use extract_actual_set_code() to obtain the “actual” set code.
      - First check if this set code exists in the provided database dictionary.
      - Only if there’s an EXACT match, look up the metadata in jsonl_records.
      - Then, determine the destination category via category_func and process the image.
    """
    processed_counts = {}
    files = [f for f in os.listdir(source_folder)
             if os.path.splitext(f)[1].lower() in IMG_EXTS]
    # Shuffle files so that the processed images are randomly sampled
    random.shuffle(files)

    print(f"Processing {len(files)} files in {source_folder} for {card_type.upper()} cards.")
    for file in tqdm(files, desc=f"Processing {card_type} images"):
        filepath = os.path.join(source_folder, file)
        base_name, _, _ = get_clean_basename(file)
        actual_code = extract_actual_set_code(base_name)
        if card_type == "mtg":
            if actual_code not in database:
                continue
        else:  # ygo
            if actual_code not in database:
                continue

        record = jsonl_records.get(base_name.upper())
        if not record:
            continue

        dest_category = category_func(record)
        if processed_counts.get(dest_category, 0) < max_count:
            target_size = MTG_SIZE if card_type == "mtg" else YGO_SIZE
            process_image(filepath, card_type, target_size, dest_category, processed_counts, max_count)
        time.sleep(0.01)
    print(f"Finished processing {card_type.upper()} images. Processed counts: {processed_counts}")

# ------------------ Category Functions ------------------

def mtg_category(record):
    """
    For an MTG card record (from the JSONL metadata), choose the destination category
    based on its "symbol" score:
      symbol 0 -> "mtg_pre6ed"
      symbol 1 -> "mtg_6ed_to_2014"
      symbol 2 -> "mtg_post2014"
    """
    symbol = record.get("symbol")
    if symbol == 0:
        return "mtg_pre6ed"
    elif symbol == 1:
        return "mtg_6ed_to_2014"
    else:
        return "mtg_post2014"

def ygo_category(record):
    """
    For a YGO card record (from the JSONL metadata), use the "pendulum" flag
    to choose between "ygo_pendulum" (if True) and "ygo" (if False).
    """
    if record.get("pendulum", False):
        return "ygo_pendulum"
    return "ygo"

# ------------------ Main Script ------------------

def main():
    mtg_records = load_jsonl_as_dict(MTG_JSONL, key_field="set_code")
    ygo_records = load_jsonl_as_dict(YGO_JSONL, key_field="set_code")

    mtg_db = load_mtg_database(MTG_DATABASE)
    ygo_db = load_ygo_database(YGO_DATABASE)

    process_folder(MTG_FOLDER, "mtg", mtg_records, mtg_db, MTG_MAX_COUNT, mtg_category)
    process_folder(YGO_FOLDER, "ygo", ygo_records, ygo_db, YGO_MAX_COUNT, ygo_category)
    print("Training data generation complete. Check the output folders under", os.path.join(OUTPUT_ROOT, "images"))

if __name__ == "__main__":
    main()