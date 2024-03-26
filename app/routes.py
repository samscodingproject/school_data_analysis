from docx import Document
from app.analysis import perform_comprehensive_analysis
from .utils import allowed_file, save_temp_files
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, flash, send_file, current_app, session
import os
import pandas as pd
from .report_generator import generate_student_report
import pickle
from scipy.stats import zscore
import logging
logging.basicConfig(level=logging.INFO)
import re
import tempfile





main = Blueprint('main', __name__)

# Define a maximum file size in bytes (e.g., 5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 Megabytes

def is_file_size_allowed(file):
    """Check if file size is within acceptable limits."""
    file.seek(0, os.SEEK_END)  # Move pointer to end of file to get size
    file_size = file.tell()  # Get file size in bytes
    file.seek(0)  # Reset pointer to start of file
    return file_size <= MAX_FILE_SIZE

def check_file_content(file_path):
    try:
        df = pd.read_excel(file_path)
        required_columns = ['StudentID', 'Class']  # Adjust based on your logic for 'Subject'
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, f"Missing required column(s): {', '.join(missing_columns)}"
        return True, "File content is valid."
    except Exception as e:
        return False, f"Failed to read file: {e}"

@main.route('/scatter_plot.png')
def serve_scatter_plot():
    app_root = os.path.dirname(current_app.instance_path)
    image_path = os.path.join(app_root, 'scatter_plot.png')
    return send_file(image_path, mimetype='image/png')

