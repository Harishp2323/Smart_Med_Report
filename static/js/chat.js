// Global state
let currentReportId = null;
let isAnalyzing = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Chat interface loaded');
    
    // --- NEW: Initialize Dark Mode and Attach Listener ---
    initializeDarkMode(); 
    // ---------------------------------------------------
    
    loadHistory();
    autoResizeTextarea();
});


// =========================================================================
// NEW: DARK/LIGHT MODE TOGGLE FUNCTIONS
// =========================================================================

/**
 * Reads user preference from localStorage or OS and sets up the mode toggle.
 */
function initializeDarkMode() {
    const isDark = localStorage.getItem('darkMode') === 'true';
    if (isDark) {
        document.body.classList.add('dark-mode');
    }
    
    const toggleBtn = document.getElementById('modeToggleBtn');
    if (toggleBtn) {
        // Update button icon/text based on current mode
        updateModeToggleUI(isDark);

        // Attach the toggle function to the button
        toggleBtn.addEventListener('click', toggleDarkMode);
    } else {
        console.warn('Mode toggle button with ID "modeToggleBtn" not found.');
    }
}

/**
 * Toggles the 'dark-mode' class on the body and saves preference to localStorage.
 */
function toggleDarkMode() {
    const isCurrentlyDark = document.body.classList.toggle('dark-mode');
    
    // Save the new state to local storage
    localStorage.setItem('darkMode', isCurrentlyDark);
    
    // Update the button icon/text
    updateModeToggleUI(isCurrentlyDark);
}

/**
 * Updates the appearance of the mode toggle button.
 * @param {boolean} isDark - The current state of dark mode.
 */
function updateModeToggleUI(isDark) {
    const toggleBtn = document.getElementById('modeToggleBtn');
    if (toggleBtn) {
        // Toggles between Sun (Light) and Moon (Dark) icons
        toggleBtn.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
        toggleBtn.setAttribute('title', isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode');
    }
}

// =========================================================================
// EXISTING FUNCTIONS (from your original code)
// =========================================================================

// Show text input area
function showTextInput() {
    const textInputArea = document.getElementById('textInputArea');
    textInputArea.style.display = 'block';
}

// Handle file upload
async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    const validTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
    if (!validTypes.includes(file.type)) {
        alert('Please upload a PDF or image file (JPG, PNG)');
        return;
    }

    // Show loading
    showLoading();

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            hideLoading();
            showAnalysis();
        } else {
            hideLoading();
            alert('Error: ' + (data.error || 'Upload failed'));
        }
    } catch (error) {
        hideLoading();
        alert('Error uploading file: ' + error.message);
    }
}

// Submit manual text
async function submitText() {
    const text = document.getElementById('manualText').value.trim();
    
    if (!text) {
        alert('Please paste some text first');
        return;
    }

    showLoading();

    try {
        const response = await fetch('/upload_text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });

        const data = await response.json();

        if (data.success) {
            hideLoading();
            showAnalysis();
        } else {
            hideLoading();
            alert('Error: ' + (data.error || 'Failed to process text'));
        }
    } catch (error) {
        hideLoading();
        alert('Error: ' + error.message);
    }
}

// Show analysis section
function showAnalysis() {
    document.getElementById('uploadSection').style.display = 'none';
    document.getElementById('analysisSection').style.display = 'flex';

    // Simulate analysis steps
    const steps = ['step1', 'step2', 'step3'];
    const statuses = [
        'Extracting text from report...',
        'Detecting parameters...',
        'Analyzing results...'
    ];

    let currentStep = 0;
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('analysisStatus');

    const interval = setInterval(() => {
        if (currentStep < steps.length) {
            document.getElementById(steps[currentStep]).classList.add('active');
            statusText.textContent = statuses[currentStep];
            progressBar.style.width = ((currentStep + 1) / steps.length * 100) + '%';
            currentStep++;
        } else {
            clearInterval(interval);
            // Proceed to analyze
            analyzeReport();
        }
    }, 1500);
}

// Analyze report
async function analyzeReport() {
    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });

        const data = await response.json();

        if (data.success) {
            currentReportId = data.report_id;
            
            // Update current report display
            document.getElementById('reportAge').textContent = data.age || 'N/A';
            document.getElementById('reportSex').textContent = data.sex || 'N/A';
            
            // Show current report section
            document.getElementById('currentReport').style.display = 'block';
            
            // Update summary stats
            updateSummaryStats(data.results);
            
            // Show chat section
            showChat();
            
            // Reload history
            loadHistory();
        } else {
            alert('Error analyzing report: ' + (data.error || 'Unknown error'));
            newChat();
        }
    } catch (error) {
        alert('Error: ' + error.message);
        newChat();
    }
}

