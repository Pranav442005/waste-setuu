(() => {
  "use strict";

  const LANGS = {
    en: "English", hi: "हिन्दी", mr: "मराठी", gu: "ગુજરાતી",
    bn: "বাংলা", ta: "தமிழ்", te: "తెలుగు", kn: "ಕನ್ನಡ"
  };
  const STORAGE_KEY = "wasteSetuLanguage";
  const CACHE_KEY = "wasteSetuTranslationCacheV1";
  const API_URL = "https://waste-setuu.onrender.com/api/translate/batch";
  const MAX_BATCH = 35;
  let currentLanguage = localStorage.getItem(STORAGE_KEY) || "en";
  let observer;
  let translating = false;
  let rerunRequested = false;

  const normalize = value => (value || "").replace(/\s+/g, " ").trim();
  const cache = (() => {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "{}"); }
    catch { return {}; }
  })();

  function saveCache() {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(cache)); }
    catch (error) { console.warn("Translation cache could not be saved.", error); }
  }

  function isIgnored(node) {
    const parent = node.parentElement;
    if (!parent) return true;
    if (parent.closest("script,style,noscript,code,pre,textarea,[data-no-translate]")) return true;
    if (!normalize(node.__wsOriginal ?? node.nodeValue)) return true;
    return false;
  }

  function collectTextNodes() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!isIgnored(node)) {
        if (node.__wsOriginal === undefined) node.__wsOriginal = node.nodeValue;
        nodes.push(node);
      }
    }
    return nodes;
  }

  async function requestTranslations(texts, language) {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texts, target_language: language })
    });
    if (!response.ok) {
      let message = `Translation service error (${response.status})`;
      try {
        const data = await response.json();
        if (data.detail) message = data.detail;
      } catch {}
      throw new Error(message);
    }
    const data = await response.json();
    if (!Array.isArray(data.translations) || data.translations.length !== texts.length) {
      throw new Error("Translation service returned an unexpected result.");
    }
    return data.translations;
  }

  async function translateAttributes(language) {
    const elements = [...document.querySelectorAll(
      "input[placeholder],input[aria-label],textarea[placeholder],button[title],[title],[aria-label]"
    )].filter(el => !el.closest("[data-no-translate]"));
    const attrs = [];
    for (const el of elements) {
      for (const attr of ["placeholder", "title", "aria-label"]) {
        if (!el.hasAttribute(attr)) continue;
        const key = `attr:${attr}:${el.getAttribute(`data-ws-original-${attr}`) || el.getAttribute(attr)}`;
        if (!el.hasAttribute(`data-ws-original-${attr}`)) {
          el.setAttribute(`data-ws-original-${attr}`, el.getAttribute(attr));
        }
        const original = el.getAttribute(`data-ws-original-${attr}`);
        if (original && normalize(original)) attrs.push({ el, attr, original, key });
      }
    }
    const missing = [...new Set(attrs.map(a => a.original))]
      .filter(text => language === "en" || !cache[`${language}:${text}`]);
    for (let i = 0; i < missing.length; i += MAX_BATCH) {
      const batch = missing.slice(i, i + MAX_BATCH);
      const translated = language === "en" ? batch : await requestTranslations(batch, language);
      batch.forEach((text, index) => cache[`${language}:${text}`] = translated[index]);
    }
    attrs.forEach(a => {
      a.el.setAttribute(a.attr, language === "en" ? a.original : (cache[`${language}:${a.original}`] || a.original));
    });
  }

  async function applyLanguage(language) {
    if (!LANGS[language]) return;
    currentLanguage = language;
    localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
    document.querySelectorAll("select.language,select#language,select[data-language-selector]")
      .forEach(select => { select.value = language; });

    if (translating) {
      rerunRequested = true;
      return;
    }
    translating = true;
    try {
      const nodes = collectTextNodes();
      const originals = nodes.map(node => node.__wsOriginal);
      if (language === "en") {
        nodes.forEach(node => { node.nodeValue = node.__wsOriginal; });
      } else {
        const uniqueMissing = [...new Set(originals.filter(text =>
          normalize(text) && !cache[`${language}:${normalize(text)}`]
        ))];
        for (let i = 0; i < uniqueMissing.length; i += MAX_BATCH) {
          const batch = uniqueMissing.slice(i, i + MAX_BATCH);
          const translated = await requestTranslations(batch, language);
          batch.forEach((text, index) => {
            cache[`${language}:${normalize(text)}`] = translated[index];
          });
          saveCache();
        }
        nodes.forEach(node => {
          const original = node.__wsOriginal;
          const translated = cache[`${language}:${normalize(original)}`];
          if (translated) {
            const leading = original.match(/^\s*/)?.[0] || "";
            const trailing = original.match(/\s*$/)?.[0] || "";
            node.nodeValue = leading + translated + trailing;
          }
        });
      }
      await translateAttributes(language);
      saveCache();
    } catch (error) {
      console.error("Waste Setu translation failed:", error);
      window.dispatchEvent(new CustomEvent("wastesetu:translation-error", {
        detail: { message: error.message }
      }));
    } finally {
      translating = false;
      if (rerunRequested) {
        rerunRequested = false;
        applyLanguage(currentLanguage);
      }
    }
  }

  function setupSelectors() {
    document.querySelectorAll(
      "select.language,select#language,select[data-language-selector],button.language"
    ).forEach(old => {
      let select = old;
      if (old.tagName === "BUTTON") {
        select = document.createElement("select");
        select.className = "language";
        select.setAttribute("aria-label", "Select language");
        old.replaceWith(select);
      }
      select.innerHTML = Object.entries(LANGS)
        .map(([code, name]) => `<option value="${code}">${name}</option>`).join("");
      select.value = currentLanguage;
      select.addEventListener("change", () => applyLanguage(select.value));
    });
  }

  function watchDynamicContent() {
    if (observer) observer.disconnect();
    observer = new MutationObserver(() => {
      if (currentLanguage !== "en" && !translating) applyLanguage(currentLanguage);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function setup() {
    setupSelectors();
    watchDynamicContent();
    applyLanguage(currentLanguage);
  }

  window.WasteSetuI18n = {
    setLanguage: applyLanguage,
    getLanguage: () => currentLanguage,
    languages: LANGS
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup, { once: true });
  } else {
    setup();
  }
})();
