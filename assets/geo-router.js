/* TraderFeeSaver geo-routing: when the page's exchange doesn't accept the
   visitor's country, suggest the best available alternative instead of
   wasting the click. Country via GeoJS (free, keyless, CORS). Fails silent. */
(function () {
  "use strict";

  var EU = ["AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE"];

  var EXCHANGES = {
    binance: { name: "Binance", page: "/index.html", blocked: ["US", "CA"] },
    bybit:   { name: "Bybit",   page: "/bybit-referral-code-2026.html",   blocked: ["US", "CA", "GB"] },
    okx:     { name: "OKX",     page: "/okx-referral-code-2026.html",     blocked: ["US", "CA"] },
    mexc:    { name: "MEXC",    page: "/mexc-referral-code-2026.html",    blocked: ["US"] },
    bitget:  { name: "Bitget",  page: "/bitget-referral-code-2026.html",  blocked: ["US", "CA", "GB"] },
    gateio:  { name: "Gate.io", page: "/gate-io-referral-code-2026.html", blocked: ["US"] },
    bingx:   { name: "BingX",   page: "/bingx-referral-code-2026.html",   blocked: ["US"] },
    exness:  { name: "Exness",  page: "/exness.html",                     blocked: ["US", "CA", "GB"].concat(EU), forex: true }
  };

  // preference order when suggesting an alternative (crypto only)
  var RANKING = ["binance", "bybit", "okx", "mexc", "bitget", "gateio", "bingx"];

  function currentExchange() {
    var p = location.pathname.toLowerCase();
    if (p.indexOf("bybit") !== -1) return "bybit";
    if (p.indexOf("okx") !== -1) return "okx";
    if (p.indexOf("mexc") !== -1) return "mexc";
    if (p.indexOf("bitget") !== -1) return "bitget";
    if (p.indexOf("gate") !== -1) return "gateio";
    if (p.indexOf("bingx") !== -1) return "bingx";
    if (p.indexOf("exness") !== -1) return "exness";
    if (p.indexOf("binance") !== -1 || p === "/" || p.indexOf("index") !== -1) return "binance";
    return null;
  }

  function pickAlternative(currentKey, country) {
    for (var i = 0; i < RANKING.length; i++) {
      var key = RANKING[i];
      if (key === currentKey) continue;
      if (EXCHANGES[key].blocked.indexOf(country) === -1) return EXCHANGES[key];
    }
    return null;
  }

  function showBanner(current, alt, countryName) {
    if (sessionStorage.getItem("tfs_geo_dismissed")) return;
    var bar = document.createElement("div");
    bar.setAttribute("role", "note");
    bar.style.cssText =
      "position:relative;z-index:9000;background:#222a38;border-bottom:2px solid #F0B90B;" +
      "color:#ffffff;font-family:'Inter',sans-serif;font-size:14px;line-height:1.5;" +
      "padding:12px 44px 12px 16px;text-align:center;";
    var msg = document.createElement("span");
    msg.textContent = current.name + " doesn’t accept new traders from " + countryName + ". ";
    bar.appendChild(msg);
    if (alt) {
      var link = document.createElement("a");
      link.href = alt.page;
      link.style.cssText = "color:#F0B90B;font-weight:600;text-decoration:underline;";
      link.textContent = "Get the best " + alt.name + " referral code instead →";
      bar.appendChild(link);
    }
    var close = document.createElement("button");
    close.setAttribute("aria-label", "Dismiss");
    close.textContent = "×";
    close.style.cssText =
      "position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;" +
      "border:none;color:#8b95a5;font-size:20px;cursor:pointer;padding:4px 8px;";
    close.onclick = function () {
      bar.remove();
      sessionStorage.setItem("tfs_geo_dismissed", "1");
    };
    bar.appendChild(close);
    document.body.insertBefore(bar, document.body.firstChild);
  }

  function run(geo) {
    var key = currentExchange();
    if (!key) return;
    var current = EXCHANGES[key];
    if (current.blocked.indexOf(geo.country) === -1) return;
    var alt = current.forex ? null : pickAlternative(key, geo.country);
    if (!alt) return; // nothing honest to offer — stay quiet
    showBanner(current, alt, geo.name || "your country");
  }

  try {
    var cached = sessionStorage.getItem("tfs_geo");
    if (cached) {
      run(JSON.parse(cached));
      return;
    }
    fetch("https://get.geojs.io/v1/ip/country.json")
      .then(function (r) { return r.json(); })
      .then(function (geo) {
        if (!geo || !geo.country) return;
        sessionStorage.setItem("tfs_geo", JSON.stringify(geo));
        run(geo);
      })
      .catch(function () {});
  } catch (e) { /* never break the page */ }
})();
