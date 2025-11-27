// static/js/story_page.js

document.addEventListener('DOMContentLoaded', () => {
    const slides = document.querySelectorAll('.story-slide');
    const paginationDotsContainer = document.querySelector('.pagination-dots');
    const prevBtn = document.querySelector('.nav-btn.prev-btn');
    const nextBtn = document.querySelector('.nav-btn.next-btn');
    let currentSlideIndex = 0;

    // Create pagination dots
    slides.forEach((_, index) => {
        const dot = document.createElement('span');
        dot.classList.add('dot');
        if (index === 0) {
            dot.classList.add('active');
        }
        dot.dataset.slideIndex = index;
        paginationDotsContainer.appendChild(dot);
    });

    const paginationDots = document.querySelectorAll('.pagination-dots .dot');

    function updateSlide(newIndex) {
        if (newIndex < 0 || newIndex >= slides.length) {
            return; // Stay within bounds
        }

        // Determine direction for animation
        const direction = newIndex > currentSlideIndex ? 'next' : 'prev';

        // Remove active class from current slide and add direction class
        slides[currentSlideIndex].classList.remove('active');
        slides[currentSlideIndex].classList.add(direction); // Add class for exit animation

        // Update active dot
        paginationDots[currentSlideIndex].classList.remove('active');
        paginationDots[newIndex].classList.add('active');

        currentSlideIndex = newIndex;

        // Add active class to new slide, remove any direction classes
        slides[currentSlideIndex].classList.remove('prev', 'next'); // Clean up old direction classes
        slides[currentSlideIndex].classList.add('active');

        // Update button states
        prevBtn.disabled = currentSlideIndex === 0;
        nextBtn.disabled = currentSlideIndex === slides.length - 1;

        // Focus on the current slide for accessibility (optional)
        slides[currentSlideIndex].focus();
    }

    // Initialize button states
    updateSlide(0); // Call once to set initial states

    // Event listeners for navigation buttons
    prevBtn.addEventListener('click', () => {
        updateSlide(currentSlideIndex - 1);
    });

    nextBtn.addEventListener('click', () => {
        updateSlide(currentSlideIndex + 1);
    });

    // Event listeners for pagination dots
    paginationDots.forEach(dot => {
        dot.addEventListener('click', (event) => {
            const index = parseInt(event.target.dataset.slideIndex);
            updateSlide(index);
        });
    });

    // Keyboard navigation (optional)
    document.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowRight') {
            updateSlide(currentSlideIndex + 1);
        } else if (event.key === 'ArrowLeft') {
            updateSlide(currentSlideIndex - 1);
        }
    });

    // Handle "Explore the Story" button on the first slide
    const exploreBtn = document.querySelector('#slide-1 .btn-primary');
    if (exploreBtn) {
        exploreBtn.addEventListener('click', () => {
            updateSlide(currentSlideIndex + 1);
        });
    }
});
