import cv2
import numpy as np
import os

# --- CONFIGURATION ---
INPUT_PATH = '/Users/raj/Desktop/Handwriting/Pre-Processing/Seperated Tables/' 
OUTPUT_PATH = '/Users/raj/Desktop/Handwriting/Cells/'

# HOW MANY ROWS TO SKIP?
# Set to 1 if the image starts immediately with the header.
# Set to 2 if there is a large white gap (margin) above the header.
SKIP_ROWS = 1 

def process_handwriting_tables(input_folder, output_folder, skip_count):
    # --- 1. SETUP PATHS ---
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created NEW output folder: {output_folder}")

    debug_folder = os.path.join(output_folder, "_Debug_Grids")
    if not os.path.exists(debug_folder):
        os.makedirs(debug_folder)

    if not os.path.exists(input_folder):
        print(f"CRITICAL ERROR: Input folder not found at {input_folder}")
        return

    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    files = [f for f in os.listdir(input_folder) 
             if f.lower().endswith(valid_extensions) and not f.startswith('.')]
    
    print(f"Found {len(files)} images. Starting process...")

    # --- 2. PROCESS IMAGES ---
    for filename in files:
        img_path = os.path.join(input_folder, filename)
        base_name = os.path.splitext(filename)[0]
        print(f"\nProcessing: {filename}...")
        
        image = cv2.imread(img_path)
        if image is None:
            print(f"  -> Skipping (File error).")
            continue

        debug_image = image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Binarize
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY, 11, 2)
        thresh = cv2.bitwise_not(thresh)

        # --- 3. DETECT GRID LINES ---
        scale = 20
        img_h, img_w = thresh.shape
        
        # Horizontal (Rows)
        hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (img_w // scale, 1))
        h_lines = cv2.erode(thresh, hor_kernel, iterations=1)
        h_lines = cv2.dilate(h_lines, hor_kernel, iterations=1)

        # Vertical (Columns)
        ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, img_h // scale))
        v_lines = cv2.erode(thresh, ver_kernel, iterations=1)
        v_lines = cv2.dilate(v_lines, ver_kernel, iterations=1)

        # Find Cut Positions
        def find_line_positions(mask, axis):
            projection = np.sum(mask, axis=axis) 
            max_val = np.max(projection)
            peaks = np.where(projection > max_val * 0.2)[0]
            clean_coords = []
            if len(peaks) > 0:
                current_group = [peaks[0]]
                for i in range(1, len(peaks)):
                    if peaks[i] - peaks[i-1] < 15: 
                        current_group.append(peaks[i])
                    else:
                        clean_coords.append(int(np.mean(current_group)))
                        current_group = [peaks[i]]
                clean_coords.append(int(np.mean(current_group)))
            return clean_coords

        row_coords = find_line_positions(h_lines, axis=1) 
        col_coords = find_line_positions(v_lines, axis=0) 

        # Force Edges: This creates "Row 0" if there is a top margin
        if len(row_coords) == 0 or row_coords[0] > 50: row_coords.insert(0, 0)
        if row_coords[-1] < img_h - 50: row_coords.append(img_h)
        if len(col_coords) == 0 or col_coords[0] > 50: col_coords.insert(0, 0)
        if col_coords[-1] < img_w - 50: col_coords.append(img_w)

        # --- 4. SAVE OUTPUTS ---
        image_output_dir = os.path.join(output_folder, f"output_{base_name}")
        if not os.path.exists(image_output_dir):
            os.makedirs(image_output_dir)

        count = 0
        
        # Iterate through ALL detected rows to label them in Debug
        for r in range(len(row_coords) - 1):
            y1, y2 = row_coords[r], row_coords[r+1]
            
            # Label the Row Number on the Debug Image (Left side)
            cv2.putText(debug_image, f"Row {r}", (5, y1 + 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            # Skip Logic
            if r < skip_count:
                # Draw RED box on skipped rows (Header/Margin)
                for c in range(len(col_coords) - 1):
                    x1, x2 = col_coords[c], col_coords[c+1]
                    cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 0, 255), 2)
                continue # Skip saving this row

            # Process Data Rows
            for c in range(len(col_coords) - 1):
                x1, x2 = col_coords[c], col_coords[c+1]
                w, h = x2 - x1, y2 - y1

                if w > 10 and h > 10:
                    # Save Cell
                    cell_crop = image[y1:y2, x1:x2]
                    save_path = os.path.join(image_output_dir, f"cell_{r}_{c}.jpg")
                    cv2.imwrite(save_path, cell_crop)
                    
                    # Draw GREEN box on processed rows
                    cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    count += 1

        # Save Debug Grid
        cv2.imwrite(os.path.join(debug_folder, f"grid_{base_name}.jpg"), debug_image)
        print(f"  -> Saved {count} cells. Debug image saved to: _Debug_Grids/grid_{base_name}.jpg")

    print("\nProcessing Complete.")
    print(f"Check the '_Debug_Grids' folder.")
    print(f"If headers are still there, change SKIP_ROWS to {skip_count + 1} and run again.")

# Run
process_handwriting_tables(INPUT_PATH, OUTPUT_PATH, SKIP_ROWS)