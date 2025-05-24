import logging

LOG_FILE_PATH = "app.log" # Define your log file path

def setup_global_logger(log_file_path=LOG_FILE_PATH, level=logging.INFO):
    """
    Configures a global logger to write to a specified file.
    """
    # Get the root logger
    logger = logging.getLogger() # Get the root logger
    logger.setLevel(level) # Set the minimum logging level

    # Prevent duplicate handlers if this function is called multiple times
    if logger.hasHandlers():
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == log_file_path:
                print("File logger already configured.")
                return
            # Be careful with clearing all handlers if other libraries or Uvicorn also set them up.
            # Often, just adding your file handler is enough.

    # Create a file handler to write to the log file
    file_handler = logging.FileHandler(log_file_path, mode='a')
    file_handler.setLevel(level) # Set level for this specific handler

    # Create a formatter to define the log message format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)

    # Add a console handler as well if you want to see logs in console AND file
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.DEBUG) # Or your desired console level
    # console_handler.setFormatter(formatter) # Use the same or a different formatter
    # logger.addHandler(console_handler)

    print(f"Global file logger configured. Logging to: {log_file_path} with level: {logging.getLevelName(level)}")

