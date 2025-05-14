import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageStat

# --- Configuration ---
INPUT_DIR = 'attach'
OUTPUT_DIR = 'watermarked_output'
# WATERMARK_TEXT = "Your Watermark"  # Change this to your desired watermark text
WHITE_WATERMARK_IMAGE_PATH = 'white-watermark.png'
BLACK_WATERMARK_IMAGE_PATH = 'black-watermark.png'

# IMPORTANT: Specify the path to a .ttf font file.
# Examples: "arial.ttf", "C:/Windows/Fonts/verdana.ttf"
# If the script can\'t find this font, it will use a low-quality default.
# FONT_PATH = "arial.ttf"

# BASE_OPACITY_PERCENT = 30       # Opacity of the watermark (0-100). 20-30% is often subtle.
OPACITY_FOR_DARK_WM_PERCENT = 15  # Opacity for the black watermark on bright backgrounds (0-100)
OPACITY_FOR_LIGHT_WM_PERCENT = 30 # Opacity for the white watermark on dark backgrounds (0-100)

BRIGHTNESS_THRESHOLD = 128    # Pixel brightness (0-255). Images brighter than this get dark text.
# FONT_SIZE_DIVISOR = 30        # Affects font size relative to image diagonal. Smaller divisor = larger font.
# TILE_ROTATION_ANGLE = -30     # Angle for tiled watermarks in degrees.
# TILE_GAP_X_FACTOR = 1.8       # Multiplier for horizontal gap between tiles (relative to rotated tile width). e.g., 1.5 = 50% gap.
# TILE_GAP_Y_FACTOR = 0.7       # Multiplier for vertical gap between tiles (relative to rotated tile height). e.g., 0.5 = tight packing.

# --- Helper Functions ---

def analyze_image_brightness(image_obj_rgb):
    """Analyzes the average brightness of an RGB image."""
    try:
        grayscale_image = image_obj_rgb.convert('L')
        stat = ImageStat.Stat(grayscale_image)
        return stat.mean[0]  # Average pixel brightness (0-255)
    except Exception as e:
        print(f"Error analyzing image brightness: {e}")
        return BRIGHTNESS_THRESHOLD # Return a default to allow processing to continue


