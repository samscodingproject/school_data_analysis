import pandas as pd
from scipy.stats import zscore, linregress
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from celery import Celery
import os
import re

app = Celery('tasks', broker='redis://localhost:6479')

matplotlib.use('Agg')  # Use the non-GUI Agg backend


def read_excel_file(file_path):
    try:
        return pd.read_excel(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

def preprocess_data(attendance_df, marks_df):
    try:
        # Example validation: Check required columns exist
        required_columns = ['T1Weight', 'T2Weight', 'T3Weight']
        for col in required_columns:
            if col not in marks_df.columns:
                raise ValueError(f"Missing required column in marks data: {col}")
        # Calculate Final Marks
        marks_df['CalculatedFinalMark'] = marks_df['T1Weight'] + marks_df['T2Weight'] + marks_df['T3Weight']
    
        # Filter Attendance Data
        filtered_attendance_df = attendance_df[(attendance_df['Class Time'] >= 1000) & (~attendance_df['Class'].str.contains("MEN"))]
        overall_attendance = filtered_attendance_df[filtered_attendance_df['Class'] == 'Overall'].copy()
        overall_attendance.loc[:, 'OverallAttendancePercentage'] = 100 - (overall_attendance['Absence Time'] / overall_attendance['Class Time'] * 100)

        
        return marks_df, overall_attendance

    except Exception as e:
        raise ValueError(f"Data preprocessing failed: {e}")
    

def identify_low_z_scores(marks_df):
    marks_df['zScore'] = marks_df.groupby('Subject')['CalculatedFinalMark'].transform(lambda x: zscore(x, ddof=1))
    low_z_scores_df = marks_df[marks_df['zScore'] < -1.2]
    return low_z_scores_df

def identify_students_with_subjects_below_threshold(marks_df):
    # Filter rows with low Z-scores
    low_z_scores = marks_df[marks_df['zScore'] < -1.2]
    
    # Group by StudentID and aggregate the subjects into a list
    subjects_below_threshold = low_z_scores.groupby('StudentID')['Subject'].apply(list).reset_index(name='Subjects')
    
    # Count the number of subjects below the threshold for each student
    subjects_below_threshold['SubjectCount'] = subjects_below_threshold['Subjects'].apply(len)
    
    # Sort the results by the number of subjects in descending order
    subjects_below_threshold = subjects_below_threshold.sort_values(by='SubjectCount', ascending=False)
    
    return subjects_below_threshold

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

def perform_comprehensive_analysis(attendance_file, marks_file):
    attendance_df = read_excel_file(attendance_file)
    marks_df = read_excel_file(marks_file)
    
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

    # Identify missing subjects
    missing_subjects = attendance_df[attendance_df['Subject'].isna()]['Class'].unique()
    if len(missing_subjects) > 0:
        print("Warning: Missing subjects for the following classes:", ", ".join(missing_subjects))

    # Drop rows where the subject is not found in the mapping
    attendance_df = attendance_df.dropna(subset=['Subject'])

    marks_df, attendance_df = preprocess_data(attendance_df, marks_df)
    
    low_z_scores_df = identify_low_z_scores(marks_df)

    print("Low Z-Scores DataFrame:")  # Debugging statement
    print(low_z_scores_df)  # Debugging statement
    print("Number of students with low z-scores:", len(low_z_scores_df['StudentID'].unique()))  # Debugging statement
    
    subjects_below_threshold = identify_students_with_subjects_below_threshold(marks_df)

    print("Subjects Below Threshold DataFrame:")  # Debugging statement
    print(subjects_below_threshold)  # Debugging statement
    print("Number of students with subjects below threshold:", len(subjects_below_threshold))  # Debugging statement
    
    average_marks_by_class = calculate_average_marks_by_class(marks_df)

    print("Average Marks by Class:")  # Debugging statement
    print(average_marks_by_class)  # Debugging statement
    
    correlation_analysis = analyze_correlation_and_prepare_scatter_plot_data(attendance_df, marks_df)
   
    print("Correlation Analysis:")  # Debugging statement
    print(correlation_analysis)  # Debugging statement

    results = {
        "low_z_scores": low_z_scores_df.to_dict(orient='records'),
        "students_below_threshold_in_multiple_subjects": subjects_below_threshold.to_dict(orient='records'),
        "average_marks_by_class": average_marks_by_class.to_dict(),
        "correlation_analysis": correlation_analysis,
        "plot_filename": correlation_analysis['plot_filename']
    }
    
    results = {key: replace_nan(value) for key, value in results.items()}

    return results