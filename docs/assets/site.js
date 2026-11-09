// L'Espiral · menú del mòbil, capçalera amb ombra, aparició suau dels blocs i vídeos que es carreguen en clicar
(function () {
  window.espiralMoviment = true;

  var bar = document.querySelector('.topbar');
  var btn = document.querySelector('.menu-btn');
  if (bar) {
    var onScroll = function () { bar.classList.toggle('is-scrolled', window.scrollY > 8); };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }
  if (bar && btn) {
    btn.addEventListener('click', function () {
      var open = bar.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      btn.setAttribute('aria-label', open ? btn.getAttribute('data-label-close') : btn.getAttribute('data-label-open'));
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && bar.classList.contains('is-open')) { btn.click(); btn.focus(); }
    });
  }

  // Els blocs apareixen suaument quan arriben a la pantalla (amb «reduir moviment», ja hi són)
  var els = document.querySelectorAll('.reveal');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(els, function (el) { el.classList.add('is-in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
    }, { threshold: 0.06, rootMargin: '0px 0px -30px 0px' });
    Array.prototype.forEach.call(els, function (el) { io.observe(el); });
  }

  // Vídeos de YouTube: la imatge es canvia pel vídeo en clicar (la pàgina no carrega YouTube fins aleshores)
  Array.prototype.forEach.call(document.querySelectorAll('[data-yt]'), function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var f = document.createElement('iframe');
      f.src = 'https://www.youtube-nocookie.com/embed/' + a.getAttribute('data-yt') + '?autoplay=1&rel=0';
      f.title = a.getAttribute('aria-label') || 'Vídeo';
      f.allow = 'autoplay; encrypted-media; picture-in-picture';
      f.allowFullscreen = true;
      a.replaceWith(f);
    });
  });

  // Mapa de Google: es carrega quan es clica el botó (abans, la pàgina no es connecta a Google)
  Array.prototype.forEach.call(document.querySelectorAll('[data-map]'), function (box) {
    var b = box.querySelector('button');
    if (!b) return;
    b.addEventListener('click', function () {
      var f = document.createElement('iframe');
      f.src = box.getAttribute('data-map');
      f.title = 'Mapa de Google';
      f.loading = 'lazy';
      f.referrerPolicy = 'no-referrer-when-downgrade';
      box.appendChild(f);
      b.remove();
    });
  });
})();
