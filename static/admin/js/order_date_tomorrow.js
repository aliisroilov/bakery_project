/**
 * Custom JavaScript to change the "Today" button to "Tomorrow" in Order admin
 */
(function() {
    'use strict';

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        // Find all "Today" links in date widgets
        const todayLinks = document.querySelectorAll('.datetimeshortcuts a');

        todayLinks.forEach(function(link) {
            // Check if this is the "Today" link for order_date field
            if (link.textContent.trim() === 'Today' && link.getAttribute('href') === '#') {
                // Change text to "Tomorrow"
                link.textContent = 'Tomorrow';

                // Override click behavior to set tomorrow's date
                link.addEventListener('click', function(e) {
                    e.preventDefault();

                    // Get the associated date input field
                    const dateInput = this.closest('.form-row').querySelector('input[type="text"][name*="order_date"]');

                    if (dateInput) {
                        // Calculate tomorrow's date
                        const tomorrow = new Date();
                        tomorrow.setDate(tomorrow.getDate() + 1);

                        // Format as YYYY-MM-DD
                        const year = tomorrow.getFullYear();
                        const month = String(tomorrow.getMonth() + 1).padStart(2, '0');
                        const day = String(tomorrow.getDate()).padStart(2, '0');

                        // Set the value
                        dateInput.value = year + '-' + month + '-' + day;

                        // Trigger change event
                        dateInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    return false;
                });
            }
        });
    }
})();
