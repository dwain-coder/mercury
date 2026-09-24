// 泊まる街を選ぶ — ranks areas by documented attributes only. The scoring is the same rule
// printed under the table on the page; nothing here is weighted in secret.
(function () {
  var form = document.getElementById('choose');
  var out = document.getElementById('choose-out');
  var raw = document.getElementById('choose-data');
  if (!form || !out || !raw) return;
  var data = JSON.parse(raw.textContent);

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function picked(name) {
    return Array.prototype.map.call(form.querySelectorAll('input[name="' + name + '"]:checked'), function (i) { return i.value; });
  }

  function score(area, traits, needs) {
    var pts = 0, why = [];
    traits.forEach(function (t) {
      if (area.traits.indexOf(t) !== -1) { pts += 2; why.push(['+2', data.traits[t]]); }
    });
    if (needs.indexOf('haneda') !== -1 && area.haneda) { pts += 2; why.push(['+2', '羽田から乗り換えなし']); }
    if (needs.indexOf('narita') !== -1 && area.narita) { pts += 2; why.push(['+2', '成田から乗り換えなし']); }
    if (needs.indexOf('lines') !== -1 && area.lines.length >= 4) { pts += 1; why.push(['+1', area.lines.length + '路線']); }
    return { pts: pts, why: why };
  }

  function render() {
    var traits = picked('trait'), needs = picked('need'), who = picked('who')[0];
    if (!traits.length && !needs.length) { out.hidden = true; return; }
    var ranked = Object.keys(data.areas).map(function (k) {
      var a = data.areas[k], s = score(a, traits, needs);
      return { key: k, area: a, pts: s.pts, why: s.why };
    }).sort(function (x, y) { return y.pts - x.pts; });   // stable: ties keep table order

    var top = ranked[0];
    var html = '<p class="choose__k">選んだ条件にいちばん当てはまるのは</p>' +
      '<h2 class="choose__h">' + esc(top.area.name) + '</h2>';
    if (top.pts === 0) {
      html = '<p class="choose__k">選んだ条件に当てはまる特徴を持つ街は、この表の中にはありませんでした。</p>';
    }
    html += '<ol class="choose__rank">' + ranked.map(function (r) {
      var why = r.why.length ? r.why.map(function (w) { return '<li><b>' + w[0] + '</b>' + esc(w[1]) + '</li>'; }).join('')
                             : '<li class="none">当てはまる項目なし</li>';
      var link = r.area.page ? ' <a href="' + r.area.page + '">この街のガイド</a>' : '';
      return '<li><div class="choose__row"><span class="choose__name">' + esc(r.area.name) + '</span>' +
        '<span class="choose__pts">' + r.pts + '点</span>' + link + '</div><ul class="choose__why-list">' + why + '</ul></li>';
    }).join('') + '</ol>';

    if (top.pts > 0 && top.area.hotels.length) {
      html += '<p class="choose__k">' + esc(top.area.name) + 'で当サイトが取り上げている宿</p>';
      top.area.hotels.forEach(function (h) {
        var t = document.getElementById('hotel-' + h);
        if (t) html += t.innerHTML;
      });
      if (who === 'group') {
        html += '<p class="choose__why">3人以上の場合：この宿の公開情報で確認できる部屋はシングル・ダブル・ツインで、3名以上で泊まれる部屋は確認できませんでした。</p>';
      }
    } else if (top.pts > 0) {
      html += '<p class="choose__why">' + esc(top.area.name) + 'の宿は、当サイトではまだ取り上げていません。下の検索から日付を入れて探せます。</p>';
    }
    out.innerHTML = html;
    out.hidden = false;
  }

  form.addEventListener('change', render);
})();
