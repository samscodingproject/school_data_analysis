# routes.py

from docx import Document
from app.analysis import perform_comprehensive_analysis
from .utils import save_temp_files
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, flash, send_file, current_app, session, stream_with_context, Response
import os
import pandas as pd
from .report_generator import generate_student_report
from scipy.stats import zscore
import logging
logging.basicConfig(level=logging.INFO)
import re
import tempfile
from .analysis import perform_comprehensive_analysis, preprocess_data
from .analysis import nan_to_none, replace_nan



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
    print("Upload function called")
    attendance_file = request.files.get('attendanceFile')
    marks_file = request.files.get('marksFile')

    if not attendance_file or not marks_file:
        error_message = 'Missing files. Please make sure to select and upload both attendance and marks files before submitting the form.'
        print(error_message)
        return jsonify({'error': error_message}), 400

    if not is_file_size_allowed(attendance_file) or not is_file_size_allowed(marks_file):
        max_size_mb = MAX_FILE_SIZE / (1024 * 1024)
        error_message = f'File size exceeds the limit. Please ensure each file is under {max_size_mb} MB.'
        print(error_message)
        return jsonify({'error': error_message}), 400

    try:
        # Extract threshold values from form data
        low_attendance_threshold = float(request.form.get('lowAttendanceThreshold', 85))
        high_attendance_threshold = float(request.form.get('highAttendanceThreshold', 95))
        low_marks_threshold = float(request.form.get('lowMarksThreshold', -1.5))
        high_marks_threshold = float(request.form.get('highMarksThreshold', 1.2))
        print(f"Extracted threshold values: Low Attendance Threshold: {low_attendance_threshold}, High Attendance Threshold: {high_attendance_threshold}, Low Marks Threshold: {low_marks_threshold}, High Marks Threshold: {high_marks_threshold}")

        session['low_attendance_threshold'] = low_attendance_threshold
        session['high_attendance_threshold'] = high_attendance_threshold
        session['low_marks_threshold'] = low_marks_threshold
        session['high_marks_threshold'] = high_marks_threshold

        # Save files for processing
        import os
        import tempfile
        from uuid import uuid4

        temp_dir = tempfile.gettempdir()

        # Save the original attendance file
        attendance_filename = f"attendance_{uuid4().hex}.xlsx"
        temp_attendance_path = os.path.join(temp_dir, attendance_filename)
        attendance_file.save(temp_attendance_path)

        # Save a copy of the attendance file
        attendance_file.stream.seek(0)  # Reset stream before re-saving
        additional_attendance_filename = f"additional_attendance_{uuid4().hex}.xlsx"
        additional_attendance_path = os.path.join(temp_dir, additional_attendance_filename)
        attendance_file.save(additional_attendance_path)

        # Save the original marks file
        marks_filename = f"marks_{uuid4().hex}.xlsx"
        temp_marks_path = os.path.join(temp_dir, marks_filename)
        marks_file.save(temp_marks_path)

        # Save a copy of the marks file
        marks_file.stream.seek(0)  # Reset stream before re-saving
        additional_marks_filename = f"additional_marks_{uuid4().hex}.xlsx"
        additional_marks_path = os.path.join(temp_dir, additional_marks_filename)
        marks_file.save(additional_marks_path)

        session['attendance_file'] = temp_attendance_path
        session['marks_file'] = temp_marks_path
        session['additional_attendance_file'] = additional_attendance_path
        session['additional_marks_file'] = additional_marks_path

        print(f"Saved temporary files: Attendance: {temp_attendance_path}, Marks: {temp_marks_path}, Additional Attendance: {additional_attendance_path}, Additional Marks: {additional_marks_path}")

        # Perform comprehensive analysis with the new thresholds
        analysis_stream = perform_comprehensive_analysis(
            temp_attendance_path, temp_marks_path,
            low_attendance_threshold, high_attendance_threshold,
            low_marks_threshold, high_marks_threshold
        )

        # Stream analysis logs and results back to the client
        return Response(stream_with_context(analysis_stream), content_type='text/event-stream')

    except KeyError as e:
        error_message = f"The required column \"{str(e).strip('[]')}\" is missing from the file."
        print(error_message)
        return jsonify({'error': error_message}), 400

    except FileNotFoundError as e:
        error_message = f"File not found: {str(e)}. Please check if the uploaded files exist and try again."
        print(error_message)
        return jsonify({'error': error_message}), 500

    except PermissionError as e:
        error_message = f"Permission denied: {str(e)}. Please ensure the server has write permissions for the temporary directory."
        print(error_message)
        return jsonify({'error': error_message}), 500

    except ValueError as e:
        error_message = f"Invalid data: {str(e)}. Please check the contents of the uploaded files and ensure they are in the expected format."
        print(error_message)
        return jsonify({'error': error_message}), 500

    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}. Please try again or contact support for assistance."
        print(error_message)
        return jsonify({'error': error_message}), 500

