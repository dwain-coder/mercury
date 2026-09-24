// 浅草橋ホテルガイド — the only script on the site. No dependencies.
// Mobile sticky booking bar: appears once the reader is past the first screen, and steps
// aside whenever an in-page booking module or the footer is on screen, so it never sits on
// top of the thing it duplicates and never covers the disclosure text.
(function () {
  var bar = document.querySelector('.stickybook');
  if (!bar || !('IntersectionObserver' in window)) return;

  var onScreen = new Set();
  var past = false;
  function update() { bar.hidden = !(past && onScreen.size === 0); }

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) onScreen.add(e.target); else onScreen.delete(e.target);
    });
    update();
  });
  document.querySelectorAll('.book, .widget, .foot, .proph__cta').forEach(function (el) { io.observe(el); });

  window.addEventListener('scroll', function () {
    past = window.scrollY > window.innerHeight * 0.8;
    update();
  }, { passive: true });
})();

// Atlas: a numbered pin and its legend row light up together, so the list and the map read
// as one thing. Pure progressive enhancement — both work without it.
(function () {
  document.querySelectorAll('.atlas').forEach(function (atlas) {
    function set(id, on) {
      atlas.querySelectorAll('[data-place="' + id + '"]').forEach(function (el) {
        el.classList.toggle('is-on', on);
      });
    }
    atlas.addEventListener('pointerover', function (e) {
      var t = e.target.closest('[data-place]');
      if (t) set(t.dataset.place, true);
    });
    atlas.addEventListener('pointerout', function (e) {
      var t = e.target.closest('[data-place]');
      if (t) set(t.dataset.place, false);
    });
    atlas.addEventListener('click', function (e) {
      var pin = e.target.closest('.a-pin');
      if (!pin) return;
      var row = atlas.querySelector('li[data-place="' + pin.dataset.place + '"] a');
      if (row) row.focus();
    });
  });
})();

// Film: plays (muted) only while on screen, pauses when scrolled away. Readers who ask for
// reduced motion get the poster and the controls — never autoplay.
(function () {
  var v = document.querySelector('.film__video');
  if (!v || !('IntersectionObserver' in window)) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  v.loop = true;
  new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (e.isIntersecting && e.intersectionRatio > .5) { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
      else v.pause();
    });
  }, { threshold: [0, .5, 1] }).observe(v);
})();

// YouTube facade: swap the thumbnail for a youtube-nocookie player only when asked.
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('.yt__play');
  if (!a) return;
  e.preventDefault();
  var f = document.createElement('iframe');
  f.src = 'https://www.youtube-nocookie.com/embed/' + a.dataset.yt + '?autoplay=1&rel=0';
  f.title = a.getAttribute('aria-label') || 'YouTube';
  f.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture';
  f.allowFullscreen = true;
  a.replaceWith(f);
});

// Scroll motion fallback for browsers without scroll-driven animations. Marks blocks .rv and
// reveals them as they enter. Never runs under reduced motion; without JS nothing is hidden.
(function () {
  if (CSS.supports && CSS.supports('animation-timeline: view()')) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!('IntersectionObserver' in window)) return;
  var sel = '.idx__row, .photo, .yt, .tbl, .diagram, .room, .bc__band, .fit, .book, .propcard, ' +
            '.hour__b > *, .sources, .hubnav > section, .mag__label, .mag__dek, ' +
            '.prose > h2, .prose > h3, .prose > p, .prose > ul, .prose > ol, .sec > h2, .sec > p, .sec > ul';
  var els = Array.prototype.filter.call(document.querySelectorAll(sel), function (el) {
    return !el.closest('.atlas-hero, .proph, .phead') && !(el.matches('.photo') && el.closest('.room')) &&
           el.getBoundingClientRect().top > window.innerHeight;   // leave the first screen alone
  });
  document.documentElement.classList.add('rv-js');
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px' });
  els.forEach(function (el) { el.classList.add('rv'); io.observe(el); });
})();

