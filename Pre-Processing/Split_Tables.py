import cv2
import numpy as np
import os

def split_exact_5_columns(input_folder, output_folder):
    # 1. Setup Folders
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Check if input folder exists to avoid errors
    if not os.path.exists(input_folder):
        print(f"Error: Input directory '{input_folder}' not found.")
        return

    files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    print(f"Processing {len(files)} images for exact splitting...")

    for filename in files:
        img_path = os.path.join(input_folder, filename)
        img = cv2.imread(img_path)
        if img is None: continue

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Isolate Vertical Lines (Aggressively)
        #    Adaptive threshold to handle shadows
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        #    Use a tall kernel to melt text into nothing, leaving only grid lines
        #    Height / 15 is long enough to bridge gaps in handwritten text
        kernel_height = h // 15
        ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_height))
        
        #    Erode (thicken lines) then Dilate (restore)
        vertical_lines = cv2.erode(thresh, ver_kernel, iterations=1)
        vertical_lines = cv2.dilate(vertical_lines, ver_kernel, iterations=1)
        
        # 3. Collapse to 1D Signal (Column Sums)
        col_sums = np.sum(vertical_lines, axis=0)
        
        #    Normalize to 0-255 for easier thresholding
        col_sums_norm = (col_sums / col_sums.max()) * 255

        # 4. Find the "Spine" (The Split Point)
        #    The spine is in the middle. We search from 45% to 55% of the width.
        #    We want the RIGHT-MOST line in this cluster to ensure we include 'Venmo'.
        
        center_start = int(w * 0.45)
        center_end = int(w * 0.55)
        center_slice = col_sums_norm[center_start:center_end]
        
        #    Find indices where we have strong lines (intensity > 50)
        strong_lines = np.where(center_slice > 50)[0]

        if len(strong_lines) > 0:
            # Pick the LAST strong line in this region (The Right-Most one)
            # This skips the "Bank|Venmo" line and lands on "Venmo|Date"
            spine_offset = strong_lines[-1]
            split_x = center_start + spine_offset
        else:
            # Fallback: exact middle
            split_x = w // 2

        # 5. Find the "Sr" Divider (Left Page Cleaning)
        #    We want to cut OFF the first column. 
        #    Search the first 12% of the image.
        sr_search_end = int(w * 0.12)
        sr_slice = col_sums_norm[0:sr_search_end]
        
        #    Ignore the first 15 pixels (image border artifact)
        sr_lines = np.where(sr_slice[15:] > 50)[0]
        
        sr_cut_x = 0
        if len(sr_lines) > 0:
            # Pick the FIRST strong line we find after the border
            sr_cut_x = 15 + sr_lines[0] 

        # 6. Crop with Buffers
        #    We add small offsets (+/- 3 pixels) to trim the black grid lines themselves
        #    so the final image is clean white space on the edges.
        
        #    Left Image: From 'Sr' cut -> Split Point
        #    Include the split_x to ensure we get the right edge of Venmo
        img_left = img[:, sr_cut_x + 3 : split_x + 3]
        
        #    Right Image: From Split Point -> End
        img_right = img[:, split_x + 3 :]

        # 7. Save
        base_name = os.path.splitext(filename)[0]
        
        out_left = os.path.join(output_folder, f"{base_name}_1.jpg")
        out_right = os.path.join(output_folder, f"{base_name}_2.jpg")
        
        cv2.imwrite(out_left, img_left)
        cv2.imwrite(out_right, img_right)
        
        print(f"Processed {filename}: Sr-Cut={sr_cut_x}, Split={split_x}")

    print("Done! Check the 'Seperated Tables' folder.")

if __name__ == "__main__":
    # --- UPDATED PATHS TO USE PRE-PROCESSING FOLDER ---
    input_folder = os.path.join('Pre-Processing', 'Gray_Scale')
    output_folder = os.path.join('Pre-Processing', 'Seperated Tables')
    
    split_exact_5_columns(input_folder, output_folder)