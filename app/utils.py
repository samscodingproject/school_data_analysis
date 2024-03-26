import json
import numpy as np
import pandas as pd
from werkzeug.utils import secure_filename
import os

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'xls', 'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if pd.isnull(obj):
            return "N/A"  # Or use None for null
        if isinstance(obj, np.number):
            return obj.item()
        return json.JSONEncoder.default(self, obj)


def check_file_content(file_path):
    """
    Checks the content of the Excel file to ensure it has the required structure.
    Returns a tuple (bool, str) indicating whether the file is valid and a message.
    """
    try:
        df = pd.read_excel(file_path)
        
        # Example: Ensure specific required columns are present
        required_columns = ['StudentID', 'Subject', 'Marks']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"
        
        # Add more checks as needed, e.g., data types, empty values, etc.

        return True, "File content is valid."
    except Exception as e:
        return False, f"Failed to read file: {e}"
    
def save_temp_files(attendance_file, marks_file):
    attendance_filename = secure_filename(attendance_file.filename)
    marks_filename = secure_filename(marks_file.filename)
    temp_attendance_path = os.path.join('/tmp', attendance_filename)
    temp_marks_path = os.path.join('/tmp', marks_filename)
    attendance_file.save(temp_attendance_path)
    marks_file.save(temp_marks_path)
    return temp_attendance_path, temp_marks_path