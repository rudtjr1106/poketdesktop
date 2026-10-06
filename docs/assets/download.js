/* '최신 버전 받기' 를 릴리스의 파일에 바로 잇는다.

   파일 이름에 버전이 들어 있어서(poketdesktop-v1.10.2.zip) 주소를 박아 둘 수 없다. 그래서 깃허브에
   최신 릴리스를 물어 그 파일의 주소로 바꾼다. 윈도우는 zip, 맥은 dmg 이다. 물어보지 못했거나
   휴대폰처럼 받을 파일이 없는 기기에서는 원래대로 릴리스 쪽으로 간다.

     data-download="auto"   이 기기에 맞는 파일
     data-download="win"    윈도우 zip        data-download="mac"   맥 dmg
     data-version           버전을 적는 자리 */
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll("a[data-download]"));
  if (!links.length || !window.fetch) { return; }
  var API = "https://api.github.com/repos/rudtjr1106/poketdesktop/releases/latest";
  var KEY = "posktop-release";

  function device() {
    var ua = navigator.userAgent || "";
    var p = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
    if (/Android|iPhone|iPad|iPod/i.test(ua)) { return "other"; }
    if (/Win/i.test(p) || /Windows/i.test(ua)) { return "win"; }
    if (/Mac/i.test(p)) { return "mac"; }
    return "other";
  }
  function apply(rel) {
    var files = { win: null, mac: null };
    (rel.assets || []).forEach(function (a) {
      var name = a.name || "", url = a.url || "";
      if (url.indexOf("https://github.com/rudtjr1106/poketdesktop/releases/download/") !== 0) { return; }
      if (/\.dmg$/.test(name)) { files.mac = a; }
      else if (/\.zip$/.test(name) && name.indexOf("-mac") < 0) { files.win = a; }
    });
    var mine = device();
    links.forEach(function (el) {
      var want = el.getAttribute("data-download");
      var f = files[want === "auto" ? mine : want];
      if (!f) { return; }
      el.href = f.url;
      el.title = f.name + " (" + Math.round(f.size / 1048576) + "MB)";
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-version]"), function (el) {
      if (rel.tag) { el.textContent = " (" + rel.tag + ")"; }
    });
  }
  function slim(r) {                         // 쓸 것만 추려 둔다
    return { tag: r.tag_name, assets: (r.assets || []).map(function (a) {
      return { name: a.name, url: a.browser_download_url, size: a.size };
    }) };
  }

  try {
    var kept = JSON.parse(sessionStorage.getItem(KEY) || "null");
    if (kept && kept.assets) { return apply(kept); }
  } catch (e) { /* 저장소를 못 쓰는 창이다 - 그냥 물어본다 */ }
  fetch(API, { headers: { Accept: "application/vnd.github+json" } })
    .then(function (r) { if (!r.ok) { throw new Error(String(r.status)); } return r.json(); })
    .then(function (r) {
      var rel = slim(r);
      try { sessionStorage.setItem(KEY, JSON.stringify(rel)); } catch (e) { /* 넘어간다 */ }
      apply(rel);
    })
    .catch(function () { /* 릴리스 쪽으로 가는 원래 주소가 그대로 남는다 */ });
})();
