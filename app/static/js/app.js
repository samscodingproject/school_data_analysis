document.getElementById('uploadForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    // Show the loading overlay
    showLoadingOverlay();

    // Clear the analysis log
    document.getElementById('analysisLog').textContent = '';

    const formData = new FormData(this);

    // Add threshold values to the form data
    const lowAttendanceThreshold = document.getElementById('lowAttendanceThreshold').value;
    const highMarksThreshold = document.getElementById('highMarksThreshold').value;
    formData.append('lowAttendanceThreshold', lowAttendanceThreshold);
    formData.append('highMarksThreshold', highMarksThreshold);

    document.getElementById('analysisResults').innerHTML = ''; // Clear previous results
    document.getElementById('downloadReportBtn').style.display = 'none'; // Ensure button is hidden initially

    try {
        const response = await fetch('/upload', { method: 'POST', body: formData });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Server responded with an error');
        }

        // Create a reader and decoder for the response body
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        let result = null;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
        
            const events = decoder.decode(value).trim().split('\n\n');
        
            for (const event of events) {
                if (event.trim() === '') continue; // Skip empty events
        
                const [eventType, eventData] = event.split('\n');
                const data = eventData.slice(6); // Remove the "data: " prefix
        
                if (eventType === 'event: log') {
                    updateAnalysisLog(data);
                } else if (eventType === 'event: result') {
                    result = JSON.parse(data);
                }
            }
        }

        if (result.error) {
            throw new Error(result.error);
        }

        // Dynamically create and display all sections with the new data
        displayCorrelationAndScatterPlotResults(result.correlation_analysis || {}, result.plot_filename);
        createCollapsibleSection('Year Group Attendance Summary', result.year_group_attendance_summary || [], displayYearGroupAttendanceSummary);
        createCollapsibleSection('Students With Low Marks (Individual Subjects)', result.low_z_scores || [], displayLowZScoresResults);
        createCollapsibleSection('High Achievers (By Subject Z-score)', result.high_z_scores || [], displayHighZScoresResults);
        createCollapsibleSection('Average Marks by Class', result.average_marks_by_class || {}, displayAverageMarksByClass);
        createCollapsibleSection('Students Below Marks Threshold in Multiple Subjects', result.students_below_threshold_in_multiple_subjects || {}, displayStudentsBelowThreshold);
        createCollapsibleSection(
            'Students Below Attendance Threshold',
            result.students_below_attendance_threshold || [],
            displayStudentsBelowAttendanceThreshold
        );

        // Show the download button after successful data processing
        document.getElementById('downloadReportBtn').style.display = 'inline-block';

        // Hide the loading overlay
        hideLoadingOverlay();

        // Show the "Open Analysis Log" button
        document.getElementById('openAnalysisLogBtn').style.display = 'inline-block';
    } catch (error) {
        displayMessage(error.message, 'error');

        // Update the analysis log
        updateAnalysisLog('Error: ' + error.message);

        // Hide the loading overlay
        hideLoadingOverlay();
    }
});

function displayHighZScoresResults(highZScores, container) {
    // Check and remove existing results container if it exists
    const existingResultsContainer = container.querySelector('.high-z-score-results');
    if (existingResultsContainer) {
        existingResultsContainer.remove();
    }

    // Create a new container for the results
    const resultsContainer = document.createElement('div');
    resultsContainer.className = 'high-z-score-results';

    if (highZScores.length === 0) {
        resultsContainer.innerHTML = '<p>No students found with high Z-scores.</p>';
    } else {
        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>StudentID</th>
                    <th>Subject</th>
                    <th>Z-Score</th>
                </tr>
            </thead>
        `;

        const tbody = document.createElement('tbody');
        highZScores.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.StudentID}</td>
                <td>${item.Subject}</td>
                <td>${item.zScore.toFixed(2)}</td>
            `;
            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        resultsContainer.appendChild(table);
    }

    // Append the results container to the collapsible section
    container.appendChild(resultsContainer);
}


