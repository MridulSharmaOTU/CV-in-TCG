from ultralytics import YOLO
import os
from multiprocessing import freeze_support

if __name__ == '__main__':
    freeze_support()  # Needed on Windows to safely spawn processes

    # Create a dedicated cache directory that YOLOv8 can write to.
    cache_dir = r"C:/YOLO_Cache"
    os.makedirs(cache_dir, exist_ok=True)
    os.environ["YOLO_CACHE_DIR"] = cache_dir  # Set environment variable for YOLO cache

    # (Optional) Set working directory to your project folder if needed.
    os.chdir(r"C:\Users\Mridul Sharma\Desktop\labs\card image model")
    print("Working directory:", os.getcwd())

    # Load the classification model.
    model = YOLO("yolov8x-cls.pt")

    # Train the model.
    results = model.train(
        data="F:/trading_card_training_data/images",  # Your dataset folder (with train/ and val/ subfolders)
        epochs=50,                  # Adjust epochs as needed
        imgsz=640,                  # Base image size
        batch=16,                   # Batch size
        rect=True,                  # Enable rectangular training
        project=".",                # Save results in this directory
        name="trading_cards_run",   # Run folder name
        save=True                   # Save the best model and training results
    )

    # model.export(format="onnx")  # Export the model to ONNX format
    print("Training complete. Best model saved in 'C:/YOLO_Results/trading_cards_run/best.pt'")