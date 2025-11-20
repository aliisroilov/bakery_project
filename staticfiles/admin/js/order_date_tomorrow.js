/**
 * Custom JavaScript to change the "Today" button to "Tomorrow" in Order admin
 */
(function() {
    'use strict';

    function changeTodayToTomorrow() {
        // Find all "Today" links in date widgets
        const todayLinks = document.querySelectorAll('.datetimeshortcuts a');

        todayLinks.forEach(function(link) {
            // Check if this is the "Today" link (supports both English and Uzbek)
            const linkText = link.textContent.trim();

            // Skip if already changed
            if (linkText === 'Ertaga' || link.dataset.tomorrowModified) {
                return;
            }

            if ((linkText === 'Today' || linkText === 'Bugun') && link.getAttribute('href') === '#') {
                // Mark as modified to prevent duplicate processing
                link.dataset.tomorrowModified = 'true';

                // Change text to "Tomorrow" (Ertaga in Uzbek)
                link.textContent = 'Ertaga';

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

    // Run immediately if DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            // Run after a short delay to ensure Django admin widgets are initialized
            setTimeout(changeTodayToTomorrow, 100);
        });
    } else {
        setTimeout(changeTodayToTomorrow, 100);
    }

    // Also run on window load as a fallback
    window.addEventListener('load', function() {
        setTimeout(changeTodayToTomorrow, 200);
    });

    // Watch for dynamically added date widgets (for inline formsets)
    if (window.MutationObserver) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length) {
                    changeTodayToTomorrow();
                }
            });
        });

        // Start observing after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            });
        } else {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    }
})();