function displayFilteredResults(data, container, threshold) {
    // Check and remove existing results container if it exists
    const existingResultsContainer = container.querySelector('.attendance-threshold-results');
    if (existingResultsContainer) {
        existingResultsContainer.remove();
    }

    // Create a new container for the results
    const resultsContainer = document.createElement('div');
    resultsContainer.className = 'attendance-threshold-results';

    if (data.length === 0) {
        resultsContainer.innerHTML = '<p>No students found below the specified attendance threshold.</p>';
    } else {
        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>StudentID</th>
                    <th>Subjects Below Threshold</th>
                    <th>Number of Subjects Below Threshold</th>
                </tr>
            </thead>
        `;

        const tbody = document.createElement('tbody');
        data.forEach(student => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${student.StudentID}</td>
                <td>${student.Subjects.join(', ')}</td>
                <td>${student.SubjectCount}</td>
            `;
            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        resultsContainer.appendChild(table);
    }

    // Append the results container to the collapsible section
    container.appendChild(resultsContainer);

    // Clear the input field after displaying the results
    const inputField = document.getElementById('attendanceThresholdInput');
    inputField.value = '';
}

function clearResults(container) {
    const resultsContainer = container.querySelector('.attendance-threshold-results');
    if (resultsContainer) {
        resultsContainer.innerHTML = '';
    }
}

function displayStudentsBelowAttendanceThreshold(data, container) {
    // Check and remove existing results container if it exists
    const existingResultsContainer = container.querySelector('.attendance-threshold-results');
    if (existingResultsContainer) {
        existingResultsContainer.remove();
    }

    // Create a new container for the results
    const resultsContainer = document.createElement('div');
    resultsContainer.className = 'attendance-threshold-results';

    if (data.length === 0) {
        resultsContainer.innerHTML = '<p>No students found below the specified attendance threshold.</p>';
    } else {
        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>StudentID</th>
                    <th>Subjects Below Threshold</th>
                    <th>Number of Subjects Below Threshold</th>
                </tr>
            </thead>
        `;

        const tbody = document.createElement('tbody');
        data.forEach(student => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${student.StudentID}</td>
                <td>${student.Subjects.join(', ')}</td>
                <td>${student.SubjectCount}</td>
            `;
            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        resultsContainer.appendChild(table);
    }

    // Append the results container to the collapsible section
    container.appendChild(resultsContainer);
}

document.getElementById('downloadReportBtn').addEventListener('click', function() {
    window.location.href = '/download_report'; // Adjust the route if necessary
});

function clearResults() {
    document.getElementById('analysisResults').innerHTML = '';
}


function renderLineOfBestFit({ slope, intercept, r_value, p_value, std_err } = {}) {
    const toFixedIfNumber = (value, digits = 2) => typeof value === 'number' ? value.toFixed(digits) : 'N/A';

    return `
        <h4>Regression Results:</h4>
        <ul>
            <li>Slope: ${toFixedIfNumber(slope)}</li>
            <li>Intercept: ${toFixedIfNumber(intercept)}</li>
            <li>R-value: ${toFixedIfNumber(r_value)}</li>
            <li>P-value: ${toFixedIfNumber(p_value, 4)}</li>
            <li>Standard Error: ${toFixedIfNumber(std_err)}</li>
        </ul>
    `;
}

function displayCorrelationAndScatterPlotResults(correlationAnalysis, plotFilename) {
    const analysisResults = document.getElementById('analysisResults');
    
    // Correlation Results
    const correlationDiv = document.createElement('div');
    correlationDiv.className = 'result-section';
    correlationDiv.innerHTML = `<h3>Correlation Results</h3>${displayCorrelationResults(correlationAnalysis)}`;
    analysisResults.appendChild(correlationDiv);
    
    // Scatter Plot
    if (plotFilename) {
        const scatterPlotDiv = document.createElement('div');
        scatterPlotDiv.className = 'result-section';
        scatterPlotDiv.innerHTML = `<h3>Scatter Plot</h3><img src="/${plotFilename}" alt="Scatter Plot" class="scatter-plot-image">`;
        analysisResults.appendChild(scatterPlotDiv);
    }
}


