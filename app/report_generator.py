from docx import Document
from docx.shared import Inches
import io
import pandas as pd
from scipy.stats import zscore

def generate_student_report(marks_df, student_ids, attendance_df=None, overall_attendance=None):
    document = Document()

    print(f"Number of student IDs: {len(student_ids)}")  # Debugging statement

    for student_id in student_ids:
        print(f"Generating report for student ID: {student_id}")  # Debugging statement
        student_marks_data = marks_df[marks_df['StudentID'] == student_id]
        print(f"Number of subjects for student {student_id}: {len(student_marks_data)}")  # Debugging statement

        # Check if 'Student Name' exists and is not empty, otherwise use 'StudentID'
        if 'Student Name' in student_marks_data.columns and not pd.isnull(student_marks_data['Student Name'].values[0]):
            student_identifier = student_marks_data['Student Name'].values[0]
        else:
            student_identifier = str(student_id)

        # Add a header with the student's identifier
        document.add_heading(f"# {student_identifier}", level=0)

        # Leave space for adding an image
        # document.add_paragraph("(Image goes here)")

        # Academic Results 2024 Section
        document.add_heading('Academic Results 2024:', level=1)
        academic_results_table = document.add_table(rows=1, cols=6)
        hdr_cells = academic_results_table.rows[0].cells
        hdr_cells[0].text = 'Subject'
        hdr_cells[1].text = 'Term 1 Weighted Mark'
        hdr_cells[2].text = 'Term 2 Weighted Mark'
        hdr_cells[3].text = 'Term 3 Weighted Mark'
        hdr_cells[4].text = 'Final Course Mark'
        hdr_cells[5].text = 'Final Course z-Score'

        for _, row in student_marks_data.iterrows():
            row_cells = academic_results_table.add_row().cells
            row_cells[0].text = row['Subject']
            row_cells[1].text = str(row['T1Weight'])
            row_cells[2].text = str(row['T2Weight'])
            row_cells[3].text = str(row['T3Weight'])
            row_cells[4].text = str(row['CalculatedFinalMark'])
            row_cells[5].text = str(row['zScore'])

        # Attendance 2024 Section
        document.add_heading('Attendance 2024:', level=1)
        attendance_table = document.add_table(rows=1, cols=2)
        hdr_cells = attendance_table.rows[0].cells
        hdr_cells[0].text = 'Overall Attendance'
        hdr_cells[1].text = 'Percentage'

        if overall_attendance is not None:
            student_overall_attendance = overall_attendance[overall_attendance['StudentID'] == student_id]['AttendancePercentage'].values[0]
            overall_attendance_row = attendance_table.add_row().cells
            overall_attendance_row[0].text = 'Overall Attendance'
            overall_attendance_row[1].text = str(student_overall_attendance)

        if attendance_df is not None:
            student_attendance_data = attendance_df[attendance_df['StudentID'] == student_id]
            for _, row in student_attendance_data.iterrows():
                subject = row['Subject']
                attendance_percentage = row['AttendancePercentage']
                new_row = attendance_table.add_row().cells
                new_row[0].text = subject
                new_row[1].text = str(attendance_percentage)

        # Deputy Principal Sign Off
        document.add_paragraph("Deputy Principal Sign Off: ______________________________")

        # Add a page break before the next student's report, if there are more students
        if student_id != student_ids[-1]:
            document.add_page_break()

    print("Report generation completed")  # Debugging statement

    # Save the document to a BytesIO object and return it
    file_stream = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream