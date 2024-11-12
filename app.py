import os
import random
import re
import subprocess
import tempfile
import zipfile
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
from github import Github
from colorama import init

# Initialize colorama for colorful terminal output
init(autoreset=True)

# Define some colors for syntax highlighting
COLORS = {
    'keyword': (0, 0, 255),    # Blue for keywords
    'string': (0, 128, 0),     # Green for strings
    'comment': (128, 128, 128),# Gray for comments
    'default': (0, 0, 0)       # Black for regular code
}

KEYWORDS = r'\b(def|class|import|from|return|if|else|for|while|try|except|with|as|lambda)\b'
STRING_PATTERN = r'".*?"|\'.*?\''
COMMENT_PATTERN = r'<!--.*?-->|//.*|/\*.*?\*/'

# Extensions allowed for processing
ALLOWED_EXTENSIONS = ['.py', '.js', '.html', '.css', '.java', '.cpp', '.php', '.ts', '.rb', '.go']
MAX_HEIGHT = 800  # Maximum height before splitting into multiple pages
FONT_SIZE = 12  # Font size for the code

# Function to clone a GitHub repository
def clone_github_repo(repo_url, clone_path):
    try:
        subprocess.run(["git", "clone", repo_url, clone_path], check=True)
    except subprocess.CalledProcessError as e:
        st.error(f"Git Clone failed: {e}")
        st.error(f"Error Output: {e.output}")

def random_color():
    """Generate a random color in RGB format."""
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def syntax_highlight(code):
    """Apply syntax highlighting to code."""
    highlighted_code = []
    lines = code.split('\n')
    for line in lines:
        parts = []
        position = 0  # Keep track of the current position in the line

        # Match keywords, strings, and comments in the line
        while position < len(line):
            # Check for keywords
            keyword_match = re.match(KEYWORDS, line[position:])
            if keyword_match:
                parts.append((line[position:position + len(keyword_match.group(0))], 'keyword'))
                position += len(keyword_match.group(0))
                continue

            # Check for strings
            string_match = re.match(STRING_PATTERN, line[position:])
            if string_match:
                parts.append((line[position:position + len(string_match.group(0))], 'string'))
                position += len(string_match.group(0))
                continue

            # Check for comments
            comment_match = re.match(COMMENT_PATTERN, line[position:])
            if comment_match:
                parts.append((line[position:position + len(comment_match.group(0))], 'comment'))
                position += len(comment_match.group(0))
                continue

            # Default case (regular code)
            parts.append((line[position], 'default'))
            position += 1

        highlighted_code.append(parts)

    return highlighted_code

def get_text_size(draw, font, text):
    """Return the width and height of the text when drawn with the given font."""
    width, height = draw.textbbox((0, 0), text, font=font)[2:4]
    return width, height

def screenshot_code_files(folder_path, log_area, image_area):
    log = ""
    st.write(f"Starting to process the folder: {folder_path}")

    # Ensure folder exists
    if not os.path.exists(folder_path):
        log += f"Error: The path {folder_path} does not exist.\n"
        log_area.text_area("Logs", value=log, height=300, disabled=True)
        return log, None

    try:
        font = ImageFont.truetype("arial.ttf", FONT_SIZE)
    except IOError:
        font = ImageFont.load_default()
        log += "Warning: Default font loaded.\n"

    base_dir = os.path.dirname(os.path.realpath(__file__))  # Base directory of the script
    image_folder = os.path.join(base_dir, "output_images")
    os.makedirs(image_folder, exist_ok=True)

    # Debug: log the image folder creation
    log += f"Images will be saved to: {image_folder}\n"
    log_area.text_area("Logs", value=log, height=300, disabled=True)

    for root, dirs, files in os.walk(folder_path):
        log += f"Checking directory: {root}\n"

        if 'node_modules' in root:
            log += "Skipping 'node_modules' directory\n"
            continue

        if not files:
            log += f"No files in directory: {root}\n"

        for file in files:
            file_path = os.path.join(root, file)
            file_extension = os.path.splitext(file)[1].lower()

            if file_extension not in ALLOWED_EXTENSIONS:
                log += f"Skipping file (unsupported extension): {file_path}\n"
                continue

            log += f"Processing file: {file_path}\n"
            log_area.text_area("Logs", value=log, height=300, disabled=True)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()

                highlighted_code = syntax_highlight(code)
                img_width = 800
                img = Image.new('RGB', (img_width, 1), color=(255, 255, 255))
                draw = ImageDraw.Draw(img)

                total_height = 0
                line_height = FONT_SIZE + 2
                for line_parts in highlighted_code:
                    line_max_height = 0
                    for part, part_type in line_parts:
                        _, height = get_text_size(draw, font, part)
                        line_max_height = max(line_max_height, height)
                    total_height += line_max_height + 2

                total_height = min(total_height, MAX_HEIGHT)

                img = Image.new('RGB', (img_width, total_height), color=(255, 255, 255))
                draw = ImageDraw.Draw(img)

                y_position = 10
                page_number = 1
                for line_parts in highlighted_code:
                    x_position = 10
                    for part, part_type in line_parts:
                        color = COLORS.get(part_type, COLORS['default'])
                        draw.text((x_position, y_position), part, font=font, fill=color)

                        text_bbox = draw.textbbox((x_position, y_position), part, font=font)
                        text_width = text_bbox[2] - text_bbox[0]
                        x_position += text_width
                    y_position += line_height

                    if y_position >= MAX_HEIGHT:
                        output_path = os.path.join(image_folder, f"{file}_page_{page_number}.png")
                        img.save(output_path)
                        log += f"Image saved to: {output_path}\n"
                        log_area.text_area("Logs", value=log, height=300, disabled=True)
                        page_number += 1
                        img = Image.new('RGB', (img_width, MAX_HEIGHT), color=(255, 255, 255))
                        draw = ImageDraw.Draw(img)
                        y_position = 10

                if y_position > 10:
                    output_path = os.path.join(image_folder, f"{file}_page_{page_number}.png")
                    img.save(output_path)
                    log += f"Image saved to: {output_path}\n"
                    log_area.text_area("Logs", value=log, height=300, disabled=True)

                # Debug: Check if images are saved
                image_files = sorted(os.listdir(image_folder))
                log += f"Images in folder: {image_files}\n"
                log_area.text_area("Logs", value=log, height=300, disabled=True)

                # Update the image display in real-time as each image is saved
                with image_area:
                    st.header("Generated Images")
                    cols = st.columns(3)  # Create a 3-column grid
                    for idx, img_file in enumerate(image_files):
                        img_path = os.path.join(image_folder, img_file)
                        cols[idx % 3].image(img_path, use_container_width=True)

            except Exception as e:
                log += f"Could not process {file_path}: {e}\n"
                log_area.text_area("Logs", value=log, height=300, disabled=True)

    return log, image_folder


