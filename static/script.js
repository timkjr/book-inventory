// static/script.js

document.addEventListener('DOMContentLoaded', function() {
    // Auto-focus search field when on home page
    const searchInput = document.querySelector('input[name="search"]');
    if (searchInput && !searchInput.value) {
        searchInput.focus();
    }

    // Auto-fill today's date for lending
    const loanedDateInput = document.getElementById('loaned_date');
    if (loanedDateInput && !loanedDateInput.value) {
        const today = new Date().toISOString().split('T')[0];
        loanedDateInput.addEventListener('focus', function() {
            if (!this.value) {
                this.value = today;
            }
        });
    }

    // Clear loaned fields when "loaned to" is emptied
    const loanedToInput = document.getElementById('loaned_to');
    if (loanedToInput) {
        loanedToInput.addEventListener('input', function() {
            if (!this.value.trim()) {
                const loanedDate = document.getElementById('loaned_date');
                const dueDate = document.getElementById('due_date');
                if (loanedDate) loanedDate.value = '';
                if (dueDate) dueDate.value = '';
            }
        });
    }

    // Auto-calculate due date (30 days from loan date)
    if (loanedDateInput) {
        loanedDateInput.addEventListener('change', function() {
            const dueDateInput = document.getElementById('due_date');
            if (dueDateInput && this.value && !dueDateInput.value) {
                const loanDate = new Date(this.value);
                loanDate.setDate(loanDate.getDate() + 30);
                dueDateInput.value = loanDate.toISOString().split('T')[0];
            }
        });
    }

    // Format ISBN input
    const isbnInput = document.getElementById('isbn');
    if (isbnInput) {
        isbnInput.addEventListener('input', function() {
            // Remove any non-digit, non-X characters
            let value = this.value.replace(/[^0-9X]/gi, '');
            
            // Format as ISBN-13 or ISBN-10
            if (value.length <= 10) {
                // ISBN-10 format: 0-123456-78-9
                value = value.replace(/^(\d{1})(\d{6})(\d{2})(\d{1})$/, '$1-$2-$3-$4');
            } else if (value.length <= 13) {
                // ISBN-13 format: 978-0-123456-78-9
                value = value.replace(/^(\d{3})(\d{1})(\d{6})(\d{2})(\d{1})$/, '$1-$2-$3-$4-$5');
            }
            
            this.value = value;
        });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        
        // Ctrl/Cmd + N to add new book
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/add';
        }
    });

    // Enhanced form validation
    const bookForm = document.querySelector('.book-form');
    if (bookForm) {
        bookForm.addEventListener('submit', function(e) {
            const title = document.getElementById('title');
            const author = document.getElementById('author');
            
            if (!title.value.trim()) {
                e.preventDefault();
                title.focus();
                showMessage('Please enter a book title', 'error');
                return;
            }
            
            if (!author.value.trim()) {
                e.preventDefault();
                author.focus();
                showMessage('Please enter an author name', 'error');
                return;
            }
        });
    }

    // Show loading state for ISBN lookups
    const lookupCheckbox = document.querySelector('input[name="lookup_metadata"]');
    if (lookupCheckbox && isbnInput) {
        const form = lookupCheckbox.closest('form');
        if (form) {
            form.addEventListener('submit', function() {
                if (lookupCheckbox.checked && isbnInput.value.trim()) {
                    const submitBtn = form.querySelector('button[type="submit"]');
                    if (submitBtn) {
                        submitBtn.disabled = true;
                        submitBtn.textContent = 'Adding Book...';
                    }
                }
            });
        }
    }
});

// Utility function to show messages
function showMessage(message, type = 'info') {
    // Remove existing messages
    const existingMessage = document.querySelector('.flash-message');
    if (existingMessage) {
        existingMessage.remove();
    }

    // Create new message
    const messageDiv = document.createElement('div');
    messageDiv.className = `flash-message flash-${type}`;
    messageDiv.textContent = message;
    
    // Style the message
    Object.assign(messageDiv.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '12px 20px',
        borderRadius: '6px',
        color: 'white',
        fontWeight: '500',
        zIndex: '1000',
        maxWidth: '400px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
    });

    // Set background color based on type
    switch (type) {
        case 'error':
            messageDiv.style.backgroundColor = '#dc2626';
            break;
        case 'success':
            messageDiv.style.backgroundColor = '#059669';
            break;
        case 'warning':
            messageDiv.style.backgroundColor = '#d97706';
            break;
        default:
            messageDiv.style.backgroundColor = '#2563eb';
    }

    // Add to page
    document.body.appendChild(messageDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateX(100%)';
        messageDiv.style.transition = 'all 0.3s ease';
        setTimeout(() => messageDiv.remove(), 300);
    }, 5000);

    // Click to dismiss
    messageDiv.addEventListener('click', () => {
        messageDiv.remove();
    });
}

// Export functions for potential future use
window.BookInventory = {
    showMessage
};