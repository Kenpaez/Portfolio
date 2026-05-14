// Main JavaScript file for interactive features

document.addEventListener('DOMContentLoaded', function() {
  // Initialize navigation menu toggle
  const navToggle = document.getElementById('nav-toggle');
  const navMenu = document.getElementById('nav-menu');
  
  if (navToggle && navMenu) {
    navToggle.addEventListener('click', function() {
      navToggle.classList.toggle('active');
      navMenu.classList.toggle('active');
    });
  }
  
  // Initialize header scroll behavior
  const header = document.getElementById('site-header');
  const heroSection = document.querySelector('.article-hero');
  
  if (header && heroSection) {
    // Set initial state
    updateHeaderAppearance();
    
    // Update on scroll
    window.addEventListener('scroll', function() {
      updateHeaderAppearance();
    });
    
    function updateHeaderAppearance() {
      const heroBottom = heroSection.offsetTop + heroSection.offsetHeight;
      const scrollPosition = window.scrollY;
      
      if (scrollPosition < heroBottom - header.offsetHeight) {
        header.classList.add('transparent');
      } else {
        header.classList.remove('transparent');
      }
    }
  }
  
  // Animate article sections on scroll
  const articleSections = document.querySelectorAll('.article-section');
  
  if (articleSections.length > 0) {
    // Remove initial animations to control with scroll
    articleSections.forEach(section => {
      section.style.animation = 'none';
      section.style.opacity = '0';
    });
    
    // Set up Intersection Observer
    const sectionObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.style.animation = 'fadeIn 1s ease forwards';
          observer.unobserve(entry.target);
        }
      });
    }, {
      root: null,
      threshold: 0.2,
      rootMargin: '-50px'
    });
    
    articleSections.forEach(section => {
      sectionObserver.observe(section);
    });
  }
  
  // Initialize smooth scrolling for table of contents links
  const tocLinks = document.querySelectorAll('.table-of-contents a');
  
  tocLinks.forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      
      const targetId = this.getAttribute('href');
      const targetElement = document.querySelector(targetId);
      
      if (targetElement) {
        // Calculate offset to account for fixed header
        const headerHeight = header ? header.offsetHeight : 0;
        const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset - headerHeight - 20;
        
        window.scrollTo({
          top: targetPosition,
          behavior: 'smooth'
        });
        
        // Update URL without page reload
        history.pushState(null, null, targetId);
      }
    });
  });
  
  // Reading progress indicator
  const progressBar = document.createElement('div');
  progressBar.className = 'reading-progress';
  progressBar.style.position = 'fixed';
  progressBar.style.top = '0';
  progressBar.style.left = '0';
  progressBar.style.height = '3px';
  progressBar.style.backgroundColor = 'var(--color-accent)';
  progressBar.style.zIndex = 'var(--z-index-fixed)';
  progressBar.style.width = '0%';
  progressBar.style.transition = 'width 0.2s';
  
  document.body.appendChild(progressBar);
  
  window.addEventListener('scroll', function() {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const scrollPercent = (scrollTop / docHeight) * 100;
    progressBar.style.width = scrollPercent + '%';
  });
  
  // Initialize share buttons
  const shareButtons = document.querySelectorAll('.share-button');
  const articleTitle = document.querySelector('.article-title').textContent;
  const currentUrl = window.location.href;
  
  shareButtons.forEach(button => {
    button.addEventListener('click', function(e) {
      e.preventDefault();
      
      let shareUrl = '';
      
      if (this.classList.contains('twitter')) {
        shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(articleTitle)}&url=${encodeURIComponent(currentUrl)}`;
      } else if (this.classList.contains('facebook')) {
        shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(currentUrl)}`;
      } else if (this.classList.contains('linkedin')) {
        shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(currentUrl)}`;
      } else if (this.classList.contains('email')) {
        shareUrl = `mailto:?subject=${encodeURIComponent(articleTitle)}&body=${encodeURIComponent(currentUrl)}`;
      }
      
      if (shareUrl) {
        window.open(shareUrl, '_blank', 'width=600,height=400');
      }
    });
  });
  
  // Add image lazy loading
  const images = document.querySelectorAll('img');
  
  if ('loading' in HTMLImageElement.prototype) {
    // Browser supports native lazy loading
    images.forEach(img => {
      if (!img.hasAttribute('loading')) {
        img.setAttribute('loading', 'lazy');
      }
    });
  } else {
    // Fallback for browsers that don't support lazy loading
    // This is a simple implementation; consider using a dedicated library for production
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const image = entry.target;
          const src = image.getAttribute('data-src');
          
          if (src) {
            image.src = src;
            image.removeAttribute('data-src');
          }
          
          observer.unobserve(image);
        }
      });
    });
    
    images.forEach(img => {
      if (!img.hasAttribute('data-src') && img.hasAttribute('src')) {
        img.setAttribute('data-src', img.src);
        img.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"%3E%3C/svg%3E';
        imageObserver.observe(img);
      }
    });
  }
});