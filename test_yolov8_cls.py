import os
import random
import json
import cv2
import numpy as np
import torch
from ultralytics import YOLO

def load_ground_truth(jsonl_path):
    """
    Load ground truth from a JSONL file.
    Each line should be a JSON object with:
      - "filename" or "image_file": the image filename (e.g., "card123.jpg")
      - For MTG: a "symbol" key (0, 1, or 2)
      - For YGO: a "pendulum" key (boolean)
    Returns a dictionary mapping the base filename to label.
    """
    gt = {}
    with open(jsonl_path, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                # Use 'filename' if available; otherwise, use 'image_file'
                file_field = data.get("filename") or data.get("image_file")
                if file_field:
                    filename = os.path.basename(file_field)
                else:
                    continue
                label = "unknown"
                if "symbol" in data:
                    symbol = data["symbol"]
                    if symbol == 0:
                        label = "mtg_pre6ed"
                    elif symbol == 1:
                        label = "mtg_6ed_to_2014"
                    elif symbol == 2:
                        label = "mtg_post2014"
                elif "pendulum" in data:
                    pendulum = data["pendulum"]
                    label = "ygo_pendulum" if pendulum else "ygo"
                gt[filename] = label
            except Exception as e:
                print(f"Error processing line: {line}\n{e}")
    print(f"Loaded {len(gt)} entries from {jsonl_path}")
    return gt

def get_random_images(folder, n=10):
    """
    Return a list of n random image file paths from the specified folder.
    Only considers files ending with .png, .jpg, or .jpeg.
    """
    valid_ext = ('.png', '.jpg', '.jpeg')
    all_files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith(valid_ext)]
    if len(all_files) < n:
        n = len(all_files)
    return random.sample(all_files, n)

def predict_image(model, image_path, device):
    """
    Manually preprocess the image and run the forward pass directly.
    This bypasses YOLOv8's built-in predictor.
    Returns the predicted class label as a string.
    """
    # Load image via OpenCV (uint8)
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image {image_path}")
        return "Error"
    
    # Convert from BGR to RGB and resize to 640x640
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (640, 640))
    
    # Normalize to [0, 1] and convert to float32
    img = img.astype(np.float32) / 255.0
    
    # Convert from NHWC to NCHW and add batch dimension -> (1, 3, 640, 640)
    img_tensor = torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0).to(device)
    
    with torch.no_grad():
        output = model.model.forward(img_tensor)
        # If output is a tuple, take the first element as logits.
        if isinstance(output, (tuple, list)):
            logits = output[0]
        else:
            logits = output
        probs = torch.softmax(logits, dim=1)
        pred_index = int(torch.argmax(probs, dim=1).item())
        pred_label = model.names[pred_index]
    return pred_label

def main():
    # --- Load the trained classification model ---
    model_path = r"C:\Users\Mridul Sharma\Desktop\labs\card image model\trading_cards_run_epoch_40\weights\best.pt"
    model = YOLO(model_path)
    
    # Set device and move model to device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    
    # --- Load ground truth dictionaries ---
    mtg_gt = load_ground_truth(r"C:\Users\Mridul Sharma\Desktop\labs\card image model\mtg_card_set.jsonl")
    ygo_gt = load_ground_truth(r"C:\Users\Mridul Sharma\Desktop\labs\card image model\ygo_card_set.jsonl")
    
    # --- Define test image folders ---
    mtg_folder = r"C:\Users\Mridul Sharma\Desktop\labs\card image model\mtg_cards"
    ygo_folder = r"C:\Users\Mridul Sharma\Desktop\labs\card image model\ygo_cards"
    
    # --- Get 10 random images from each folder ---
    mtg_images = get_random_images(mtg_folder, 100)
    ygo_images = get_random_images(ygo_folder, 100)
    
    print("----- Testing on MTG Cards -----")
    for img_path in mtg_images:
        pred_label = predict_image(model, img_path, device)
        filename = os.path.basename(img_path)
        gt_label = mtg_gt.get(filename, "Not Found")
        print(f"Image: {filename} | Predicted: {pred_label} | Ground Truth: {gt_label}")
    
    print("\n----- Testing on YGO Cards -----")
    for img_path in ygo_images:
        pred_label = predict_image(model, img_path, device)
        filename = os.path.basename(img_path)
        gt_label = ygo_gt.get(filename, "Not Found")
        print(f"Image: {filename} | Predicted: {pred_label} | Ground Truth: {gt_label}")

if __name__ == '__main__':
    main()