def add_watermark_to_image(image_path, output_path):
    """Opens an image, adds a single centered watermark, and saves it."""
    try:
        img = Image.open(image_path).convert("RGBA") # Ensure RGBA for compositing
        img_width, img_height = img.size

        # Analyze brightness of the original image (before converting to RGBA if it was, e.g. JPG)
        # For brightness analysis, use an RGB version if original had no alpha
        img_for_brightness_analysis = Image.open(image_path).convert("RGB")
        brightness = analyze_image_brightness(img_for_brightness_analysis)

        selected_watermark_path = ""
        if brightness > BRIGHTNESS_THRESHOLD:
            # Image is bright, use dark text
            # text_color_with_alpha = (0, 0, 0, alpha_value) # Black
            selected_watermark_path = BLACK_WATERMARK_IMAGE_PATH
            watermark_choice_info = "black"
        else:
            # Image is dark, use light text
            # text_color_with_alpha = (255, 255, 255, alpha_value) # White
            selected_watermark_path = WHITE_WATERMARK_IMAGE_PATH
            watermark_choice_info = "white"
        
        print(f"Processing '{os.path.basename(image_path)}': Target size {img_width}x{img_height}, Brightness {brightness:.0f}, using {watermark_choice_info} watermark ('{os.path.basename(selected_watermark_path)}').")

        try:
            watermark_img_original = Image.open(selected_watermark_path)
        except FileNotFoundError:
            print(f"Error: Watermark image file not found at '{selected_watermark_path}'. Skipping watermark for this image.")
            img.convert("RGB").save(output_path, quality=95) # Save original if watermark image missing
            print(f"Saved original image to '{output_path}' due to missing watermark file.")
            return
            
        watermark_img_rgba = watermark_img_original.convert("RGBA")

        # --- DIAGNOSTIC PRINTS --- START ---
        print(f"DIAGNOSTIC: Watermark '{selected_watermark_path}' loaded. Mode: {watermark_img_rgba.mode}")
        if watermark_img_rgba.mode == 'RGBA':
            _, _, _, a_original_diag = watermark_img_rgba.split()
            min_alpha_orig, max_alpha_orig = a_original_diag.getextrema()
            print(f"DIAGNOSTIC: Original watermark alpha range (0-255): Min={min_alpha_orig}, Max={max_alpha_orig}")
        # --- DIAGNOSTIC PRINTS --- END ---

        # Determine new size for the watermark (square, side = min of target image dimensions)
        new_watermark_side = min(img_width, img_height)
        
        current_opacity_percent = 0
        if brightness > BRIGHTNESS_THRESHOLD:
            # Image is bright, using dark watermark
            current_opacity_percent = OPACITY_FOR_DARK_WM_PERCENT
        else:
            # Image is dark, using light watermark
            current_opacity_percent = OPACITY_FOR_LIGHT_WM_PERCENT

        # Resize watermark
        try:
            resized_watermark = watermark_img_rgba.resize((new_watermark_side, new_watermark_side), Image.Resampling.LANCZOS)
        except AttributeError: # Older Pillow versions
            resized_watermark = watermark_img_rgba.resize((new_watermark_side, new_watermark_side), Image.LANCZOS)

        # Apply opacity to the resized watermark
        r_wm, g_wm, b_wm, a_original_wm = resized_watermark.split()
        opacity_multiplier = current_opacity_percent / 100.0
        # Ensure alpha values are integers after multiplication
        final_alpha_band_wm = a_original_wm.point(lambda p: int(round(p * opacity_multiplier)))
        
        # --- DIAGNOSTIC PRINTS --- START ---
        min_alpha_final, max_alpha_final = final_alpha_band_wm.getextrema()
        print(f"DIAGNOSTIC: Watermark alpha range AFTER applying {current_opacity_percent}% opacity (0-255): Min={min_alpha_final}, Max={max_alpha_final}")
        # --- DIAGNOSTIC PRINTS --- END ---

        watermark_with_opacity = Image.merge("RGBA", (r_wm, g_wm, b_wm, final_alpha_band_wm))

        # Create a new transparent layer for the watermark, same size as the target image
        watermark_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))

        # Calculate position to center the watermark
        paste_x = (img_width - new_watermark_side) // 2
        paste_y = (img_height - new_watermark_side) // 2

        # Paste the watermark onto the layer
        # The watermark_with_opacity itself acts as its own mask due to its alpha channel
        watermark_layer.paste(watermark_with_opacity, (paste_x, paste_y), watermark_with_opacity)

        # Composite the watermark layer onto the image
        watermarked_image = Image.alpha_composite(img, watermark_layer)

        # Save, converting back to RGB if the original was likely JPG, etc.
        # Or save as PNG to preserve transparency if needed, but JPG is common.
        final_image_to_save = watermarked_image.convert("RGB")
        final_image_to_save.save(output_path, quality=95) # Adjust quality for JPG

        print(f"Saved watermarked image to '{output_path}'")

    except FileNotFoundError:
        print(f"Error: Image file not found at '{image_path}'")
    except IOError as e:
        print(f"Error processing image '{image_path}': {e}. Is it a valid image file?")
    except Exception as e:
        print(f"An unexpected error occurred with '{image_path}': {e}")

# --- Main Script ---
def main():
    # Check for watermark image files existence
    if not os.path.exists(WHITE_WATERMARK_IMAGE_PATH):
        print(f"Error: White watermark image '{WHITE_WATERMARK_IMAGE_PATH}' not found.")
        print("Please make sure it's in the same directory as the script, or update the path.")
        return
    if not os.path.exists(BLACK_WATERMARK_IMAGE_PATH):
        print(f"Error: Black watermark image '{BLACK_WATERMARK_IMAGE_PATH}' not found.")
        print("Please make sure it's in the same directory as the script, or update the path.")
        return

    if not os.path.exists(INPUT_DIR):
        print(f"Error: Input directory '{INPUT_DIR}' not found.")
        print(f"Please create it and place images inside.")
        return

    if not os.path.isdir(INPUT_DIR):
        print(f"Error: '{INPUT_DIR}' is not a directory.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    image_paths_to_process = []
    for root, _, files in os.walk(INPUT_DIR):
        for filename in files:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')):
                full_image_path = os.path.join(root, filename)
                relative_image_path = os.path.relpath(full_image_path, INPUT_DIR)
                image_paths_to_process.append((full_image_path, relative_image_path))

    if not image_paths_to_process:
        print(f"No image files found in '{INPUT_DIR}' or its subdirectories.")
        return

    print(f"Found {len(image_paths_to_process)} images to watermark.")

    for full_path, relative_path in image_paths_to_process:
        # Create corresponding subdirectories in the output folder
        output_sub_directory = os.path.join(OUTPUT_DIR, os.path.dirname(relative_path))
        os.makedirs(output_sub_directory, exist_ok=True)

        base_filename, file_extension = os.path.splitext(os.path.basename(relative_path))
        output_filename = base_filename + "_watermarked.jpg" # Save as JPG
        output_path = os.path.join(output_sub_directory, output_filename)
        
        # It's good to print which file is being processed, especially for many files
        print(f"---\nProcessing: {full_path}")
        add_watermark_to_image(full_path, output_path)

    print("\nBatch watermarking complete.")
    print(f"Watermarked images are saved in '{OUTPUT_DIR}'.")

if __name__ == "__main__":
    main() 