function displayCorrelationResults({ correlation, line_of_best_fit, explainer_text }) {
    const correlationValue = isFinite(correlation) ? correlation.toFixed(2) : 'N/A';
    let resultsHTML = `
        <p>Correlation: ${correlationValue}</p>
        <p>${explainer_text.correlation}</p>
        
        <h3>Regression Results:</h3>
        <ul>
            <li><strong>Slope:</strong> ${toFixedIfNumber(line_of_best_fit.slope)}</li>
            <li><strong>Intercept:</strong> ${toFixedIfNumber(line_of_best_fit.intercept)}</li>
            <li><strong>R-value:</strong> ${toFixedIfNumber(line_of_best_fit.r_value)}</li>
            <li><strong>P-value:</strong> ${toFixedIfNumber(line_of_best_fit.p_value, 4)}</li>
            <li><strong>Standard Error:</strong> ${toFixedIfNumber(line_of_best_fit.std_err)}</li>
        </ul>
        <p>${explainer_text.regression}</p>
    `;
    return resultsHTML;
}

function displayLowZScoresResults(lowZScores, container) {
    container.innerHTML = ''; // Clear the container
    if (lowZScores.length === 0) {
        container.innerHTML = '<p>No low Z-scores found.</p>';
        return;
    }
    
    const table = document.createElement('table');
    table.innerHTML = `
        <thead>
            <tr>
                <th>StudentID</th>
                <th>Subject</th>
                <th>Z-Score</th>
            </tr>
        </thead>
    `;
    
    const tbody = document.createElement('tbody');
    lowZScores.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.StudentID}</td>
            <td>${item.Subject}</td>
            <td>${toFixedIfNumber(item.zScore)}</td>
        `;
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
}

function displayAverageMarksByClass(averageMarks, container) {
    container.innerHTML = ''; // Clear the container

    if (Object.keys(averageMarks).length === 0) {
        container.innerHTML = '<p>No average marks data available.</p>';
        return;
    }

    // Create the multi-select dropdown
    const multiSelect = document.createElement('select');
    multiSelect.setAttribute('multiple', 'multiple');
    multiSelect.style.width = '100%'; // Ensure the Select2 dropdown fills the container
    
    Object.entries(averageMarks).forEach(([className, mark]) => {
        const option = document.createElement('option');
        option.value = className;
        option.textContent = `${className}: ${toFixedIfNumber(mark)}`;
        multiSelect.appendChild(option);
    });

    container.appendChild(multiSelect);

    // Initialize Select2 on the multi-select dropdown
    $(multiSelect).select2({
        placeholder: "Select classes",
        allowClear: true,
        closeOnSelect: false // Keep the dropdown open after selecting an option
    });

    // Create a container for displaying selected classes' average marks
    const selectedClassesContainer = document.createElement('div');
    selectedClassesContainer.setAttribute('id', 'selectedClassesContainer');
    container.appendChild(selectedClassesContainer);

    // Listen for selection changes and update the display
    $(multiSelect).on('change', function() {
        const selectedValues = $(this).val(); // Get selected options
        displaySelectedClasses(selectedValues, averageMarks, selectedClassesContainer);
    });
}


function displaySelectedClasses(selectedClasses, averageMarks, selectedClassesContainer) {
    // Clear previous selections
    selectedClassesContainer.innerHTML = '';

    // Check if there are any selected classes
    if (selectedClasses && selectedClasses.length > 0) {
        // Iterate over selected classes and create elements to display their average marks
        selectedClasses.forEach(className => {
            const mark = averageMarks[className];
            const classInfo = document.createElement('p');
            classInfo.textContent = `Average mark for ${className} is ${toFixedIfNumber(mark)}.`;
            selectedClassesContainer.appendChild(classInfo);
        });
        // Make the container visible
        selectedClassesContainer.classList.add('active');
    } else {
        // Hide the container if no classes are selected
        selectedClassesContainer.classList.remove('active');
    }
}

function displayYearGroupAttendanceSummary(yearGroupAttendanceSummary, container) {
    container.innerHTML = ''; // Clear the container
    if (yearGroupAttendanceSummary.length === 0) {
        container.innerHTML = '<p>No year group attendance summary data available.</p>';
        return;
    }
    
    const table = document.createElement('table');
    table.innerHTML = `
        <thead>
            <tr>
                <th>School Year</th>
                <th>Mean</th>
                <th>Median</th>
                <th>Min</th>
                <th>Max</th>
                <th>Std</th>
                <th>Percentage Above 90%</th>
            </tr>
        </thead>
    `;
    
    const tbody = document.createElement('tbody');
    yearGroupAttendanceSummary.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item['School Year']}</td>
            <td>${toFixedIfNumber(item.mean)}</td>
            <td>${toFixedIfNumber(item.median)}</td>
            <td>${toFixedIfNumber(item.min)}</td>
            <td>${toFixedIfNumber(item.max)}</td>
            <td>${toFixedIfNumber(item.std)}</td>
            <td>${toFixedIfNumber(item.PercentageAbove90)}%</td>
        `;
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);

    const histogramDiv = document.createElement('div');
    histogramDiv.innerHTML = `
        <h4>Distribution of Attendance Percentages</h4>
        <img src="/static/images/attendance_distribution_histogram.png" alt="Attendance Distribution Histogram">
    `;
    container.appendChild(histogramDiv);
}