@main.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@main.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads and return analysis results."""
    print("upload function called")

    attendance_file = request.files.get('attendanceFile')
    marks_file = request.files.get('marksFile')

    if not attendance_file or not marks_file:
        return jsonify({'error': 'Missing files. Please upload both attendance and marks files.'}), 400

    if not (allowed_file(attendance_file.filename) and allowed_file(marks_file.filename)):
        return jsonify({'error': 'File type not allowed. Please upload only XLS or XLSX files.'}), 400

    if not (is_file_size_allowed(attendance_file) and is_file_size_allowed(marks_file)):
        return jsonify({'error': 'One or more files exceed the maximum allowed size of 5MB.'}), 400

    try:
        # Temporarily save files for processing
        print("Saving files temporarily")
        temp_attendance_path, temp_marks_path = save_temp_files(attendance_file, marks_file)
        
        # Store the temporary file paths in the session
        session['attendance_file'] = temp_attendance_path
        session['marks_file'] = temp_marks_path
        
        # Perform analysis
        print("Calling perform_comprehensive_analysis")
        results = perform_comprehensive_analysis(temp_attendance_path, temp_marks_path)

        # Assuming results is a DataFrame, for example
        # Generate a temporary file path
        _, temp_file_path = tempfile.mkstemp(suffix='.pkl')

        # After saving the temporary files...
        logging.info(f"Temp attendance file saved at {temp_attendance_path}")
        logging.info(f"Temp marks file saved at {temp_marks_path}")
        session['attendance_file'] = temp_attendance_path
        session['marks_file'] = temp_marks_path

        
        # Use pickle to save the results dictionary
        with open(temp_file_path, 'wb') as f:
            pickle.dump(results, f)

        # Store the path to this temporary file in the session
        session['processed_data_file'] = temp_file_path

        # Return analysis results as JSON
        return jsonify(results)

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred during analysis'}), 500


def cleanup_files(temp_attendance_path, temp_marks_path):
    """Remove temporary files."""
    if temp_attendance_path and os.path.exists(temp_attendance_path):
        os.remove(temp_attendance_path)
    if temp_marks_path and os.path.exists(temp_marks_path):
        os.remove(temp_marks_path)



@main.route('/download_report')
def download_report():
    logging.info("Entering download_report route")
    if 'processed_data_file' not in session:
        flash("No data available. Please upload and analyze files first.", "warning")
        logging.info("No processed_data_file found in session")
        return redirect(url_for('main.index'))

    processed_data_file = session.get('processed_data_file')
    if not os.path.exists(processed_data_file):
        flash("Processed data file does not exist. Please re-upload and analyze your files.", "error")
        logging.error(f"File {processed_data_file} not found")
        return redirect(url_for('main.index'))

    try:
        print("Attempting to load results from session['processed_data_file']")
        results = pd.read_pickle(session['processed_data_file'])
        low_z_scores_data = results['low_z_scores']
        low_z_scores_df = pd.DataFrame(low_z_scores_data)

        marks_file = session.get('marks_file')
        if marks_file:
            marks_df = pd.read_excel(marks_file)
        else:
            raise ValueError("Original marks file not found in the session.")

        # Data validation checks
        required_columns = ['StudentID', 'Subject', 'T1Weight', 'T2Weight', 'T3Weight', 'FinalMark']
        missing_columns = [col for col in required_columns if col not in marks_df.columns]
        if missing_columns:
            error_message = f"Missing columns in the data: {', '.join(missing_columns)}. Please check the uploaded file."
            flash(error_message, "error")
            logging.error(error_message)
            return redirect(url_for('main.index'))

        # Data cleaning and preprocessing
        marks_df = marks_df.dropna(subset=['StudentID', 'Subject'])  # Drop rows with missing StudentID or Subject
        marks_df['StudentID'] = marks_df['StudentID'].astype(int)  # Convert StudentID to integer
        marks_df['Subject'] = marks_df['Subject'].str.strip()  # Remove leading/trailing spaces from Subject

        # Print the number of final marks entries for each subject
        print("\nNumber of final marks entries for each subject:")
        subject_final_marks_counts = marks_df.groupby('Subject')['FinalMark'].count().reset_index()
        for _, row in subject_final_marks_counts.iterrows():
            subject = row['Subject']
            final_marks_count = row['FinalMark']
            print(f"{subject}: {final_marks_count}")

        marks_df['CalculatedFinalMark'] = marks_df[['T1Weight', 'T2Weight', 'T3Weight']].sum(axis=1, skipna=True)
        marks_df['zScore'] = marks_df.groupby('Subject')['CalculatedFinalMark'].transform(lambda x: zscore(x[x.notna()], ddof=1))
        marks_df['zScore'] = marks_df['zScore'].fillna(0)
        marks_df = marks_df.round(2)

        print("Initial marks_df shape:", marks_df.shape)
        print("Initial marks_df columns:", marks_df.columns)

        biology_df = marks_df[marks_df['Subject'] == 'Biology']
        print("inital biology dataframe:", biology_df)

        # Create a mapping between classes and subjects from the marks data
        class_subject_mapping = marks_df.groupby('Class')['Subject'].unique().to_dict()

        # Create a list of students with multiple subjects having z-score < -1.2
        students_multiple_low = marks_df[marks_df['zScore'] < -1.2].groupby('StudentID').filter(lambda x: len(x) > 1)['StudentID'].unique()

        print(f"Number of students with multiple subjects having z-score < -1.2: {len(students_multiple_low)}")
        print("Students with multiple low z-scores:", students_multiple_low)

        marks_df = marks_df[marks_df['StudentID'].isin(students_multiple_low)]

        print("\nAfter filtering for students with multiple low z-scores:")
        print(marks_df)
        print("Marks DataFrame shape:", marks_df.shape)
        print("Marks DataFrame columns:", marks_df.columns)

        # Print the number of final marks entries for each subject after filtering
        print("\nNumber of final marks entries for each subject after filtering:")
        subject_final_marks_counts = marks_df.groupby('Subject')['FinalMark'].count().reset_index()
        for _, row in subject_final_marks_counts.iterrows():
            subject = row['Subject']
            final_marks_count = row['FinalMark']
            print(f"{subject}: {final_marks_count}")

        print("\nStudents in marks_df after filtering:", marks_df['StudentID'].unique())


        print("Marks DataFrame shape after filtering:", marks_df.shape)
        print("Marks DataFrame columns after filtering:", marks_df.columns)
        print(f"Students in marks_df: {marks_df['StudentID'].unique()}")

          # Print the average z-score for each subject
        print("Average z-score for each subject:")
        subject_z_scores = marks_df.groupby('Subject')['zScore'].mean().reset_index()
        for _, row in subject_z_scores.iterrows():
            subject = row['Subject']
            avg_z_score = row['zScore']
            print(f"{subject}: {avg_z_score:.2f}")

        # Identify subjects with an average z-score of 0
        subjects_with_zero_avg = subject_z_scores[subject_z_scores['zScore'] == 0]['Subject'].tolist()

        if subjects_with_zero_avg:
            print("\nSubjects with an average z-score of 0:")
            for subject in subjects_with_zero_avg:
                print(f"\n{subject}:")
                subject_z_scores = marks_df[marks_df['Subject'] == subject]['zScore']
                print("Raw z-scores (sorted from lowest to highest):")
                print(sorted(subject_z_scores.dropna().tolist()))


        print("Generating report...")

        # Load attendance data (if available)
        attendance_file = session.get('attendance_file')
        if attendance_file:
            attendance_df = pd.read_excel(attendance_file)
            attendance_df = attendance_df.dropna(subset=['StudentID', 'Class'])  # Drop rows with missing StudentID or Class
            attendance_df['StudentID'] = attendance_df['StudentID'].astype(int)  # Convert StudentID to integer
            attendance_df['Class'] = attendance_df['Class'].str.strip()  # Remove leading/trailing spaces from Class

            # Remove the trailing 'a' from the class names in the attendance data
            attendance_df['Class'] = attendance_df['Class'].apply(lambda x: re.sub(r'a$', '', x))

            # Map the classes in the attendance data to their respective subjects
            attendance_df['Subject'] = attendance_df['Class'].map(class_subject_mapping)

            # Drop rows where the subject is not found in the mapping
            attendance_df = attendance_df.dropna(subset=['Subject'])

            # Rename the attendance percentage column
            attendance_df = attendance_df.rename(columns={'Percentage': 'AttendancePercentage'})

            # Calculate overall attendance percentage for each student
            overall_attendance = attendance_df.groupby('StudentID')['AttendancePercentage'].mean().reset_index()
            overall_attendance = overall_attendance.round(2)
        else:
            attendance_df = None
            overall_attendance = None

        combined_report = generate_student_report(marks_df, students_multiple_low, attendance_df, overall_attendance)

        # Validate the generated Word document
        try:
            document = Document(combined_report)
        except Exception as e:
            flash("The generated Word document is corrupted or invalid. Please try again.", "error")
            logging.error(f"Error validating Word document: {e}")
            return redirect(url_for('main.index'))

        # Save the validated Word document to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
            temp_file_path = temp_file.name
            document.save(temp_file_path)

        print("Report generated, sending file to client")
        return send_file(temp_file_path, as_attachment=True, download_name='Student_Reports.docx', mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        flash("Failed to generate the report.", "error")
        print(f"Report generation failed: {e}")
        return redirect(url_for('main.index'))