def cleanup_files(temp_marks_file, temp_attendance_file):
    if temp_marks_file and os.path.exists(temp_marks_file):
        os.remove(temp_marks_file)
    if temp_attendance_file and os.path.exists(temp_attendance_file):
        os.remove(temp_attendance_file)


@main.route('/download_report')
def download_report():
    logging.info("Entering download_report route")
    if 'additional_marks_file' not in session or 'additional_attendance_file' not in session:
        flash("No data available. Please upload and analyze files first.", "warning")
        logging.info("No additional_marks_file or additional_attendance_file found in session")
        return redirect(url_for('main.index'))

    additional_marks_file = session.get('additional_marks_file')
    if not os.path.exists(additional_marks_file):
        flash("Additional marks file does not exist. Please re-upload and analyze your files.", "error")
        logging.error(f"File {additional_marks_file} not found")
        return redirect(url_for('main.index'))

    try:
        additional_marks_df = pd.read_excel(additional_marks_file)

        # Data validation checks
        required_columns = ['StudentID', 'Subject', 'T1Weight', 'T2Weight', 'T3Weight', 'FinalMark']
        missing_columns = [col for col in required_columns if col not in additional_marks_df.columns]
        if missing_columns:
            error_message = f"Missing columns in the additional data: {', '.join(missing_columns)}. Please check the uploaded file."
            flash(error_message, "error")
            logging.error(error_message)
            return redirect(url_for('main.index'))

        # Data cleaning and preprocessing
        additional_marks_df = additional_marks_df.dropna(subset=['StudentID', 'Subject'])
        additional_marks_df['StudentID'] = additional_marks_df['StudentID'].astype(int)
        additional_marks_df['Subject'] = additional_marks_df['Subject'].str.strip()

        # Print the number of final marks entries for each subject
        print("\nNumber of final marks entries for each subject (additional data):")
        subject_final_marks_counts = additional_marks_df.groupby('Subject')['FinalMark'].count().reset_index()
        for _, row in subject_final_marks_counts.iterrows():
            subject = row['Subject']
            final_marks_count = row['FinalMark']
            print(f"{subject}: {final_marks_count}")

        additional_marks_df['CalculatedFinalMark'] = additional_marks_df[['T1Weight', 'T2Weight', 'T3Weight']].sum(axis=1, skipna=True)
        additional_marks_df['zScore'] = additional_marks_df.groupby('Subject')['CalculatedFinalMark'].transform(lambda x: zscore(x[x.notna()], ddof=1))
        additional_marks_df['zScore'] = additional_marks_df['zScore'].fillna(0)
        additional_marks_df = additional_marks_df.round(2)

        low_marks_threshold = session.get('low_marks_threshold', -1.5)
        students_multiple_low = additional_marks_df[additional_marks_df['zScore'] < low_marks_threshold].groupby('StudentID').filter(lambda x: len(x) > 1)['StudentID'].unique()

        print(f"Number of students with multiple subjects having z-score < {low_marks_threshold}: {len(students_multiple_low)}")
        print("Students with multiple low z-scores:", students_multiple_low)

        additional_marks_df = additional_marks_df[additional_marks_df['StudentID'].isin(students_multiple_low)]

        print("\nAfter filtering for students with multiple low z-scores:")
        print(additional_marks_df)
        print("Additional Marks DataFrame shape:", additional_marks_df.shape)
        print("Additional Marks DataFrame columns:", additional_marks_df.columns)

        # Print the number of final marks entries for each subject after filtering
        print("\nNumber of final marks entries for each subject after filtering:")
        subject_final_marks_counts = additional_marks_df.groupby('Subject')['FinalMark'].count().reset_index()
        for _, row in subject_final_marks_counts.iterrows():
            subject = row['Subject']
            final_marks_count = row['FinalMark']
            print(f"{subject}: {final_marks_count}")

        print("\nStudents in additional_marks_df after filtering:", additional_marks_df['StudentID'].unique())

        print("Additional Marks DataFrame shape after filtering:", additional_marks_df.shape)
        print("Additional Marks DataFrame columns after filtering:", additional_marks_df.columns)
        print(f"Students in additional_marks_df: {additional_marks_df['StudentID'].unique()}")

        # Print the average z-score for each subject
        print("Average z-score for each subject:")
        subject_z_scores = additional_marks_df.groupby('Subject')['zScore'].mean().reset_index()
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
                subject_z_scores = additional_marks_df[additional_marks_df['Subject'] == subject]['zScore']
                print("Raw z-scores (sorted from lowest to highest):")
                print(sorted(subject_z_scores.dropna().tolist()))

        print("Generating report...")

        # Load attendance data (if available)
        additional_attendance_file = session.get('additional_attendance_file')
        if additional_attendance_file:
            attendance_df = pd.read_excel(additional_attendance_file)
            attendance_df = attendance_df.dropna(subset=['StudentID', 'Class'])
            attendance_df['StudentID'] = attendance_df['StudentID'].astype(int)
            attendance_df['Class'] = attendance_df['Class'].str.strip()

            # Remove the trailing 'a' from the class names in the attendance data
            attendance_df['Class'] = attendance_df['Class'].apply(lambda x: re.sub(r'a$', '', x))

            # Map the classes in the attendance data to their respective subjects
            class_subject_mapping = additional_marks_df.groupby('Class')['Subject'].unique().to_dict()
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

        combined_report = generate_student_report(additional_marks_df, students_multiple_low, attendance_df, overall_attendance)

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