function toFixedIfNumber(value, digits = 2) {
    return typeof value === 'number' ? value.toFixed(digits) : 'N/A';
}

function displayStudentsBelowThreshold(studentsBelowThreshold, container) {
    container.innerHTML = ''; // Clear the container
    if (studentsBelowThreshold.length === 0) {
        container.innerHTML = '<p>No students below threshold in multiple subjects.</p>';
        return;
    }
    
    const table = document.createElement('table');
    table.innerHTML = `
        <thead>
            <tr>
                <th>StudentID</th>
                <th>Subjects Below Threshold</th>
            </tr>
        </thead>
    `;
    
    const tbody = document.createElement('tbody');
    studentsBelowThreshold.forEach(student => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${student.StudentID}</td>
            <td>${student.Subjects.join(', ')}</td>
        `;
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
}

function displayMessage(message, className) {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = `<div class="${className}">${message}</div>`;
}

function toFixedIfNumber(value, digits = 2) {
    return typeof value === 'number' ? value.toFixed(digits) : 'N/A';
}


function createCollapsibleSection(title, data, displayFunction) {
    const section = document.createElement('div');
    section.className = 'result-section';

    const button = document.createElement('button');
    button.textContent = title;
    button.className = 'collapsible';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';

    // Append the newly created elements to the analysisResults container
    section.appendChild(button);
    section.appendChild(contentDiv);
    document.getElementById('analysisResults').appendChild(section);

    // Add event listener to the collapsible button
    button.addEventListener('click', function() {
        this.classList.toggle('active');
        if (this.classList.contains('active')) {
            contentDiv.style.display = 'block';
            // Execute the display function when the collapsible section is expanded
            displayFunction(data, contentDiv);
        } else {
            contentDiv.style.display = 'none';
            // Clear the content when the collapsible section is collapsed
            contentDiv.innerHTML = '';
        }
    });
}

function initializeCollapsibles() {
    const collapsibles = document.querySelectorAll('.collapsible');
    collapsibles.forEach(collapsible => {
        collapsible.addEventListener('click', function() {
            this.classList.toggle('active');
            const content = this.nextElementSibling;
            if (content.style.display === "block") {
                content.style.display = "none";
            } else {
                content.style.display = "block";
            }
        });
    });
}

// Function to show the loading overlay
function showLoadingOverlay() {
    document.getElementById('loadingOverlay').style.display = 'block';
}

// Function to hide the loading overlay
function hideLoadingOverlay() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

// Function to update the analysis log
function updateAnalysisLog(message) {
    const analysisLog = document.getElementById('analysisLog');
    analysisLog.textContent += message + '\n';
}

// Function to open the analysis log modal
function openAnalysisLogModal() {
    document.getElementById('analysisLogModal').style.display = 'block';
}

// Function to close the analysis log modal
function closeAnalysisLogModal() {
    document.getElementById('analysisLogModal').style.display = 'none';
}

// Add event listener to the close button of the analysis log modal
document.getElementsByClassName('close')[0].addEventListener('click', closeAnalysisLogModal);

// Add event listener to the "Open Analysis Log" button
document.getElementById('openAnalysisLogBtn').addEventListener('click', openAnalysisLogModal);