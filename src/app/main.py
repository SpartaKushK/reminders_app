# # src/reminder_app/main.py
import tkinter as tk
from tkinter import messagebox
import logging
import sys
import os
from ui import ReminderUI


def setup_logging():
    """Setup logging configuration"""
    log_dir = os.path.expanduser("~/Library/Logs/ReminderApp")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "reminder_app.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


def check_requirements():
    """Check if all requirements are met"""
    errors = []

    # Check if running on macOS
    if sys.platform != 'darwin':
        errors.append(
            "This application requires macOS to access the Messages database.")

    # Check if Messages database exists
    messages_db_path = os.path.expanduser("~/Library/Messages/chat.db")
    if not os.path.exists(messages_db_path):
        errors.append(
            "Messages database not found. Make sure Messages app has been used.")

    # Check required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        errors.append("GOOGLE_API_KEY environment variable not set.")

    return errors


def main():
    """Main application entry point"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Smart Reminder Assistant...")

    # Check requirements
    requirement_errors = check_requirements()
    if requirement_errors:
        error_msg = "Application requirements not met:\n\n" + \
            "\n".join(f"• {error}" for error in requirement_errors)
        logger.error("Requirements check failed")

        # Show error in GUI if possible
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showerror("Requirements Error", error_msg)
        return 1

    try:
        # Create and run the application
        root = tk.Tk()

        # Set app icon and properties
        root.title("Smart Reminder Assistant")

        # Create the application
        app = ReminderUI(root)

        # Handle window closing
        def on_closing():
            logger.info("Application closing...")
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        # Start the application
        logger.info("Application started successfully")
        root.mainloop()

        logger.info("Application closed normally")
        return 0

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

        # Show error dialog if possible
        try:
            messagebox.showerror("Application Error",
                                 f"An unexpected error occurred:\n\n{str(e)}")
        except:
            pass

        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)


# from ui import ReminderUI
# import tkinter as tk


# def main():
#     root = tk.Tk()
#     app = ReminderUI(root)
#     root.mainloop()


# if __name__ == '__main__':
#     main()