// Update summary stats
function updateSummaryStats(results) {
    const summaryStats = document.getElementById('summaryStats');
    
    let normalCount = 0;
    let abnormalCount = 0;
    
    results.forEach(result => {
        if (result.status === 'Normal') {
            normalCount++;
        } else if (result.status === 'Low' || result.status === 'High') {
            abnormalCount++;
        }
    });
    
    summaryStats.innerHTML = `
        <span class="stat-badge normal">✓ ${normalCount} Normal</span>
        <span class="stat-badge abnormal">⚠ ${abnormalCount} Abnormal</span>
    `;
}

// Show chat interface
function showChat() {
    document.getElementById('analysisSection').style.display = 'none';
    document.getElementById('chatSection').style.display = 'flex';
    
    // Focus on input
    document.getElementById('messageInput').focus();
}

// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Clear input
    input.value = '';
    input.style.height = 'auto';
    
    // Disable send button
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    
    // Show typing indicator
    showTypingIndicator();
    
    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question: message })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator();
        
        if (data.success) {
            addMessage(data.response, 'assistant');
        } else {
            addMessage('Sorry, I encountered an error: ' + (data.error || 'Unknown error'), 'assistant');
        }
    } catch (error) {
        removeTypingIndicator();
        addMessage('Sorry, I encountered an error: ' + error.message, 'assistant');
    } finally {
        sendBtn.disabled = false;
    }
}

// Ask predefined question
function askQuestion(question) {
    document.getElementById('messageInput').value = question;
    sendMessage();
}

// Add message to chat
function addMessage(text, role) {
    const messagesContainer = document.getElementById('chatMessages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';
    avatarDiv.innerHTML = role === 'assistant' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-user"></i>';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const textP = document.createElement('p');
    textP.textContent = text;
    
    contentDiv.appendChild(textP);
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant-message';
    typingDiv.id = 'typingIndicator';
    
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Remove typing indicator
function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// Handle Enter key
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Auto-resize textarea
function autoResizeTextarea() {
    const textarea = document.getElementById('messageInput');
    if (!textarea) return;
    
    textarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });
}

