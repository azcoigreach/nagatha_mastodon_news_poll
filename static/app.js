// Character counters for Mastodon limits
document.addEventListener('DOMContentLoaded', function() {
    // Question character counter (max 100)
    const questionInput = document.getElementById('poll-question');
    const questionCounter = document.getElementById('question-counter');
    
    if (questionInput && questionCounter) {
        questionInput.addEventListener('input', function() {
            const length = this.value.length;
            const remaining = 100 - length;
            questionCounter.textContent = remaining;
            
            questionCounter.classList.remove('warning', 'danger');
            if (remaining < 20 && remaining >= 0) {
                questionCounter.classList.add('warning');
            } else if (remaining < 0) {
                questionCounter.classList.add('danger');
            }
        });
        // Trigger initial count
        questionInput.dispatchEvent(new Event('input'));
    }
    
    // Option character counters (max 50 each)
    document.querySelectorAll('.poll-option-input').forEach((input, index) => {
        const counter = document.getElementById(`option-${index}-counter`);
        if (counter) {
            input.addEventListener('input', function() {
                const length = this.value.length;
                const remaining = 50 - length;
                counter.textContent = remaining;
                
                counter.classList.remove('warning', 'danger');
                if (remaining < 10 && remaining >= 0) {
                    counter.classList.add('warning');
                } else if (remaining < 0) {
                    counter.classList.add('danger');
                }
            });
            // Trigger initial count
            input.dispatchEvent(new Event('input'));
        }
    });
    
    // Clear flash messages from session after display
    if (document.querySelector('.alert')) {
        // Flash messages are displayed, clear them from session
        fetch('/clear-messages', { method: 'POST' }).catch(() => {});
    }
    
    // Auto-refresh poll status every 5 seconds on detail page
    const pollDetailRefresh = document.getElementById('poll-detail-refresh');
    if (pollDetailRefresh) {
        setInterval(function() {
            htmx.trigger('#poll-status-badge', 'refresh');
        }, 5000);
    }
    
    // Confirm delete actions
    document.querySelectorAll('[data-confirm]').forEach(element => {
        element.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        });
    });
    
    // Form validation for poll editing
    const pollForm = document.getElementById('poll-edit-form');
    if (pollForm) {
        pollForm.addEventListener('submit', function(e) {
            const question = document.getElementById('poll-question');
            const options = document.querySelectorAll('.poll-option-input');
            let valid = true;
            let errors = [];
            
            // Validate question length
            if (question.value.length > 100) {
                errors.push('Question must be 100 characters or less');
                valid = false;
            }
            
            if (question.value.trim() === '') {
                errors.push('Question cannot be empty');
                valid = false;
            }
            
            // Validate options
            let filledOptions = 0;
            options.forEach(option => {
                if (option.value.trim() !== '') {
                    filledOptions++;
                    if (option.value.length > 50) {
                        errors.push('Poll options must be 50 characters or less');
                        valid = false;
                    }
                }
            });
            
            if (filledOptions < 2) {
                errors.push('You must provide at least 2 poll options');
                valid = false;
            }
            
            if (filledOptions > 4) {
                errors.push('Maximum 4 poll options allowed');
                valid = false;
            }
            
            // Validate duration
            const duration = document.getElementById('poll-duration');
            if (duration) {
                const hours = parseInt(duration.value);
                if (hours < 1 || hours > 168) {
                    errors.push('Duration must be between 1 and 168 hours');
                    valid = false;
                }
            }
            
            if (!valid) {
                e.preventDefault();
                alert('Please fix the following errors:\n\n' + errors.join('\n'));
            }
        });
    }
    
    // Live poll preview update
    const previewElements = {
        question: document.getElementById('poll-question'),
        options: document.querySelectorAll('.poll-option-input'),
        duration: document.getElementById('poll-duration')
    };
    
    const previewDisplay = {
        question: document.getElementById('preview-question'),
        options: document.querySelectorAll('.preview-option'),
        duration: document.getElementById('preview-duration')
    };
    
    if (previewElements.question && previewDisplay.question) {
        previewElements.question.addEventListener('input', function() {
            previewDisplay.question.textContent = this.value || '[Question]';
        });
        
        previewElements.options.forEach((input, index) => {
            input.addEventListener('input', function() {
                if (previewDisplay.options[index]) {
                    const optionText = this.value.trim() || `[Option ${index + 1}]`;
                    previewDisplay.options[index].textContent = optionText;
                    
                    // Show/hide based on whether there's content
                    if (this.value.trim()) {
                        previewDisplay.options[index].parentElement.style.display = 'block';
                    } else if (index >= 2) {
                        // Hide empty options beyond the first 2
                        previewDisplay.options[index].parentElement.style.display = 'none';
                    }
                }
            });
        });
        
        if (previewElements.duration && previewDisplay.duration) {
            previewElements.duration.addEventListener('input', function() {
                const hours = parseInt(this.value) || 24;
                let displayText;
                if (hours >= 24) {
                    const days = Math.floor(hours / 24);
                    const remainingHours = hours % 24;
                    displayText = remainingHours > 0 
                        ? `${days} day${days > 1 ? 's' : ''}, ${remainingHours} hour${remainingHours > 1 ? 's' : ''}`
                        : `${days} day${days > 1 ? 's' : ''}`;
                } else {
                    displayText = `${hours} hour${hours > 1 ? 's' : ''}`;
                }
                previewDisplay.duration.textContent = displayText;
            });
        }
    }
});

// Helper function to format timestamps
function formatTimestamp(isoString) {
    try {
        // Ensure timestamp is treated as UTC; backend sends naive ISO strings
        const normalized = isoString.endsWith('Z') ? isoString : `${isoString}Z`;
        const date = new Date(normalized);
        if (isNaN(date.getTime())) {
            console.error('Invalid timestamp:', isoString);
            return 'unknown';
        }
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } catch(e) {
        console.error('Error parsing timestamp:', isoString, e);
        return 'unknown';
    }
}

// Update all timestamps on page
function updateTimestamps() {
    const elements = document.querySelectorAll('[data-timestamp]');
    console.log(`Updating ${elements.length} timestamps`);
    elements.forEach(element => {
        const timestamp = element.getAttribute('data-timestamp');
        const formatted = formatTimestamp(timestamp);
        console.log(`Timestamp: ${timestamp} -> ${formatted}`);
        element.textContent = formatted;
    });
}

// Update timestamps every minute
setInterval(updateTimestamps, 60000);
updateTimestamps();
