// Same storage key and class as the native Hindsight console, so both stay in sync.
(function () {
  let saved = null;
  try { saved = localStorage.getItem("theme"); } catch (e) { /* storage disabled */ }
  const dark = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", dark);
})();

function bindThemeButton(button) {
  if (!button) return;
  const paint = () => {
    const dark = document.documentElement.classList.contains("dark");
    button.dataset.tip = dark ? "切换到浅色" : "切换到深色";
    button.setAttribute("aria-label", button.dataset.tip);
    button.innerHTML = `<i data-lucide="${dark ? "sun" : "moon"}"></i>`;
    if (window.lucide) lucide.createIcons();
  };
  button.onclick = () => {
    const dark = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", dark);
    try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch (e) { /* storage disabled */ }
    paint();
  };
  paint();
}
