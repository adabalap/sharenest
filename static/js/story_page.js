document.addEventListener('DOMContentLoaded', () => {
    const storySections = document.querySelectorAll('.story-section');

    const options = {
        root: null, // viewport
        rootMargin: '0px',
        threshold: 0.2 // Trigger when 20% of the section is visible
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                // Optionally, unobserve once animated if it's a one-time animation
                // observer.unobserve(entry.target); 
            } else {
                // Optionally remove 'is-visible' if you want animations to reset when scrolling away
                // entry.target.classList.remove('is-visible');
            }
        });
    }, options);

    storySections.forEach(section => {
        observer.observe(section);
    });

    // Smooth scroll for internal links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();

            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Simple scroll indicator (optional, if needed for longer pages)
    // window.addEventListener('scroll', () => {
    //     const scrollPosition = window.scrollY;
    //     const totalHeight = document.body.scrollHeight - window.innerHeight;
    //     const progress = (scrollPosition / totalHeight) * 100;
    //     // Update a progress bar or indicator here
    // });
});