import pandas as pd
from scipy.stats import zscore, linregress
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from celery import Celery
import os
import re
from flask import jsonify, request, session
import json




app = Celery('tasks', broker='redis://localhost:6479')

matplotlib.use('Agg')  # Use the non-GUI Agg backend


def read_excel_file(file_path):
    try:
        return pd.read_excel(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

import tempfile
from flask import session

def preprocess_data(attendance_df, marks_df):
    try:
        print("\nPreprocessing data...")
        print("Initial Attendance DataFrame shape:", attendance_df.shape)
        print("Initial Marks DataFrame shape:", marks_df.shape)

        # Log initial data overview
        print("Initial attendance DataFrame sample:")
        print(attendance_df.head())

        # Validate required columns in marks DataFrame
        required_marks_columns = ['StudentID', 'Subject', 'Class', 'T1Weight', 'T2Weight', 'T3Weight']
        missing_marks_columns = [col for col in required_marks_columns if col not in marks_df.columns]
        if missing_marks_columns:
            raise ValueError(f"Missing required columns in marks data: {', '.join(missing_marks_columns)}")
        print("Required columns check passed for marks data.")

        # Validate required columns in attendance DataFrame
        required_attendance_columns = ['StudentID', 'Class', 'Percentage']
        missing_attendance_columns = [col for col in required_attendance_columns if col not in attendance_df.columns]
        if missing_attendance_columns:
            raise ValueError(f"Missing required columns in attendance data: {', '.join(missing_attendance_columns)}")
        print("Required columns check passed for attendance data.")

        # Calculate Final Marks
        marks_df['CalculatedFinalMark'] = marks_df['T1Weight'] + marks_df['T2Weight'] + marks_df['T3Weight']
        print("Calculated final marks.")

        # Filter Attendance Data
        print("\nFiltering Attendance Data...")
        filtered_attendance_df = attendance_df[(attendance_df['Class Time'] >= 1000) & (~attendance_df['Class'].str.contains("MEN"))]
        print("Filtered Attendance DataFrame shape:", filtered_attendance_df.shape)

        # Map 'Class' to 'Subject' in the attendance DataFrame
        class_to_subject = marks_df[['Class', 'Subject']].drop_duplicates().set_index('Class')['Subject'].to_dict()
        filtered_attendance_df['Subject'] = filtered_attendance_df['Class'].map(class_to_subject)
        print("Filtered unique values in 'Subject' column after mapping:", filtered_attendance_df['Subject'].unique())

        # Calculate Overall Attendance Percentage (without narrowing down to 'Overall' class only)
        # Assuming 'Absence Time' and 'Class Time' are columns that exist for all records
        filtered_attendance_df.loc[:, 'OverallAttendancePercentage'] = 100 - (filtered_attendance_df['Absence Time'] / filtered_attendance_df['Class Time'] * 100)
        print("Calculated overall attendance percentage for all records.")

        # Log final shapes and sample data
        print("\nPreprocessing complete.")
        print("Final Marks DataFrame shape:", marks_df.shape)
        print("Final Filtered Attendance DataFrame shape:", filtered_attendance_df.shape)
        print("Final DataFrames sample:")
        print(marks_df.head())
        print(filtered_attendance_df.head())

        # Store the DataFrames as temporary files and save the file paths in the session
        # Store the DataFrames as temporary files and save the file paths in the session
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as temp_marks_file:
            marks_df.to_pickle(temp_marks_file.name)
            session['marks_file'] = temp_marks_file.name

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as temp_attendance_file:
            filtered_attendance_df.to_pickle(temp_attendance_file.name)
            session['attendance_file'] = temp_attendance_file.name

        marks_df['zScore'] = marks_df.groupby('Subject')['CalculatedFinalMark'].transform(lambda x: zscore(x, ddof=1))


        return marks_df, filtered_attendance_df

    except ValueError as e:
        print(f"Error during preprocessing: {e}")
        # Return empty DataFrames in case of a ValueError
        return pd.DataFrame(), pd.DataFrame()

    except Exception as e:
        print(f"Error during preprocessing: {e}")
        # Return empty DataFrames in case of any other exception
        return pd.DataFrame(), pd.DataFrame()

def get_student_marks(student_id, marks_df):
    student_marks = marks_df[marks_df['StudentID'] == student_id]
    return student_marks[['Subject', 'CalculatedFinalMark', 'zScore']].to_dict(orient='records')

def get_student_attendance(student_id, attendance_df):
    student_attendance = attendance_df[attendance_df['StudentID'] == student_id]
    return student_attendance[['Subject', 'OverallAttendancePercentage']].to_dict(orient='records')

def identify_low_z_scores(marks_df, low_marks_threshold):
    """Identify entries with z-scores below the specified threshold."""
    marks_df['zScore'] = marks_df.groupby('Subject')['CalculatedFinalMark'].transform(lambda x: zscore(x, ddof=1))
    low_z_scores_df = marks_df[marks_df['zScore'] < low_marks_threshold]
    return low_z_scores_df

def identify_high_z_scores(marks_df, high_marks_threshold):
    """Identify entries with z-scores above the specified threshold."""
    marks_df['zScore'] = marks_df.groupby('Subject')['CalculatedFinalMark'].transform(lambda x: zscore(x, ddof=1))
    high_z_scores_df = marks_df[marks_df['zScore'] > high_marks_threshold]
    return high_z_scores_df

def calculate_year_group_attendance_summary(attendance_df):
    # Calculate the average attendance for each student
    student_attendance = attendance_df.groupby(['StudentID', 'School Year'])['Percentage'].mean().reset_index()
    
    # Calculate summary statistics for each year group
    year_group_summary = student_attendance.groupby('School Year')['Percentage'].agg(['mean', 'median', 'min', 'max', 'std']).reset_index()
    
    
    student_attendance['AboveThreshold'] = student_attendance['Percentage'] > 90
    attendance_above_90 = student_attendance.groupby('School Year')['AboveThreshold'].mean() * 100
    year_group_summary = year_group_summary.merge(attendance_above_90.reset_index(name='PercentageAbove90'), on='School Year', how='left')
    year_group_summary['PercentageAbove90'] = year_group_summary['PercentageAbove90'].fillna(0)
    
    # Generate a bar chart comparing the average attendance across year groups
    plt.figure(figsize=(8, 6))
    plt.hist(attendance_df['Percentage'], bins=20, alpha=0.7)
    plt.xlabel('Attendance Percentage')
    plt.ylabel('Number of Students')
    plt.title('Distribution of Attendance Percentages')
    
    # Save the histogram image to the static images folder
    static_folder = os.path.join(os.path.dirname(__file__), 'static', 'images')
    os.makedirs(static_folder, exist_ok=True)
    histogram_path = os.path.join(static_folder, 'attendance_distribution_histogram.png')
    plt.savefig(histogram_path)
    plt.close()
    
    return year_group_summary.to_dict(orient='records')

def identify_students_with_subjects_below_threshold(marks_df, low_marks_threshold):
    # Filter rows with z-scores below the specified low marks threshold
    low_z_scores = marks_df[marks_df['zScore'] < low_marks_threshold]
    
    # Group by StudentID and aggregate the subjects into a list
    subjects_below_threshold = low_z_scores.groupby('StudentID')['Subject'].apply(list).reset_index(name='Subjects')
    
    # Count the number of subjects below the threshold for each student
    subjects_below_threshold['SubjectCount'] = subjects_below_threshold['Subjects'].apply(len)
    
    # Sort the results by the number of subjects in descending order
    subjects_below_threshold = subjects_below_threshold.sort_values(by='SubjectCount', ascending=False)
    
    return subjects_below_threshold

def identify_students_below_low_attendance_threshold(attendance_df, low_attendance_threshold):
    print(f"Analyzing students below low attendance threshold: {low_attendance_threshold}%")
    below_threshold = attendance_df[attendance_df['Percentage'] < low_attendance_threshold]
    print(f"Found {len(below_threshold)} students below {low_attendance_threshold}% attendance.")
    
    students_below_threshold = (
        below_threshold.groupby('StudentID')
        .agg({
            'Subject': list,
            'Percentage': 'count'
        })
        .rename(columns={'Subject': 'Subjects', 'Percentage': 'SubjectCount'})
        .reset_index()
    )
    print(f"Details of students below threshold: {students_below_threshold}")
    return students_below_threshold


def identify_students_above_high_attendance_threshold(attendance_df, high_attendance_threshold):
    print(f"Analyzing students above high attendance threshold: {high_attendance_threshold}%")
    above_threshold = attendance_df[attendance_df['Percentage'] > high_attendance_threshold]
    print(f"Found {len(above_threshold)} students above {high_attendance_threshold}% attendance.")
    
    students_above_threshold = (
        above_threshold.groupby('StudentID')
        .agg({
            'Subject': list,
            'Percentage': 'count'
        })
        .rename(columns={'Subject': 'Subjects', 'Percentage': 'SubjectCount'})
        .reset_index()
    )
    print(f"Details of students above threshold: {students_above_threshold}")
    return students_above_threshold



def calculate_average_marks_by_class(marks_df):
    return marks_df.groupby('Class')['CalculatedFinalMark'].mean()

def generate_regression_explainer(slope, intercept, r_value, p_value, std_err):
    regression_explainer = ""
    
    # Slope
    regression_explainer += f"The slope ({slope:.2f}) indicates that for each additional percentage point in attendance, "
    regression_explainer += f"the model predicts a {slope:.2f} point increase in the final mark.\n\n"

    # Intercept
    regression_explainer += f"The intercept ({intercept:.2f}) suggests that students with zero percent attendance are predicted to score {intercept:.2f} points, "
    regression_explainer += "which may not be realistic and indicates the intercept's value in this context should be cautiously interpreted.\n\n"

    # R-value and R-squared
    r_squared = r_value ** 2
    regression_explainer += f"An R-value of {r_value:.2f} results in an R-squared (coefficient of determination) of {r_squared:.2f}, "
    regression_explainer += "indicating the proportion of the variance in the dependent variable (final mark) that is predictable from the independent variable (attendance percentage).\n\n"

    # P-value
    if p_value < 0.05:
        regression_explainer += f"With a P-value of {p_value:.4f}, the relationship between attendance and final marks is statistically significant, "
        regression_explainer += "meaning there's a low probability that this relationship is due to chance.\n\n"
    else:
        regression_explainer += f"With a P-value of {p_value:.4f}, the relationship between attendance and final marks is not statistically significant, "
        regression_explainer += "suggesting that any observed correlation may be due to chance.\n\n"

    # Standard Error
    regression_explainer += f"The standard error of the slope ({std_err:.2f}) measures the average distance that the observed values fall from the regression line. "
    regression_explainer += "A lower standard error indicates that the slope estimate is more precise.\n\n"

    return regression_explainer


def analyze_correlation_and_prepare_scatter_plot_data(attendance_df, marks_df):
    # Merge dataframes on 'StudentID'
    combined_df = pd.merge(marks_df, attendance_df[['StudentID', 'OverallAttendancePercentage']], on='StudentID', how='inner')
    
    # Ensure data is numeric and handle NaNs
    combined_df.dropna(subset=['CalculatedFinalMark', 'OverallAttendancePercentage'], inplace=True)
    
    final_mark = combined_df['CalculatedFinalMark']
    attendance_percentage = combined_df['OverallAttendancePercentage']
    
    # Optionally, remove outliers here if necessary
    
    # Calculate correlation
    correlation = final_mark.corr(attendance_percentage)
    
    # Check if data is sufficient for linear regression
    if len(final_mark) > 1 and len(attendance_percentage) > 1:
        # Perform linear regression
        slope, intercept, r_value, p_value, std_err = linregress(attendance_percentage, final_mark)
    else:
        slope, intercept, r_value, p_value, std_err = np.nan, np.nan, np.nan, np.nan, np.nan
    
    # Generate scatter plot
    plot_filename = 'scatter_plot.png'
    generate_scatter_plot(attendance_percentage.tolist(), final_mark.tolist(), slope, intercept, r_value, plot_filename)


    correlation_explainer = f"The correlation coefficient of {correlation:.2f} suggests "
    if abs(correlation) > 0.7:
        correlation_explainer += "a strong"
    elif abs(correlation) > 0.3:
        correlation_explainer += "a moderate"
    else:
        correlation_explainer += "a weak"
    correlation_explainer += " linear relationship between attendance percentage and final marks. "
    correlation_explainer += "A positive value indicates that higher attendance is associated with higher marks, while a negative value suggests the opposite."

    regression_explainer = generate_regression_explainer(slope, intercept, r_value, p_value, std_err)

    explainer_text = {
        'correlation': correlation_explainer,
        'regression': regression_explainer
    }
    # Ensure values are floats or N/A
    correlation_analysis = {
        'correlation': float(correlation) if not np.isnan(correlation) else 'N/A',
        'line_of_best_fit': {
            'slope': float(slope) if not np.isnan(slope) else 'N/A',
            'intercept': float(intercept) if not np.isnan(intercept) else 'N/A',
            'r_value': float(r_value) if not np.isnan(r_value) else 'N/A',
            'p_value': float(p_value) if not np.isnan(p_value) else 'N/A',
            'std_err': float(std_err) if not np.isnan(std_err) else 'N/A',
        },
        'explainer_text': explainer_text,  # Add explainer_text here
        'plot_filename': plot_filename
    }
    
    return correlation_analysis

def generate_scatter_plot(attendance_percentage, final_mark, slope, intercept, r_value, plot_filename):
    plt.figure(figsize=(9, 7))
    plt.scatter(attendance_percentage, final_mark, alpha=0.5, label='Student Data')
    
    # Calculate values for the line of best fit
    x_vals = np.linspace(min(attendance_percentage), max(attendance_percentage), 100)
    y_vals = intercept + slope * x_vals
    plt.plot(x_vals, y_vals, color='red', label=f'Line of Best Fit (R²={r_value**2:.2f})')  # Square the R-value for R-squared
    
    # Labels and Title
    plt.xlabel('Attendance Percentage')
    plt.ylabel('Final Mark')
    plt.title('Correlation between Student Attendance and Final Marks')

    # Legend
    plt.legend()

    # Save the plot to the specified path
    full_path = os.path.join('/Users/Sam/Desktop/New schools data analysis', plot_filename)
    plt.savefig(full_path, bbox_inches='tight')  # bbox_inches='tight' to include annotations outside the plot area
    plt.close()


def nan_to_none(value):
    """Recursively convert NaN values in nested data structures to None."""
    if isinstance(value, float) and np.isnan(value):
        return None
    elif isinstance(value, dict):
        return {k: nan_to_none(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [nan_to_none(v) for v in value]
    elif isinstance(value, pd.DataFrame):
        return value.where(pd.notnull(value), None)
    elif isinstance(value, pd.Series):
        return value.where(pd.notnull(value), None)
    return value

def replace_nan(obj):
    """Recursively replace NaN values with None for JSON serialization."""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: replace_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_nan(item) for item in obj]
    elif isinstance(obj, pd.DataFrame):
        return obj.where(pd.notnull(obj), None).to_dict(orient='records')
    elif isinstance(obj, pd.Series):
        return obj.where(pd.notnull(obj), None).to_dict()
    return obj

def perform_comprehensive_analysis(attendance_file, marks_file, low_attendance_threshold, high_attendance_threshold, low_marks_threshold, high_marks_threshold):
    def log_message(message):
        # Emit the log message to the front-end with event type "log"
        yield f"event: log\ndata: {message}\n\n"

    try:
        log_message("Reading attendance and marks files...")
        attendance_df = read_excel_file(attendance_file)
        marks_df = read_excel_file(marks_file)

        log_message("Mapping classes to subjects...")
        class_to_subject = marks_df[['Class', 'Subject']].drop_duplicates().set_index('Class')['Subject'].to_dict()

        # Define a function to find the closest match for a class name
        def find_closest_match(class_name, class_to_subject):
            closest_match = None
            closest_distance = float('inf')
            for pattern, subject in class_to_subject.items():
                distance = len(re.sub(pattern, '', class_name)) + len(re.sub(class_name, '', pattern))
                if distance < closest_distance:
                    closest_match = subject
                    closest_distance = distance
            return closest_match

        # Map the classes in the attendance data to their respective subjects
        attendance_df['Subject'] = attendance_df['Class'].apply(lambda x: class_to_subject.get(x, find_closest_match(x, class_to_subject)))
        print("attendance Data origional")

        print(attendance_df["Subject"].unique())
        session['attendance_df'] = attendance_df

        log_message("Identifying missing subjects...")
        print("Identifying missing subjects")
        # Identify missing subjects
        missing_subjects = attendance_df[attendance_df['Subject'].isna()]['Class'].unique()
        if len(missing_subjects) > 0:
            log_message(f"Warning: Missing subjects for the following classes: {', '.join(missing_subjects)}")
            print("The following are the missing subjects")
            print(missing_subjects)

        # Drop rows where the subject is not found in the mapping
        attendance_df = attendance_df.dropna(subset=['Subject'])
        print("attendance Data after dropna")

        print(attendance_df["Subject"].unique())

        log_message("Preprocessing data...")
        marks_df, attendance_df = preprocess_data(attendance_df, marks_df)
        print("attendance Data after preprocess")
        print(attendance_df["Subject"].unique())


        log_message("Identifying low Z-scores...")
        low_z_scores_df = identify_low_z_scores(marks_df, low_marks_threshold)
        log_message(f"Number of students with low z-scores: {len(low_z_scores_df['StudentID'].unique())}")

        log_message("Identifying students with subjects below threshold...")
        subjects_below_threshold = identify_students_with_subjects_below_threshold(marks_df, low_marks_threshold)
        log_message(f"Number of students with subjects below threshold: {len(subjects_below_threshold)}")

        log_message("Calculating average marks by class...")
        average_marks_by_class = calculate_average_marks_by_class(marks_df)
        
        log_message(f"Identifying high Z-scores above threshold {high_marks_threshold}...")
        high_z_scores_df = identify_high_z_scores(marks_df, high_marks_threshold)
        log_message(f"Number of students with high z-scores: {len(high_z_scores_df['StudentID'].unique())}")


        log_message("Analyzing correlation and preparing scatter plot...")
        correlation_analysis = analyze_correlation_and_prepare_scatter_plot_data(attendance_df, marks_df)

        log_message("Calculating year group attendance summary...")
        year_group_attendance_summary = calculate_year_group_attendance_summary(attendance_df)

        log_message("Identifying students below low attendance threshold...")
        students_below_threshold = identify_students_below_low_attendance_threshold(attendance_df, low_attendance_threshold)
        print(f"Students below threshold count: {students_below_threshold.shape[0]}")
        log_message(f"Number of students below low attendance threshold: {students_below_threshold.shape[0]}")

        log_message("Identifying students above high attendance threshold...")
        students_above_threshold = identify_students_above_high_attendance_threshold(attendance_df, high_attendance_threshold)
        print(f"Students above threshold count: {students_above_threshold.shape[0]}")
        log_message(f"Number of students above high attendance threshold: {students_above_threshold.shape[0]}")

        log_message("Attendance analysis completed.")


        log_message("Analysis completed successfully.")
        
        results = {
            "low_z_scores": low_z_scores_df.to_dict(orient='records'),
            "students_below_threshold_in_multiple_subjects": subjects_below_threshold.to_dict(orient='records'),
            "average_marks_by_class": average_marks_by_class.to_dict(),
            "correlation_analysis": correlation_analysis,
            "high_z_scores": high_z_scores_df.to_dict(orient='records'),
            "plot_filename": correlation_analysis['plot_filename'],
            "year_group_attendance_summary": year_group_attendance_summary,
            "students_below_low_threshold": students_below_threshold.to_dict(orient='records'),
            "students_above_high_threshold": students_above_threshold.to_dict(orient='records')
        }
        results = {key: replace_nan(value) for key, value in results.items()}
        
        print("students_below_low_threshold:")
        print(results["students_below_low_threshold"])
        print("\nstudents_above_high_threshold:")
        print(results["students_above_high_threshold"])

        # Send the final response data as JSON with event type "result"
        yield f"event: result\ndata: {json.dumps(results)}\n\n"


    except Exception as e:
        log_message(f"An error occurred during analysis: {str(e)}")
        raise