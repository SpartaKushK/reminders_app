# setup.py at the root level
from setuptools import setup, find_packages

setup(
    name="my_reminder_app",
    version="0.1.0",
    description="An app that reads unread messages, generates reminders using Gemini, and creates reminders on macOS.",
    author="Kush Khamesra",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pandas",
        "google-generativeai",
        "tenacity",
        'tkinter',
        'sqlite3',
        # Include other dependencies
    ],
    entry_points={
        'console_scripts': [
            'my_reminder_app=reminder_app.main:main'
        ],
    },
    setup_requires=['py2app'],
    options={
        'py2app': {
            'argv_emulation': True,
            'packages': ['pandas', 'google.generativeai', 'tenacity', 'tkinter'],
            'iconfile': 'app_icon.icns',  # Optional icon file
        }
    }
)
