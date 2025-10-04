// Sistema SaaS CiviPro - Theme toggle
// Desenvolvido por João Layon

(function () {
  const root = document.documentElement;
  const toggle = document.getElementById("themeToggle");

  const stored = localStorage.getItem("civipro_theme");
  if (stored === "dark" || (!stored && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }

  toggle && toggle.addEventListener("click", function () {
    if (document.documentElement.classList.contains("dark")) {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("civipro_theme", "light");
    } else {
      document.documentElement.classList.add("dark");
      localStorage.setItem("civipro_theme", "dark");
    }
  });

  const mobileBtn = document.getElementById("mobileMenuBtn");
  mobileBtn && mobileBtn.addEventListener("click", function () {
    const side = document.querySelector("aside.sidebar");
    if (side) side.classList.toggle("hidden");
  });
})();
