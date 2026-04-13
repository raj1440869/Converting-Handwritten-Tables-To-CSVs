import os
import csv

def create_training_csvs():
    # Define the source directories
    name_dir = "/Users/raj/Desktop/Handwriting/Training_Data/name_training"
    number_dir = "/Users/raj/Desktop/Handwriting/Training_Data/number_training"

    # Define output CSV filenames (saved in the folder where you run the script)
    name_csv_output = "name_data.csv"
    number_csv_output = "number_data.csv"

    # --- PROCESS NAMES ---
    print(f"Processing Names from: {name_dir}")
    try:
        with open(name_csv_output, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["FILE NAME", "Value"])  # Header

            files = os.listdir(name_dir)
            count = 0
            for filename in files:
                # Skip hidden system files (like .DS_Store)
                if filename.startswith('.'):
                    continue
                
                # Get the value (remove the .jpg, .png extension)
                value = os.path.splitext(filename)[0]
                
                writer.writerow([filename, value])
                count += 1
            print(f"Successfully created {name_csv_output} with {count} entries.")
            
    except FileNotFoundError:
        print(f"Error: Could not find directory {name_dir}")

    print("-" * 30)

    # --- PROCESS NUMBERS ---
    print(f"Processing Numbers from: {number_dir}")
    try:
        with open(number_csv_output, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["FILE NAME", "Value"])  # Header

            files = os.listdir(number_dir)
            count = 0
            for filename in files:
                # Skip hidden system files
                if filename.startswith('.'):
                    continue
                
                # Remove extension first to get the raw name
                raw_name = os.path.splitext(filename)[0]
                value = raw_name

                # Rule 1: If it has an underscore (e.g., 20_5), take the first number
                if '_' in value:
                    value = value.split('_')[0]

                # Rule 2: If it has a hyphen (e.g., 4-8), change to slash (date format)
                # Note: We check this *after* the underscore split to handle cases like 4-8_2.jpg
                if '-' in value:
                    value = value.replace('-', '/')

                writer.writerow([filename, value])
                count += 1
            print(f"Successfully created {number_csv_output} with {count} entries.")

    except FileNotFoundError:
        print(f"Error: Could not find directory {number_dir}")

if __name__ == "__main__":
    create_training_csvs()