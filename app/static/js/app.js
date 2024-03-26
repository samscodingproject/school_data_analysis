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


function displayCorrelationResults({ correlation, line_of_best_fit }) {
    const correlationValue = isFinite(correlation) ? correlation.toFixed(2) : 'N/A';
    return `
        <p>Correlation: ${correlationValue}</p>
        ${renderLineOfBestFit(line_of_best_fit)}
    `;
}

function displayLowZScoresResults(lowZScores, container) {
    container.innerHTML = '';
    if (lowZScores.length === 0) {
        container.innerHTML = '<p>No low Z-scores found.</p>';
    } else {
        const list = document.createElement('ul');
        lowZScores.forEach(item => {
            const listItem = document.createElement('li');
            listItem.textContent = `StudentID: ${item.StudentID}, Subject: ${item.Subject}, Z-Score: ${item.zScore.toFixed(2)}`;
            list.appendChild(listItem);
        });
        container.appendChild(list);
    }
}

function displayAverageMarksByClass(averageMarks, container) {
    if (Object.keys(averageMarks).length === 0) {
        container.innerHTML = '<p>No average marks data available.</p>';
    } else {
        const list = document.createElement('ul');
        Object.entries(averageMarks).forEach(([className, mark]) => {
            const listItem = document.createElement('li');
            listItem.textContent = `${className}: ${toFixedIfNumber(mark)}`;
            list.appendChild(listItem);
        });
        container.appendChild(list);
    }
}

function displayStudentsBelowThreshold(studentsBelowThreshold, container) {
    if (studentsBelowThreshold.length === 0) {
        container.innerHTML = '<p>No students below threshold in multiple subjects.</p>';
    } else {
        const list = document.createElement('ul');
        studentsBelowThreshold.forEach(student => {
            const listItem = document.createElement('li');
            listItem.textContent = `StudentID: ${student.StudentID}, Subjects: ${student.Subjects.join(', ')}`;
            list.appendChild(listItem);
        });
        container.appendChild(list);
    }
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