# Function to delete all images in the given folder without confirmation
def delete_all_images(image_folder):
    # Ensure that image_folder exists and contains files
    if os.path.exists(image_folder):
        image_files = os.listdir(image_folder)
        if image_files:
            try:
                # Loop through the image folder and delete all images
                for img_file in image_files:
                    img_path = os.path.join(image_folder, img_file)
                    if os.path.isfile(img_path):
                        os.remove(img_path)
                        st.success(f"Deleted image: {img_file}")
                st.info("All images have been deleted.")
            except Exception as e:
                st.error(f"Error deleting images: {e}")
        else:
            st.info("No images found to delete.")
    else:
        st.error("The specified image folder does not exist.")


# Function to download all images in the folder
def download_all_images(image_folder):
    # Allow users to download the images
    from zipfile import ZipFile
    import shutil

    zip_filename = "images.zip"
    zip_filepath = os.path.join(image_folder, zip_filename)

    try:
        # Create a zip file containing all images
        with ZipFile(zip_filepath, 'w') as zipf:
            for img_file in os.listdir(image_folder):
                img_path = os.path.join(image_folder, img_file)
                if os.path.isfile(img_path):
                    zipf.write(img_path, os.path.basename(img_path))
        # Provide download link
        with open(zip_filepath, "rb") as f:
            st.download_button(
                label="Download All Images",
                data=f,
                file_name=zip_filename,
                mime="application/zip",
            )
    except Exception as e:
        st.error(f"Error creating zip: {e}")


def main():
    st.title("Code Screenshot Generator")

    # Initialize processing state if not already done
    if "processing" not in st.session_state:
        st.session_state.processing = False

    # Initialize image_folder as None to avoid UnboundLocalError
    image_folder = None

    # Radio button to select input type (Local Directory or GitHub Repository)
    choice = st.radio("Select Input Type", ("Local Directory", "GitHub Repository"))

    # Input fields and button are placed above the image and logs sections
    st.subheader("Enter the details below:")
    
    if choice == "Local Directory":
        directory = st.text_input("Enter directory path:") 
        generate_button = st.button("Generate Screenshots", disabled=st.session_state.processing, key="local_dir_generate")
    elif choice == "GitHub Repository":
        repo_url = st.text_input("Enter GitHub repository URL:")  
        generate_button = st.button("Generate Screenshots", disabled=st.session_state.processing, key="github_generate")

    # Layout with two columns (Image container and Log container)
    col1, col2 = st.columns([3, 1])

    with col1:  # Image Container
        image_area = st.empty()  # Placeholder for images

    with col2:  # Log Container
        log_area = st.empty()  # Placeholder for logs

    # Input handling and processing
    if generate_button:
        st.session_state.processing = True

        if choice == "Local Directory":
            log, image_folder = screenshot_code_files(directory, log_area, image_area)
        elif choice == "GitHub Repository":
            clone_path = tempfile.mkdtemp()
            clone_github_repo(repo_url, clone_path)
            log, image_folder = screenshot_code_files(clone_path, log_area, image_area)

        st.session_state.processing = False

    # Add delete and download buttons if image_folder is not None
    if image_folder:
        delete_button = st.button("Delete All Images")
        if delete_button:
            delete_all_images(image_folder)

        download_button = st.button("Download All Images")
        if download_button:
            download_all_images(image_folder)

if __name__ == "__main__":
    main()