from .analysis import preprocess_data, get_student_marks, get_student_attendance

@main.route('/get_students', methods=['GET'])
def get_students():
    try:
        attendance_file = session.get('attendance_file')
        if not attendance_file:
            return jsonify({'error': 'No data available'}), 400
        
        attendance_df = pd.read_pickle(attendance_file)
        
        if 'StudentName' in attendance_df.columns:
            students = attendance_df[['StudentID', 'StudentName']].drop_duplicates().to_dict(orient='records')
        else:
            students = attendance_df[['StudentID']].drop_duplicates().to_dict(orient='records')
            for student in students:
                student['StudentName'] = ''
        
        return jsonify(students)
    except Exception as e:
        print(f"Error fetching students: {e}")
        return jsonify({'error': str(e)}), 500
    

@main.route('/search_students', methods=['GET'])
def search_students():
    try:
        query = request.args.get('query', '').strip().lower()
        
        # Read the DataFrames from the temporary files
        marks_file = session.get('marks_file')
        attendance_file = session.get('attendance_file')

        if not marks_file or not attendance_file:
            return jsonify({'error': 'No data available'}), 400

        marks_df = pd.read_pickle(marks_file)
        attendance_df = pd.read_pickle(attendance_file)

        # Filter students based on the search query
        students = attendance_df[
            (attendance_df['StudentID'].astype(str).str.contains(query))
        ]

        # Prepare the student data
        student_data = []
        for _, row in students.iterrows():
            student_id = row['StudentID']
            student_name = row.get('StudentName', '')  # Use an empty string if 'StudentName' is not available
            marks = get_student_marks(student_id, marks_df)
            attendance = get_student_attendance(student_id, attendance_df)

            student_data.append({
                'StudentID': student_id,
                'StudentName': student_name,
                'Marks': marks,
                'Attendance': attendance
            })

        # Convert NaN values to None using the replace_nan function
        student_data = replace_nan(student_data)

        return jsonify({'students': student_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500