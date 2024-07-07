# Tagline

This application is a powerful tool for automatically generating captions and tags for images using Google's Gemini AI models. It provides a user-friendly interface for processing multiple images, embedding metadata, and managing API keys.

You can obtain an API key from here: (https://aistudio.google.com/app/apikey)


## Features

- Supports multiple image formats: JPG, JPEG, PNG, and WebP
- Uses Google's Gemini AI models for generating captions and tags
- Embeds generated metadata directly into image files
- Manages multiple API keys with automatic switching
- Customizable safety settings for content generation
- Adjustable retry counts and delay between processing
- Option to save results as separate text files
- Queue system for processing multiple images
- Ability to copy results to clipboard
- Context menu for easy file management

## Main Functions

1. **Upload Images**: Select multiple images for processing.
2. **Add Photos**: Add more images to the existing queue.
3. **Generate Captions and Tags**: Automatically generate descriptive captions and relevant tags for each image.
4. **Embed Metadata**: Embed the generated captions and tags directly into the image files.
5. **Manage API Keys**: Add, remove, and switch between multiple Google API keys.
6. **Customize Settings**: Adjust safety settings, retry counts, delays, and other parameters.
7. **View Queue**: Monitor the processing queue with thumbnail previews.
8. **Retry Processing**: Retry processing for individual images with custom retry counts.
9. **Copy Results**: Easily copy generated captions and tags to the clipboard.

## Setup and Requirements

Please refer to the `setup.py` file for installation instructions and the `requirements.txt` file for a list of required packages.

Make sure you have Python 3.6 or higher installed on your system.
Install the required external tool:

For Windows: Download and install exiv2 from https://www.exiv2.org/download.html
For macOS: Use Homebrew to install exiv2 with brew install exiv2
For Linux: Use your package manager to install exiv2 (e.g., sudo apt-get install exiv2 for Ubuntu)

Place the app.py file in your project directory.
Create a virtual environment (recommended):

python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

Install the required packages:
pip install -r requirements.txt

Run the setup:
python setup.py install

Run the application:
python app.py



## Usage

1. Launch the application by running `python app.py`.
2. Add your Google API key(s) in the settings.
3. Upload images using the "Upload Images" button.
4. Adjust settings as needed in the "Extra Settings" menu.
5. Monitor the processing in the main window and queue display.
6. Use the context menu (right-click on images) for additional options.

This is meant as an educational app and is not to be used to abuse the API in any way. plz use this respectfully 

## Support Me

If you find this application useful, consider supporting the developer:

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/milky99)

Your support helps maintain and improve this project!

## License

[MIT License](LICENSE)