// 着いてから、チェックインまで — arrival planner. Figures come from the page (JSON built from
// the sourced facts); the landing-to-train buffer is the reader's own estimate.
(function () {
  var DEF = { 'haneda-dom': 30, 'haneda-intl': 75, 'narita': 75 };   // editable starting points
  function hm(m) { m = ((m % 1440) + 1440) % 1440; return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); }
  function fmt(m) { return (m >= 1440 ? '翌' : '') + hm(m); }
  document.querySelectorAll('.arr').forEach(function (sec) {
    var d = JSON.parse(sec.querySelector('.arr__data').textContent);
    var f = sec.querySelector('form'), out = sec.querySelector('.arr__out'), bv = sec.querySelector('.arr__buf-v');
    var touched = false;
    function calc() {
      var t = (f.land.value || '20:30').split(':'), land = +t[0] * 60 + +t[1];
      var buf = +f.buf.value, ride = f.ap.value === 'narita' ? d.narita : d.haneda;
      var at = land + buf + ride + d.walk;
      bv.textContent = '　' + buf + '分';
      var cls, head, body;
      if (at >= 1440 || at > d.close) {
        cls = 'late'; head = '受付終了（' + hm(d.close) + '）より後に着く見込みです';
        body = '予約の前に施設へ到着時刻を伝えて確認するか、深夜も受け付ける宿を検討してください。';
      } else if (at > d.close - 30) {
        cls = 'tight'; head = '受付終了（' + hm(d.close) + '）に近い、ぎりぎりの時刻です';
        body = '遅れる可能性があるなら、予約時に到着時刻を施設へ伝えておくのが確実です。';
      } else if (at < d.open) {
        cls = 'early'; head = 'チェックイン開始（' + hm(d.open) + '）より前に着きます';
        body = 'チェックイン前の荷物預かり（無料）を使って、身軽に街へ出られます。';
      } else {
        cls = 'ok'; head = 'チェックインの受付時間内に着く目安です';
        body = '受付は ' + hm(d.open) + '〜' + hm(d.close) + '。';
      }
      out.className = 'arr__out arr__out--' + cls;
      out.innerHTML =
        '<ol class="arr__steps">' +
        '<li><b>' + hm(land) + '</b>着陸</li>' +
        '<li><b>+' + buf + '分</b>電車に乗るまで</li>' +
        '<li><b>+' + ride + '分</b>' + (f.ap.value === 'narita' ? '成田' : '羽田') + 'から浅草橋（施設の目安）</li>' +
        '<li><b>+' + d.walk + '分</b>駅から宿</li>' +
        '<li class="arr__at"><b>' + fmt(at) + '</b>宿に着く目安</li></ol>' +
        '<p class="arr__verdict"><strong>' + head + '</strong>' + body + '</p>' +
        '<p class="arr__more"><a href="#book">日付を入れて空室を見る</a></p>';
    }
    f.ap.addEventListener('change', function () { if (!touched) f.buf.value = DEF[f.ap.value]; calc(); });
    f.buf.addEventListener('input', function () { touched = true; calc(); });
    f.land.addEventListener('input', calc);
    f.buf.value = DEF[f.ap.value];
    calc();
  });
})();

// The sky over 浅草橋, now. A strip under the masthead takes the colour of the current hour in
// Tokyo (the 24 Hours palette) and shows the local time — wherever the reader is.
(function () {
  var a = document.querySelector('.sky');
  if (!a || !window.Intl) return;
  var STOPS = [[0, '#171b27'], [270, '#2f3552'], [360, '#e7c3b1'], [480, '#dfe7ee'], [720, '#faf7ef'],
               [900, '#efdcbb'], [1050, '#e2a676'], [1140, '#2b3144'], [1320, '#171b27'], [1440, '#171b27']];
  function rgb(h) { return [1, 3, 5].map(function (i) { return parseInt(h.slice(i, i + 2), 16); }); }
  function mix(m) {
    for (var i = 0; i < STOPS.length - 1; i++) {
      var p = STOPS[i], q = STOPS[i + 1];
      if (m >= p[0] && m <= q[0]) {
        var t = (m - p[0]) / (q[0] - p[0]), x = rgb(p[1]), y = rgb(q[1]);
        return 'rgb(' + x.map(function (v, k) { return Math.round(v + (y[k] - v) * t); }).join(',') + ')';
      }
    }
    return STOPS[0][1];
  }
  var fmtT = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Tokyo', hour: '2-digit', minute: '2-digit', hour12: false });
  function tick() {
    var s = fmtT.format(new Date()), p = s.split(':'), m = +p[0] * 60 + +p[1];
    a.style.setProperty('--sky', mix(m));
    a.querySelector('.sky__t').textContent = '浅草橋 いま ' + s;
    a.hidden = false;
  }
  tick();
  setInterval(tick, 60000);
})();