// Show results modal
async function showResults() {
    try {
        const response = await fetch('/summary');
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
            return;
        }
        
        const modal = document.getElementById('resultsModal');
        const content = document.getElementById('resultsContent');
        
        let html = `
            <div style="margin-bottom: 20px;">
                <h3>Patient Information</h3>
                <p><strong>Age:</strong> ${data.age || 'N/A'} | <strong>Sex:</strong> ${data.sex || 'N/A'}</p>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h3>Summary</h3>
                <div style="display: flex; gap: 20px;">
                    <span class="stat-badge normal">✓ ${data.normal_count} Normal</span>
                    <span class="stat-badge low">⬇ ${data.low_count} Low</span>
                    <span class="stat-badge high">⬆ ${data.high_count} High</span>
                </div>
            </div>
        `;
        
        if (data.abnormal_params.length > 0) {
            html += `
                <div>
                    <h3>Abnormal Parameters</h3>
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th>Parameter</th>
                                <th>Value</th>
                                <th>Unit</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            data.abnormal_params.forEach(param => {
                html += `
                    <tr>
                        <td>${param.parameter}</td>
                        <td>${param.value.toFixed(2)}</td>
                        <td>${param.unit}</td>
                        <td><span class="status-badge ${param.status.toLowerCase()}">${param.status}</span></td>
                    </tr>
                `;
            });
            
            html += `
                        </tbody>
                    </table>
                </div>
            `;
        }
        
        content.innerHTML = html;
        modal.style.display = 'flex';
    } catch (error) {
        alert('Error loading results: ' + error.message);
    }
}

// Close modal
function closeModal() {
    document.getElementById('resultsModal').style.display = 'none';
}

// Show trends
async function showTrends() {
    try {
        const response = await fetch('/trends');
        const data = await response.json();
        
        const modal = document.getElementById('trendsModal');
        const content = document.getElementById('trendsContent');
        
        if (data.message) {
            content.innerHTML = `
                <div class="no-trends">
                    <i class="fas fa-chart-line"></i>
                    <p>${data.message}</p>
                </div>
            `;
        } else if (data.trends) {
            let html = '';
            
            for (const [param, values] of Object.entries(data.trends)) {
                if (values.length > 0) {
                    html += `
                        <div class="trend-chart">
                            <h3>${param}</h3>
                            <div style="margin-top: 16px;">
                    `;
                    
                    values.forEach((item, index) => {
                        const date = new Date(item.date).toLocaleDateString();
                        html += `
                            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color);">
                                <span>${date}</span>
                                <span><strong>${item.value.toFixed(2)}</strong></span>
                                <span class="status-badge ${item.status.toLowerCase()}">${item.status}</span>
                            </div>
                        `;
                    });
                    
                    html += `
                            </div>
                        </div>
                    `;
                }
            }
            
            content.innerHTML = html || '<div class="no-trends"><p>No trend data available</p></div>';
        }
        
        modal.style.display = 'flex';
    } catch (error) {
        alert('Error loading trends: ' + error.message);
    }
}

// Close trends modal
function closeTrendsModal() {
    document.getElementById('trendsModal').style.display = 'none';
}

// Load history
async function loadHistory() {
    try {
        const response = await fetch('/history');
        const data = await response.json();
        
        const historyList = document.getElementById('historyList');
        
        if (data.reports && data.reports.length > 0) {
            historyList.innerHTML = '';
            
            data.reports.forEach(report => {
                const date = new Date(report.date).toLocaleDateString();
                const item = document.createElement('div');
                item.className = 'history-item';
                item.innerHTML = `
                    <div class="history-date">${date}</div>
                    <div class="history-info">
                        Age: ${report.age || 'N/A'} | Sex: ${report.sex || 'N/A'}
                        <br><small>${report.abnormal_count} abnormal parameter(s)</small>
                    </div>
                `;
                historyList.appendChild(item);
            });
        } else {
            historyList.innerHTML = '<p class="empty-state">No previous reports</p>';
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// New chat / Clear session
async function newChat() {
    if (confirm('Start a new analysis? Current session will be cleared.')) {
        try {
            await fetch('/clear_session', { method: 'POST' });
            location.reload();
        } catch (error) {
            console.error('Error clearing session:', error);
            location.reload();
        }
    }
}

// Download report
function downloadReport() {
    alert('Report download feature coming soon!');
}

// Show/hide loading overlay
function showLoading() {
    document.getElementById('loadingOverlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

// Close modals on outside click
window.onclick = function(event) {
    const resultsModal = document.getElementById('resultsModal');
    const trendsModal = document.getElementById('trendsModal');
    
    if (event.target === resultsModal) {
        closeModal();
    }
    if (event.target === trendsModal) {
        closeTrendsModal();
    }
}

// Add these functions to chat.js

// Section navigation
function showSection(sectionName) {
    // Hide all sections
    const sections = [
        'uploadSection', 'analysisSection', 'chatSection', 
        'analyzerSection', 'visualizeSection', 'correlationsSection'
    ];
    
    sections.forEach(section => {
        const element = document.getElementById(section);
        if (element) {
            element.style.display = 'none';
        }
    });
    
    // Show selected section
    let targetSection;
    switch(sectionName) {
        case 'analyzer':
            targetSection = 'analyzerSection';
            break;
        case 'visualize':
            targetSection = 'visualizeSection';
            break;
        case 'correlations':
            targetSection = 'correlationsSection';
            break;
        default:
            targetSection = 'chatSection';
    }
    
    const targetElement = document.getElementById(targetSection);
    if (targetElement) {
        targetElement.style.display = 'flex';
        console.log(`🎯 Displaying section: ${targetSection}`);
        
        // Load data for specific sections
        if (sectionName === 'analyzer') {
            console.log("🚀 Loading analyzer data...");
            loadAnalyzerData();
        } else if (sectionName === 'visualize') {
            loadVisualizationData();
        } else if (sectionName === 'correlations') {
            loadCorrelations();
        }
    } else {
        console.error(`❌ Section not found: ${targetSection}`);
    }
}

// Load analyzer data
async function loadAnalyzerData() {
    try {
        console.log("🔄 Loading analyzer data...");
        const response = await fetch('/get_analyzer_data');
        const data = await response.json();
        
        console.log("📦 Received analyzer data:", data);
        
        if (data.success) {
            console.log("✅ Parameters received:", data.parameters);
            console.log("✅ Absolute counts received:", data.absolute_counts);
            console.log(`📊 Total parameters: ${data.parameters.length}`);
            console.log(`📊 Total absolute counts: ${data.absolute_counts.length}`);
            
            populateAnalyzerTables(data.parameters, data.absolute_counts);
        } else {
            console.error("❌ Error loading analyzer data:", data.error);
            showMessage('Error loading analyzer data: ' + data.error, 'error');
            
            // Show empty state in table
            const paramsTableBody = document.getElementById('parametersTableBody');
            paramsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: var(--error-color);">' + data.error + '</td></tr>';
        }
    } catch (error) {
        console.error("❌ Error in loadAnalyzerData:", error);
        showMessage('Error: ' + error.message, 'error');
    }
}

// Populate analyzer tables
function populateAnalyzerTables(parameters, absoluteCounts) {
    const paramsTableBody = document.getElementById('parametersTableBody');
    const absoluteTableBody = document.getElementById('absoluteTableBody');
    
    console.log("🔄 Populating tables with parameters:", parameters);
    console.log("🔄 Populating tables with absolute counts:", absoluteCounts);
    
    // Clear existing data
    paramsTableBody.innerHTML = '';
    absoluteTableBody.innerHTML = '';
    
    // Populate parameters table
    if (parameters && parameters.length > 0) {
        console.log(`📊 Found ${parameters.length} parameters to display`);
        
        parameters.forEach(param => {
            const row = document.createElement('tr');
            
            // Determine status badge class
            let statusClass = 'normal';
            if (param.Status === 'Low') statusClass = 'low';
            if (param.Status === 'High') statusClass = 'high';
            if (!param.Status) statusClass = 'normal';
            
            // Escape parameter name for JavaScript
            const safeParamName = param.Parameter.replace(/'/g, "\\'");
            
            row.innerHTML = `
                <td>${param.Parameter}</td>
                <td>
                    <input type="number" 
                           value="${param.Value}" 
                           step="0.01" 
                           style="width: 80px; padding: 4px; border: 1px solid var(--border-color); border-radius: 4px;"
                           onchange="updateParameter('${safeParamName}', this.value)">
                </td>
                <td>${param.Unit || 'N/A'}</td>
                <td>${param['Reference Low'] || 'N/A'}</td>
                <td>${param['Reference High'] || 'N/A'}</td>
                <td>
                    <span class="status-badge ${statusClass}">
                        ${param.Status || 'Normal'}
                    </span>
                </td>
                <td>
                    <button class="btn-save" onclick="saveParameterEdit('${safeParamName}')" style="padding: 6px 12px;">
                        <i class="fas fa-save"></i> Save
                    </button>
                </td>
            `;
            paramsTableBody.appendChild(row);
        });
        
        console.log("✅ Parameters table populated successfully");
    } else {
        console.warn("⚠️ No parameters data available");
        paramsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: var(--text-secondary);">No parameter data available</td></tr>';
    }
    
    // Populate absolute counts table
    if (absoluteCounts && absoluteCounts.length > 0) {
        console.log(`📊 Found ${absoluteCounts.length} absolute counts to display`);
        
        absoluteCounts.forEach(param => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${param.Parameter}</td>
                <td>${param.Value}</td>
                <td>${param.Unit}</td>
            `;
            absoluteTableBody.appendChild(row);
        });
        
        console.log("✅ Absolute counts table populated successfully");
    } else {
        console.warn("⚠️ No absolute counts data available");
        absoluteTableBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px; color: var(--text-secondary);">No absolute counts data available</td></tr>';
    }
}

