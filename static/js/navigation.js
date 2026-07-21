document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".nav-toggle");
  const navigation = document.getElementById("primary-navigation");
  if (!toggle || !navigation) return;

  const closeNavigation = ({ restoreFocus = false } = {}) => {
    navigation.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation");
    if (restoreFocus) toggle.focus();
  };
  const openNavigation = () => {
    navigation.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close navigation");
    const firstLink = navigation.querySelector("a, button, input, select, textarea");
    if (firstLink) firstLink.focus();
  };

  toggle.addEventListener("click", () => navigation.classList.contains("is-open") ? closeNavigation() : openNavigation());
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navigation.classList.contains("is-open")) closeNavigation({ restoreFocus: true });
  });
  document.addEventListener("click", (event) => {
    if (navigation.classList.contains("is-open") && !navigation.contains(event.target) && !toggle.contains(event.target)) closeNavigation();
  });
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a") && window.matchMedia("(max-width: 991px)").matches) closeNavigation();
  });
  window.addEventListener("resize", () => {
    if (!window.matchMedia("(max-width: 991px)").matches) closeNavigation();
  });
});
