from setuptools import setup, find_packages

setup(
    name="jarvis-dev",
    version="0.1.7",
    packages=find_packages(),
    py_modules=['cli'],
    install_requires=[
        "typer", "rich", "requests", "watchdog", "sounddevice", "scipy", 
        "numpy", "sentence-transformers", "faiss-cpu", "SpeechRecognition", 
        "prompt_toolkit", "dropbox", "google-api-python-client", "google-auth-oauthlib",
        "paramiko", "psutil", "Pillow", "keyring"
    ],
    entry_points={
        'console_scripts': [
            'jarvis=cli:app',
        ],
    },
)
