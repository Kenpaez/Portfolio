const hamburger = document.querySelector('.hamburger');
const navMenu = document.querySelector('.nav-menu');
const navLinks = document.querySelectorAll('.nav-link');
const navbar = document.querySelector('.navbar');
const contactForm = document.getElementById('contactForm');

hamburger.addEventListener('click', () => {
  hamburger.classList.toggle('active');
  navMenu.classList.toggle('active');
});

navLinks.forEach(link => {
  link.addEventListener('click', () => {
    hamburger.classList.remove('active');
    navMenu.classList.remove('active');
  });
});

window.addEventListener('scroll', () => {
  if (window.scrollY > 50) {
    navbar.classList.add('scrolled');
  } else {
    navbar.classList.remove('scrolled');
  }
});

const observerOptions = {
  threshold: 0.3,
  rootMargin: '0px'
};

const animateSkills = (entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const skillBars = entry.target.querySelectorAll('.skill-progress');
      skillBars.forEach(bar => {
        const progress = bar.getAttribute('data-progress');
        bar.style.setProperty('--progress-width', progress + '%');
        bar.classList.add('animated');
      });
    }
  });
};

const skillsObserver = new IntersectionObserver(animateSkills, observerOptions);
const skillsSection = document.querySelector('.skills');
if (skillsSection) {
  skillsObserver.observe(skillsSection);
}

const fadeInElements = document.querySelectorAll('.project-card, .stat-card, .skill-category');
const fadeInObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '0';
      entry.target.style.transform = 'translateY(20px)';
      entry.target.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';

      setTimeout(() => {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }, 100);

      fadeInObserver.unobserve(entry.target);
    }
  });
}, observerOptions);

fadeInElements.forEach(element => {
  fadeInObserver.observe(element);
});

contactForm.addEventListener('submit', (e) => {
  e.preventDefault();

  const formData = new FormData(contactForm);
  const data = Object.fromEntries(formData);

  console.log('Form submitted:', data);

  const button = contactForm.querySelector('button[type="submit"]');
  const originalText = button.textContent;
  button.textContent = 'Sending...';
  button.disabled = true;

  setTimeout(() => {
    alert('Thank you for your message! I will get back to you soon.');
    contactForm.reset();
    button.textContent = originalText;
    button.disabled = false;
  }, 1000);
});

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      const offsetTop = target.offsetTop - 70;
      window.scrollTo({
        top: offsetTop,
        behavior: 'smooth'
      });
    }
  });
});
