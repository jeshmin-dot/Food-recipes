const filterButtons = document.querySelectorAll(".filter-button");
const recipeCards = document.querySelectorAll(".recipe-card");
const searchInput = document.querySelector("#recipe-search");
const resultCount = document.querySelector(".result-count");
const emptyState = document.querySelector(".empty-state");
let activeCategory = "all";

function updateRecipes() {
    const searchTerm = searchInput.value.trim().toLowerCase();
    let visibleCount = 0;

    recipeCards.forEach((card) => {
        const matchesCategory =
            activeCategory === "all" || card.dataset.category === activeCategory;
        const matchesSearch = card.dataset.search.toLowerCase().includes(searchTerm);
        const shouldShow = matchesCategory && matchesSearch;

        card.hidden = !shouldShow;

        if (shouldShow) {
            visibleCount += 1;
        }
    });

    resultCount.textContent = `${visibleCount} ${visibleCount === 1 ? "recipe" : "recipes"} shown`;
    emptyState.hidden = visibleCount > 0;
}

filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
        activeCategory = button.dataset.filter;

        filterButtons.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");

        updateRecipes();
    });
});

searchInput.addEventListener("input", updateRecipes);
