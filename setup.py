from setuptools import setup, find_packages

setup(
    name="Image Captioning and Tagging App",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "tkinter",
        "Pillow",
        "google-generativeai",
        "cryptography",
        "exif",
        "pywin32",
    ],
    entry_points={
        "console_scripts": [
            "image_caption_app=app:main",
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="An application for automatically generating captions and tags for images using Google's Gemini AI models.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/image-caption-app",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)