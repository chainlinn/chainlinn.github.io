(function() {
    var ruler = document.getElementById('toc-ruler');
    if (!ruler) return;

    var allHeadings = document.querySelectorAll('.post-content h1[id], .post-content h2[id], .post-content h3[id], .post-content h4[id]');
    if (allHeadings.length === 0) return;

    // Build hover card with all heading levels
    var card = document.createElement('div');
    card.className = 'toc-hover-card toc-hover-card-hidden';

    allHeadings.forEach(function(h) {
        var a = document.createElement('a');
        a.className = 'hc-item hc-level-' + h.tagName.toLowerCase();
        a.href = '#' + h.id;
        a.textContent = h.textContent.trim().replace(/\s*#\s*$/, '');
        a.addEventListener('click', function(e) {
            e.preventDefault();
            h.scrollIntoView({ behavior: 'smooth' });
        });
        card.appendChild(a);
    });

    ruler.insertBefore(card, ruler.firstChild);

    // Card scroll lock
    card.addEventListener('wheel', function(e) {
        e.preventDefault();
        card.scrollTop += e.deltaY;
    }, { passive: false });

    // Show/hide on ruler + card hover
    function show() { card.classList.remove('toc-hover-card-hidden'); update(); }
    function hide() { card.classList.add('toc-hover-card-hidden'); }

    ruler.addEventListener('mouseenter', show);
    ruler.addEventListener('mouseleave', function(e) { if (!card.contains(e.relatedTarget)) hide(); });
    card.addEventListener('mouseenter', show);
    card.addEventListener('mouseleave', function(e) { if (!ruler.contains(e.relatedTarget)) hide(); });

    // Ruler dots (h1/h2/h3)
    var dotHeadings = document.querySelectorAll('.post-content h1[id], .post-content h2[id], .post-content h3[id]');
    var dots = [];
    dotHeadings.forEach(function(h) {
        var dot = document.createElement('span');
        dot.className = 'toc-ruler-dot level-' + h.tagName.toLowerCase();
        dot.addEventListener('click', function() { h.scrollIntoView({ behavior: 'smooth' }); });
        ruler.appendChild(dot);
        dots.push({ dot: dot, heading: h });
    });

    function bestIdx(list, threshold) {
        var best = -1;
        for (var i = 0; i < list.length; i++) {
            if (list[i].getBoundingClientRect().top <= threshold) best = i;
        }
        return best;
    }

    var activeDotIdx = -1;
    var lastCardActiveId = null;

    function update() {
        // Dots: top threshold
        var dotBest = bestIdx(dots.map(function(d) { return d.heading; }), 80);
        if (dotBest !== activeDotIdx) {
            if (activeDotIdx >= 0) dots[activeDotIdx].dot.classList.remove('active');
            activeDotIdx = dotBest;
            if (activeDotIdx >= 0) dots[activeDotIdx].dot.classList.add('active');
        }

        // Card: top threshold when visible
        if (!card.classList.contains('toc-hover-card-hidden')) {
            var items = card.querySelectorAll('.hc-item');
            var cardHeadings = Array.from(items).map(function(a) {
                return document.getElementById(a.getAttribute('href').slice(1));
            }).filter(Boolean);
            var cardBest = bestIdx(cardHeadings, 80);
            var newId = cardBest >= 0 ? items[cardBest].getAttribute('href').slice(1) : null;
            if (newId !== lastCardActiveId) {
                items.forEach(function(i) { i.classList.remove('active'); });
                lastCardActiveId = newId;
                if (newId) {
                    var active = card.querySelector('.hc-item[href="#' + newId + '"]');
                    if (active) { active.classList.add('active'); }
                }
            }
        }
    }

    var ticking = false;
    window.addEventListener('scroll', function() {
        if (!ticking) { requestAnimationFrame(function() { update(); ticking = false; }); ticking = true; }
    }, { passive: true });
    update();
})();