// Switch analyzer tabs
function switchAnalyzerTab(tabName) {
    const paramsTable = document.getElementById('parametersTable');
    const absoluteTable = document.getElementById('absoluteTable');
    const paramTab = document.querySelector('.tab-btn[onclick="switchAnalyzerTab(\'parameters\')"]');
    const absoluteTab = document.querySelector('.tab-btn[onclick="switchAnalyzerTab(\'absolute\')"]');
    
    if (tabName === 'parameters') {
        paramsTable.style.display = 'table';
        absoluteTable.style.display = 'none';
        paramTab.classList.add('active');
        absoluteTab.classList.remove('active');
    } else {
        paramsTable.style.display = 'none';
        absoluteTable.style.display = 'table';
        paramTab.classList.remove('active');
        absoluteTab.classList.add('active');
    }
}

// Update parameter value
function updateParameter(parameter, value) {
    // Store the updated value temporarily
    if (!window.updatedParameters) {
        window.updatedParameters = {};
    }
    window.updatedParameters[parameter] = parseFloat(value);
}

// Save parameter edit
async function saveParameterEdit(parameter) {
    if (!window.updatedParameters || !window.updatedParameters[parameter]) {
        alert('No changes detected for ' + parameter);
        return;
    }
    
    try {
        const response = await fetch('/update_parameter', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                parameter: parameter,
                value: window.updatedParameters[parameter]
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Parameter updated successfully!');
            delete window.updatedParameters[parameter];
            loadAnalyzerData(); // Refresh data
        } else {
            alert('Error updating parameter: ' + data.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Load visualization data
async function loadVisualizationData() {
    try {
        const response = await fetch('/get_visualization_data');
        const data = await response.json();
        
        if (data.success) {
            createCharts(data.chart_data);
        } else {
            alert('Error loading visualization data: ' + data.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Create charts
function createCharts(chartData) {
    // Status distribution chart
    const statusCtx = document.getElementById('statusChart').getContext('2d');
    const statusCounts = {
        'Normal': 0,
        'Low': 0,
        'High': 0
    };
    
    chartData.statuses.forEach(status => {
        if (statusCounts.hasOwnProperty(status)) {
            statusCounts[status]++;
        }
    });
    
    new Chart(statusCtx, {
        type: 'doughnut',
        data: {
            labels: ['Normal', 'Low', 'High'],
            datasets: [{
                data: [statusCounts.Normal, statusCounts.Low, statusCounts.High],
                backgroundColor: ['#3a9d4c', '#ffb74d', '#e5534b']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Parameter Status Distribution'
                }
            }
        }
    });
    
    // Parameters values chart
    const paramsCtx = document.getElementById('parametersChart').getContext('2d');
    new Chart(paramsCtx, {
        type: 'bar',
        data: {
            labels: chartData.parameters,
            datasets: [{
                label: 'Parameter Values',
                data: chartData.values,
                backgroundColor: chartData.statuses.map(status => 
                    status === 'Normal' ? '#3a9d4c' : 
                    status === 'Low' ? '#ffb74d' : '#e5534b'
                )
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Parameter Values by Status'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Differential chart
    const diffCtx = document.getElementById('differentialChart').getContext('2d');
    const diffParams = ['NEUTROPHILS', 'LYMPHOCYTES', 'MONOCYTES', 'EOSINOPHILS', 'BASOPHILS'];
    const diffData = [];
    const diffLabels = [];
    
    diffParams.forEach(param => {
        const index = chartData.parameters.indexOf(param);
        if (index !== -1) {
            diffLabels.push(param);
            diffData.push(chartData.values[index]);
        }
    });
    
    if (diffData.length > 0) {
        new Chart(diffCtx, {
            type: 'pie',
            data: {
                labels: diffLabels,
                datasets: [{
                    data: diffData,
                    backgroundColor: ['#00788d', '#005a66', '#66c2cc', '#d9f0f3', '#1c2b3a']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'White Blood Cell Differential'
                    }
                }
            }
        });
    }
}

// Load correlations
async function loadCorrelations() {
    try {
        const response = await fetch('/get_correlations');
        const data = await response.json();
        
        if (data.success) {
            displayCorrelations(data.correlations);
        } else {
            alert('Error loading correlations: ' + data.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Display correlations
function displayCorrelations(correlations) {
    const content = document.getElementById('correlationsContent');
    
    if (correlations.length === 0) {
        content.innerHTML = `
            <div class="no-correlations">
                <i class="fas fa-check-circle"></i>
                <h3>No Significant Correlations Found</h3>
                <p>All parameters appear to be within normal ranges.</p>
            </div>
        `;
    } else {
        let html = '';
        correlations.forEach(corr => {
            html += `
                <div class="correlation-card">
                    <h3><i class="fas fa-exclamation-triangle"></i> Clinical Finding</h3>
                    <p>${corr}</p>
                </div>
            `;
        });
        content.innerHTML = html;
    }
}

// Show all trends (fixed version)
async function showAllTrends() {
    try {
        const response = await fetch('/get_all_trends');
        const data = await response.json();
        
        const modal = document.getElementById('trendsModal');
        const content = document.getElementById('trendsContent');
        
        if (data.message) {
            content.innerHTML = `
                <div class="no-trends">
                    <i class="fas fa-chart-line"></i>
                    <p>${data.message}</p>
                </div>
            `;
        } else if (data.trends) {
            let html = '';
            
            for (const [param, values] of Object.entries(data.trends)) {
                if (values.length > 0) {
                    html += `
                        <div class="trend-chart">
                            <h3>${param}</h3>
                            <div style="margin-top: 16px;">
                    `;
                    
                    values.forEach((item, index) => {
                        const date = new Date(item.date).toLocaleDateString();
                        html += `
                            <div class="trend-item">
                                <span class="trend-date">${date}</span>
                                <span class="trend-value">${item.value.toFixed(2)} ${item.unit || ''}</span>
                                <span class="status-badge ${item.status ? item.status.toLowerCase() : 'normal'}">${item.status || 'N/A'}</span>
                            </div>
                        `;
                    });
                    
                    html += `
                            </div>
                        </div>
                    `;
                }
            }
            
            content.innerHTML = html || '<div class="no-trends"><p>No trend data available</p></div>';
        }
        
        modal.style.display = 'flex';
    } catch (error) {
        alert('Error loading trends: ' + error.message);
    }
}

// Clear history
async function clearHistory() {
    if (confirm('Are you sure you want to clear all your history? This action cannot be undone.')) {
        try {
            const response = await fetch('/clear_history', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert('History cleared successfully!');
                location.reload();
            } else {
                alert('Error clearing history: ' + data.error);
            }
        } catch (error) {
            alert('Error: ' + error.message);
        }
    }
}

// Refresh analyzer
function refreshAnalyzer() {
    loadAnalyzerData();
}

// Update the download report function
async function downloadReport() {
    try {
        const response = await fetch('/download_full_report');
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `CBC_Report_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            const error = await response.json();
            alert('Error downloading report: ' + error.error);
        }
    } catch (error) {
        alert('Error downloading report: ' + error.message);
    }
}

// Add to your chat.js
function toggleHistory() {
    const historyContent = document.getElementById('historyContent');
    const historyToggle = document.getElementById('historyToggle');
    
    historyContent.classList.toggle('collapsed');
    const isCollapsed = historyContent.classList.contains('collapsed');
    
    historyToggle.innerHTML = isCollapsed ? 
        '<i class="fas fa-chevron-right"></i>' : 
        '<i class="fas fa-chevron-down"></i>';
}

function updateHistoryCount(count) {
    document.getElementById('historyCount').textContent = count;
}

// Initialize history as expanded by default
document.addEventListener('DOMContentLoaded', function() {
    // You might want to collapse if there are many history items
    const historyItems = document.querySelectorAll('.history-item').length;
    if (historyItems > 5) {
        toggleHistory(); // Auto-collapse if too many items
    }
    updateHistoryCount(historyItems);
});
// Add this script to your chat.js or in a script tag
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarClose = document.getElementById('sidebarClose');
    const chatContainer = document.querySelector('.chat-container');
    const mainContent = document.querySelector('.main-content');

    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
        sidebar.classList.toggle('active');
        chatContainer.classList.toggle('sidebar-collapsed');
        mainContent.classList.toggle('sidebar-expanded');
        sidebarOverlay.classList.toggle('active');
        sidebarToggle.classList.toggle('active');
    }

    sidebarToggle.addEventListener('click', toggleSidebar);
    sidebarOverlay.addEventListener('click', toggleSidebar);
    sidebarClose.addEventListener('click', toggleSidebar);

    // Close sidebar when clicking on links (mobile)
    if (window.innerWidth <= 1024) {
        const sidebarLinks = document.querySelectorAll('.sidebar a, .history-item');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', toggleSidebar);
        });
    }
});
