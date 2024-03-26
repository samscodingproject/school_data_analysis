document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    document.getElementById('analysisResults').innerHTML = ''; // Clear previous results
    document.getElementById('downloadReportBtn').style.display = 'none'; // Ensure button is hidden initially
    
    try {
        const response = await fetch('/upload', { method: 'POST', body: formData });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Server responded with an error');
        }
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Dynamically create and display all sections with the new data
        displayCorrelationAndScatterPlotResults(data.correlation_analysis || {}, data.plot_filename);
        createCollapsibleSection('Low Z-Scores', data.low_z_scores || [], displayLowZScoresResults);
        createCollapsibleSection('Average Marks by Class', data.average_marks_by_class || {}, displayAverageMarksByClass);
        createCollapsibleSection('Students Below Threshold in Multiple Subjects', data.students_below_threshold_in_multiple_subjects || {}, displayStudentsBelowThreshold);
        
        // Initialize the collapsible sections to make them functional
        initializeCollapsibles();

        // Show the download button after successful data processing
        document.getElementById('downloadReportBtn').style.display = 'inline-block';
    } catch (error) {
        displayMessage(error.message, 'error');
    }
});

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
        <h3>Correlation Results:</h3>
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

    // Use the display function to populate the contentDiv with data
    displayFunction(data, contentDiv);
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