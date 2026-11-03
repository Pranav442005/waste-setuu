(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const dots = document.getElementById('dots');
  let index = 0, timer;
  const show = n => {
    if (!slides.length) return;
    index = (n + slides.length) % slides.length;
    slides.forEach((s, i) => s.classList.toggle('active', i === index));
    [...(dots?.children || [])].forEach((d, i) => d.classList.toggle('active', i === index));
  };
  slides.forEach((_, i) => {
    const b = document.createElement('button');
    b.type = 'button'; b.setAttribute('aria-label', `Show banner ${i + 1}`);
    b.addEventListener('click', () => { show(i); restart(); });
    dots?.appendChild(b);
  });
  const stop = () => { if (timer) clearInterval(timer); timer = null; };
  const start = () => { stop(); if (slides.length > 1) timer = setInterval(() => show(index + 1), window.WASTE_SETU_CONFIG?.carouselIntervalMs || 3000); };
  const restart = start;
  document.getElementById('prev')?.addEventListener('click', () => { show(index - 1); restart(); });
  document.getElementById('next')?.addEventListener('click', () => { show(index + 1); restart(); });
  show(0); start();
  document.querySelector('.hero')?.addEventListener('mouseenter', stop);
  document.querySelector('.hero')?.addEventListener('mouseleave', start);
  const menu = document.getElementById('menuToggle'), links = document.getElementById('navLinks');
  menu?.addEventListener('click', () => { const open = links.classList.toggle('open'); menu.setAttribute('aria-expanded', String(open)); });
  document.getElementById('year').textContent = new Date().getFullYear();
  
})();


/* ================= HERO IMAGE SLIDER ================= */

document.addEventListener("DOMContentLoaded", function () {

    const slides = document.querySelectorAll(".hero .slide");
    const dots = document.querySelectorAll("#dots button");

    const prevButton = document.getElementById("prevSlide");
    const nextButton = document.getElementById("nextSlide");

    if (slides.length === 0) {
        console.log("No hero slides found!");
        return;
    }

    let currentSlide = 0;
    let slideInterval;

    function showSlide(index) {

        slides.forEach((slide, i) => {
            slide.classList.toggle("active", i === index);
        });

        dots.forEach((dot, i) => {
            dot.classList.toggle("active", i === index);
        });

        currentSlide = index;
    }

    function nextSlide() {
        showSlide((currentSlide + 1) % slides.length);
    }

    function previousSlide() {
        showSlide(
            (currentSlide - 1 + slides.length) % slides.length
        );
    }

    function startAutoSlide() {
        clearInterval(slideInterval);
        slideInterval = setInterval(nextSlide, 5000);
    }

    // Next button
    if (nextButton) {
        nextButton.addEventListener("click", function () {
            nextSlide();
            startAutoSlide();
        });
    }

    // Previous button
    if (prevButton) {
        prevButton.addEventListener("click", function () {
            previousSlide();
            startAutoSlide();
        });
    }

    // Dot navigation
    dots.forEach((dot, index) => {
        dot.addEventListener("click", function () {
            showSlide(index);
            startAutoSlide();
        });
    });

    // Start slider
    showSlide(0);
    startAutoSlide();

    console.log("Waste Setu image slider initialized!");

});
<script src="/assets/js/waste-setu-assistant.js" defer></script>
