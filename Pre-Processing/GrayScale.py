import cv2
import glob
import os
import numpy as np


def convert_images_to_grayscale(folder_path, output_folder):
    """
    Convert all images in folder_path to grayscale and save them to output_folder.
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Locate all images
    file_paths = glob.glob(os.path.join(folder_path, '*.jpg')) + \
                 glob.glob(os.path.join(folder_path, '*.jpeg')) + \
                 glob.glob(os.path.join(folder_path, '*.png'))

    converted_count = 0
    for file_path in file_paths:
        img = cv2.imread(file_path)
        if img is not None:
            # --- EXACT LOGIC PRESERVED ---
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            filename = os.path.basename(file_path)
            output_path = os.path.join(output_folder, filename)
            cv2.imwrite(output_path, gray_img)
            converted_count += 1
            print(f"Converted: {filename}")
        else:
            print(f"Could not read image: {file_path}")
    
    print(f"\nTotal images converted to grayscale: {converted_count}")

if __name__ == "__main__":
    # Path configuration: Pointing into the 'Pre-Processing' folder
    input_folder = os.path.join('Pre-Processing', 'Original_Images')
    output_folder = os.path.join('Pre-Processing', 'Gray_Scale')
    
    convert_images_to_grayscale(input_folder, output_folder)


def crop_image_to_grid(image_path, output_path):
    # 1. Load the image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Skipping: Could not load {image_path}")
        return

    # 2. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Adaptive Thresholding (EXACT LOGIC PRESERVED)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )

    # 4. Define Kernels (EXACT LOGIC PRESERVED)
    horizontal_kernel_len = np.array(img).shape[1] // 40
    vertical_kernel_len = np.array(img).shape[0] // 40

    hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_kernel_len, 1))
    ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_kernel_len))

    # 5. Morphological Operations (EXACT LOGIC PRESERVED)
    image_horizontal = cv2.erode(thresh, hor_kernel, iterations=3)
    image_horizontal = cv2.dilate(image_horizontal, hor_kernel, iterations=3)

    image_vertical = cv2.erode(thresh, ver_kernel, iterations=3)
    image_vertical = cv2.dilate(image_vertical, ver_kernel, iterations=3)

    # 6. Combine to create mask
    table_mask = cv2.addWeighted(image_horizontal, 1, image_vertical, 1, 0.0)

    # 7. Find contours
    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        # Assumes the table is the largest single grid structure
        c = max(contours, key=cv2.contourArea)
        
        # Get bounding box coordinates
        x, y, w, h = cv2.boundingRect(c)
        
        # Crop the original image
        cropped_img = img[y:y+h, x:x+w]
        
        # Save the result
        cv2.imwrite(output_path, cropped_img)
        print(f"Processed: {os.path.basename(image_path)}")
    else:
        print(f"Warning: No grid found in {os.path.basename(image_path)}")

def process_folder(input_folder_path, output_folder_path):
    # Get current working directory
    cwd = os.getcwd()
    
    # Construct full paths based on where the script is running
    input_dir = os.path.join(cwd, input_folder_path)
    output_dir = os.path.join(cwd, output_folder_path)

    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    # Check input directory
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_folder_path}' not found.")
        return

    # Loop through all files
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(valid_extensions)]

    print(f"Found {len(files)} images. Starting batch processing...")

    for filename in files:
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)
        
        try:
            crop_image_to_grid(input_path, output_path)
        except Exception as e:
            print(f"Failed to process {filename}: {e}")

    print("Batch processing complete.")

if __name__ == "__main__":
    # Path configuration: Pointing into the 'Pre-Processing' folder
    # Note: 'Seperated Tables' matches the spelling in your file tree image
    input_folder = os.path.join('Pre-Processing', 'Gray_Scale')
    output_folder = os.path.join('Pre-Processing', 'Gray_Scale')
    
    process_folder(input_folder, output_folder)

