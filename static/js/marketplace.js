document.addEventListener("DOMContentLoaded", () => {
  const forms = document.querySelectorAll("#marketplace-form, #filter-form");
  const loading = document.getElementById("marketplace-loading");
  forms.forEach((form) => form.addEventListener("submit", () => {
    if (loading) loading.hidden = false;
  }));
});
