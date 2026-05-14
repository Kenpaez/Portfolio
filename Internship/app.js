document.addEventListener('DOMContentLoaded', () => {
  const featuredGrid = document.getElementById('featuredGrid');
  const articlesGrid = document.getElementById('articlesGrid');

  const getCategoryColor = (category) => {
    const colors = {
      'Technology': 'bg-blue-100 text-blue-800',
      'Design': 'bg-purple-100 text-purple-800',
      'Development': 'bg-green-100 text-green-800',
      'UX': 'bg-orange-100 text-orange-800',
      'Ethics': 'bg-red-100 text-red-800'
    };
    return colors[category] || 'bg-gray-100 text-gray-800';
  };

  const createCard = (post, featured = false) => {
    const card = document.createElement('article');
    card.className = 'card';
    
    card.innerHTML = `
      <div class="card-image">
        <img src="${post.imageUrl}" alt="${post.title}">
        <span class="card-category">${post.category}</span>
      </div>
      <div class="card-content">
        <h3 class="card-title">${post.title}</h3>
        <p class="card-excerpt">${post.excerpt}</p>
        <div class="card-meta">
          <span>${post.author}</span>
          <span>${post.date}</span>
        </div>
         <a href="article/${post.id}.html" class="read-more-btn">
          Read Article
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </a>
      </div>
    `;
    
    return card;
  };

  // Render featured posts
  const featuredPosts = blogPosts.filter(post => post.featured);
  featuredPosts.forEach(post => {
    featuredGrid.appendChild(createCard(post, true));
  });

  // Render regular posts
  const regularPosts = blogPosts.filter(post => !post.featured);
  regularPosts.forEach(post => {
    articlesGrid.appendChild(createCard(post));
  });

  // Search functionality
  const searchInput = document.querySelector('.search-input');
  searchInput.addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();
    const allCards = document.querySelectorAll('.card');
    
    allCards.forEach(card => {
      const title = card.querySelector('.card-title').textContent.toLowerCase();
      const excerpt = card.querySelector('.card-excerpt').textContent.toLowerCase();
      const isVisible = title.includes(searchTerm) || excerpt.includes(searchTerm);
      card.style.display = isVisible ? 'block' : 'none';
    });
  });

  // Subscribe form handling
  const subscribeForms = document.querySelectorAll('.subscribe-form');
  subscribeForms.forEach(form => {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = form.querySelector('input[type="email"]').value;
      alert(`Thank you for subscribing with: ${email}`);
      form.reset();
    });
  });
});