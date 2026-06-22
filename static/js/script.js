const filterButtons = document.querySelectorAll(".filter-button");
const recipeCards = document.querySelectorAll(".recipe-card");

filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const selectedCategory = button.dataset.filter;

        filterButtons.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");

        recipeCards.forEach((card) => {
            const shouldShow =
                selectedCategory === "all" || card.dataset.category === selectedCategory;

            card.hidden = !shouldShow;
        });
    });
});
